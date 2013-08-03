(ns mortimer.web
  "### The web app server"
  (:use compojure.core
        clojure.pprint)
  (:require [compojure.route :as route]
            [clojure.tools.cli :refer [cli]]
            [clojure.java.io :as io]
            [clojure.string :as s]
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

(defn derivative [pointseries & interpargs]
  (let [interpargs (or interpargs [:linear])
        interped (apply interp/interpolate pointseries interpargs)
        derif (opt/derivative interped)]
    (for [[t _] pointseries]
      [t (derif t)])))

(defn create-pointseries
  [defaults query]
  (let [{:keys [stat options]} (parse-statqry query)
        options (merge defaults options)
        bucket (options :bucket)
        file (options :file)
        pointseries (mdb/extract
                      (keyword stat)
                      (get-in @mdb/stats [file bucket]))
        pointseries (if (options :rate)
                      ;; Mark any points where the derivative of Uptime is negative as nil.
                      ;; (they will show up as holes, rather than massively negative values.)
                      (map (fn [[dt dv] [ut uv]]
                             (if-not (neg? uv) [dt dv] [dt nil])) 
                           (derivative pointseries)
                           (derivative (mdb/extract :uptime (get-in @mdb/stats [file bucket]))))
                      pointseries)]
    pointseries))

(defn multistat-response
  "Combine multiple stats, but only at real points"
  [stats]
  (let
    [pointseries (map (partial create-pointseries {}) stats)
     times (sort (distinct (map first (apply concat pointseries))))
     pointmaps (map (partial into {}) pointseries)
     pointfn (apply juxt pointmaps)]
    {:stats (map #(s/escape % {\: " " \; " "}) stats)
     :interpolated false
     :points (for [t times]
               (into [(* t 1000)]
                     (pointfn t)))}))

(defonce connected-dudes (atom #{}))

(defn send-update [dudes]
  (let [message (json/generate-string
                  {:kind :status-update
                   :data {:files (mdb/list-files)
                          :loading @mdb/progress
                          :buckets (mdb/list-buckets)}})]
    (doseq [d dudes]
      (lam/enqueue d message))))

(def broadcast-channel (lam/permanent-channel))
(defn ws-handler
  [ch handshake]
  (swap! connected-dudes conj ch)
  (lam/siphon ch broadcast-channel)
  (lam/siphon broadcast-channel ch)
  (lam/on-closed ch #(swap! connected-dudes disj ch))
  (send-update [ch]))

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
      (if-let [currentrev (s/trim (slurp "http://s3.crate.im/mortimer-build/git-rev.txt"))]
        (if (= currentrev gitrev)
          (println "Up to date!")
          (let [diffs (:body  
                        (http/get (str "https://api.github.com/repos/couchbaselabs/mortimer/"
                                       "compare/" gitrev "..." currentrev) {:as :json}))]
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
    (catch Exception e "Couldn't check for updates")))

(defn -main [& args]
  (let [[opts more usage]
        (cli args
             ["-p" "--port" "Start webserver on this port" :parse-fn read-string :default 18334]
             ["-d" "--dir" "Directory to search for collectinfo .zips" :default "."]
             ["-v" "--debug" "Enable debugging messages" :flag true]
             ["-n" "--no-browse" "Don't auto open browser" :flag true :default true]
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
        (check-update)
        (start-server opts)
        (mdb/progress-updater-start)
        (swap! mdb/progress-watchers conj
               (fn [] (send-update @connected-dudes)))
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

