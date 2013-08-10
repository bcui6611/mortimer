(ns mortimer.web
  "### The web app server"
  (:use compojure.core
        clojure.pprint)
  (:require [compojure.route :as route]
            [clojure.tools.cli :refer [cli]]
            [clojure.java.io :as io]
            [clojure.string :as s]
            [clojure.core.memoize :as memo]
            [mortimer.data :as mdb]
            [mortimer.interval :as iv]
            [cheshire.core :as json]
            [ring.util.response :as response]
            [compojure.handler :refer [api]]
            [incanter.optimize :as opt]
            [incanter.interpolation :as interp]
            [clj-http.client :as http]
            [ring.middleware.stacktrace :refer [wrap-stacktrace]]
            [lamina.core :as lam]
            [me.raynes.conch :refer [programs]]
            [aleph.http :refer [start-http-server
                                wrap-aleph-handler
                                wrap-ring-handler]]))

(programs open)

(defn json-response
  "Transform `obj` to JSON and create a ring response object of it."
  [obj]
  (-> (response/response (json/generate-string obj))
      (response/content-type "application/json; charset=utf-8")))

(defn delist
  "Takes a string of the form `\"thing1, thing2, thing3\"`, and returns
   `[\"thing1\" \"thing2\" \"thing3\"]`, or nil if the string contains
   only whitespace and commas."
  [lstring]
  (when lstring
    (when-let [els (s/split lstring #",")]
      (let [els (map s/trim els)]
        (when-let [els (seq (remove empty? els))]
          els)))))


(defn parse-statqry
  "Parses \"statname:opt;opt2=val2\" into
   {:stat \"statname\" :options {:opt true :opt2 \"val2\"}}"
  [qstr]
  (let [[_ stat rst kvs] (re-matches #"([^:]+)(:(.*))?" qstr)
        kvparts (if kvs (s/split kvs #";") [])
        kvmap (reduce (fn [acc kvstr]
                        (let [[_ k _ v] (re-matches #"([^=]+)(=(.*))?" kvstr)]
                          (if k
                            (conj acc [(keyword k) (or v true)])
                            acc)))
                      {} kvparts)]
    {:stat stat
     :options kvmap}))

(defn moving-average [pointseries window]
  (let [vecseries (vec pointseries)] ; make sure we have fast random access
    (for [n (range 0 (count pointseries))]
      (let [samples (map second (map #(nth vecseries % nil) (range (- n window) (+ n window 1))))
            orig (nth vecseries n)
            [t _] orig]
        (if (or (some nil? samples) (nil? (nth vecseries (- n window 1) nil))) 
          [t nil]
          [t (/ (apply + samples) (count samples))])))))

(defn derivative [pointseries & interpargs]
  (let [interpargs (or interpargs [:linear])
        derivseries (filter (complement (comp nil? second)) pointseries)
        interped (apply interp/interpolate derivseries interpargs)
        derif (opt/derivative interped)]
    (for [[t v] pointseries]
      [t (derif (+ t 1/2))])))

(defonce session-data 
  (atom {:smoothing-window 0}))

(defn create-pointseries*
  [defaults query smoothing-window]
  (let [{:keys [stat options]} (parse-statqry query)
        options (merge defaults options)
        bucket (options :bucket)
        file (options :file)
        pointseries (mdb/extract
                      (keyword stat)
                      (get-in @mdb/stats [file bucket]))
        pointseries (if (options :rate)
                      (let [uprate
                            (-> (mdb/extract :uptime (get-in @mdb/stats [file bucket]))
                                (moving-average smoothing-window)
                                (derivative))]
                        ;; Mark any points where the derivative of Uptime is negative as nil.
                        ;; (they will show up as holes, rather than massively negative values.)
                        (-> pointseries
                            (moving-average smoothing-window)
                            (derivative)
                            (->> (map (fn [[ut uv] [dt dv]]
                                        (if-not (neg? uv) [dt dv] [dt nil]))
                                      uprate))))
                      pointseries)]
    (with-meta pointseries 
               {:name (str stat (if (options :rate) " per second")
                           " in " bucket " on " file)})))

(def create-pointseries-memo* (memo/lru create-pointseries* :lru/threshold 100))

(defn create-pointseries [defaults query]
  (create-pointseries-memo* defaults query (:smoothing-window @session-data)))

(defn multistat-response
  "Combine multiple stats, but only at real points"
  [stats]
  (let
    [pointseries (map (partial create-pointseries {}) stats)
     times (sort (distinct (map first (apply concat pointseries))))
     pointmaps (map (partial into {}) pointseries)
     pointfn (apply juxt pointmaps)]
    {:stats (map (comp :name meta) pointseries)
     :interpolated false
     :points (for [t times]
               (into [(* t 1000)]
                     (pointfn t)))}))

(defonce broadcast-channel (lam/permanent-channel))

(defn send-update []
  (let [message (json/generate-string
                  {:kind :status-update
                   :data {:files (mdb/list-files)
                          :loading @mdb/progress
                          :buckets (mdb/list-buckets)}})]
    (lam/enqueue broadcast-channel message)))

(defn send-session [ch]
  (lam/enqueue ch (json/generate-string {:kind "session-data" :data @session-data})))

(defn ws-dispatch [ch msg]
  (try (when-let [parsed (json/parse-string msg true)]
         (case (:kind parsed)
           ;; broadcast this message to all receivers
           "range-update" (lam/enqueue broadcast-channel msg)
           (do (println "Could not handle message.")
               (pprint parsed))
           "session-apply"
           (let [action (read-string (:code parsed))
                 code `(swap! session-data ~@action)]
             (eval code)
             (send-session broadcast-channel))))
       (catch Exception e 
         (println "Exception handling websocket message:" msg e)
         (.printStackTrace e))))


(defn ws-handler
  [ch handshake]
  (lam/siphon broadcast-channel ch)
  (lam/receive-all ch #(#'ws-dispatch ch %))
  (send-session ch)
  (send-update))

(defroutes app-routes
  (GET "/files" [] (json-response (mdb/list-files)))
  (GET "/buckets" [] (json-response (mdb/list-buckets)))
  (GET "/stats" [] (json-response (mdb/list-stats)))
  (GET "/events" [file] (json-response (mdb/get-events file)))
  (GET "/statdata" {{stats :stat} :params}
       (let [stats (delist stats)]
         (json-response (multistat-response stats))))
  (GET "/status-ws" {}
       (wrap-aleph-handler ws-handler))
  (GET "/" [] {:body (slurp (io/resource "public/index.html"))
               :headers {"content-type" "text/html"}})
  (route/resources "/")
  (route/not-found "404!"))

(def handler
  (-> #'app-routes
      api
      wrap-stacktrace))

(defonce server (atom nil))

(defn start-server [{:keys [port browse]}]
  (reset! server (-> #'handler
                     wrap-ring-handler
                     (start-http-server {:port port :websocket true})))
  (println (str "Listening on http://localhost:" port "/"))
  (when browse
    (try
      (open (str "http://localhost:" port "/"))
      (catch Exception e nil))))

(defn check-update []
  (try 
    (if-let [gitrev (s/trim (slurp (io/resource "git-rev.txt")))]
      (if-let [currentrev (-> "http://s3.crate.im/mortimer-build/git-rev.txt"
                              (http/get {:socket-timeout 1000}
                                        {:conn-timeout 1000})
                              :body s/trim)]
        (if (= currentrev gitrev)
          (println "Up to date!")
          (let [diffs (:body  
                        (http/get (str "https://api.github.com/repos/couchbaselabs/mortimer/"
                                       "compare/" gitrev "..." currentrev)
                                  {:socket-timeout 1000
                                   :conn-timeout 1000
                                   :as :json}))]
            (if (= "ahead" (:status diffs))
              (do
                (println "New version available! Changes:")
                (doseq [commit (:commits diffs)]
                  (let [msg (-> commit :commit :message)
                        msg (first (s/split-lines msg))]
                    (println " *" msg)))
                (println "\nhttp://s3.crate.im/mortimer-build/mortimer.jar\n"))
              (println "You have a newer version than is available for download."))))
        (println "Couldn't check for updated version"))
      (println "Unknown mortimer version"))
    (catch Exception e 
      (println "Couldn't check for updates" e))))

(defn -main [& args]
  (let [[opts more usage]
        (cli args
             ["-p" "--port" "Start webserver on this port" :parse-fn read-string :default 18334]
             ["-d" "--dir" "Directory to search for collectinfo .zips" :default "."]
             ["-v" "--debug" "Enable debugging messages" :flag true]
             ["-u" "--update" "Check for updates" :flag true :default true]
             ["-n" "--browse" "Auto open browser" :flag true :default true]
             ["-h" "--help" "Display help" :flag true])]
    (when (:debug opts)
      (pprint opts)
      (alter-var-root #'mortimer.debug/*debug* (constantly true)))
    (if (:help opts)
      (println usage)
      ;otherwise
      (let [dir (io/file (:dir opts))
            files (->> (.listFiles dir)
                       (filter #(.endsWith (.getName %) ".zip")))
            numfiles (count files)
            numloaded (atom 0)
            messages (atom "")]
        (when (:update opts) (check-update))
        (start-server opts)
        (mdb/progress-updater-start)
        (swap! mdb/progress-watchers conj
               (fn [] (send-update)))
        (print (str "Loading files... 0/" numfiles))
        (flush)
        ;; Load the found .zips file into the memory DB in parallel
        (try
          (doseq [fut
                  (mapv (fn [f]
                          (future (swap! messages str
                                         (with-out-str
                                           (mdb/load-collectinfo f :as (.getName f))))
                                  (print (str "\rLoading files... "
                                              (swap! numloaded inc) "/" numfiles))
                                  (flush)))
                        files)]
            @fut)
          (finally
            (println "\nDone!")
            (println @messages)))))))

