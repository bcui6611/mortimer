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
            [mortimer.process :as proc]
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

(defonce broadcast-channel (lam/permanent-channel))

(programs open)

(defn json-response
  "Transform `obj` to JSON and create a ring response object of it."
  [obj]
  (-> (response/response (json/generate-string obj))
      (response/content-type "application/json; charset=utf-8")))

(defn parse-statqry
  "Parses \"expr;k=v,k2=v2\" into
   {:expr \"expr\" :context {:k \"v\" :k2 \"v2\"}}"
  [qstr]
  (let [[_ expr optstring] (re-matches #"^([^;]+);(.*)$" qstr)
        pairstrings (s/split optstring #",")
        ctx (into {}
                  (map (fn [ps]
                         (let [[k v] (s/split ps #"=")]
                           [(keyword k) v]))
                       pairstrings))]
    {:expr expr
     :context ctx}))

(defonce session-data 
  (atom {:smoothing-window 0}))

(defn create-pointseries*
  [session-context query]
  (let [{:keys [expr context]} (parse-statqry query)
        context (merge session-context context)]
    (try (with-meta (proc/expr-eval-string expr context)
               {:name 
                (str (or (:name context) expr)
                     " in " (:bucket context) " on " (:file context))})
         (catch Exception e
           (lam/enqueue broadcast-channel
                       (json/generate-string 
                         {:kind :error
                          :short (str (.getMessage e))
                          :extra (when-let [d (ex-data e)]
                                   (:extra d))}))
           nil))))

(def create-pointseries-memo* (memo/lru create-pointseries* :lru/threshold 100))

(defn create-pointseries [context query]
  (create-pointseries-memo* context query))

(defn multistat-response
  "Combine multiple stats, but only at real points"
  [stats]
  (let
    [pointseries (keep (partial create-pointseries @session-data) stats)
     times (sort (distinct (map first (apply concat pointseries))))
     pointmaps (map (partial into {}) pointseries)
     pointfn (apply juxt pointmaps)]
    {:stats (map (comp :name meta) pointseries)
     :interpolated false
     :points (for [t times]
               (into [(* t 1000)]
                     (pointfn t)))}))

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
       (let [stats (json/parse-string stats)]
         (json-response (multistat-response stats))))
  (GET "/status-ws" {}
       (wrap-aleph-handler ws-handler))
  (GET "/" [] {:body (slurp (io/resource "public/index.html"))
               :headers {"content-type" "text/html"}})
  (route/resources "/")
  (route/not-found "404!"))

(defn wrap-warns [h]
  (fn [rq]
    (binding [proc/*messages* (atom [])] 
      (let [response (h rq)]
        (doseq [m @proc/*messages*]
          (lam/enqueue broadcast-channel (json/generate-string m)))
        response))))

(def handler
  (-> #'app-routes
      wrap-warns
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
          (println "
  Your copy of mortimer is possibly out of date!

  Get the current version at: 
  http://s3.crate.im/mortimer-build/mortimer.jar\n"))
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

