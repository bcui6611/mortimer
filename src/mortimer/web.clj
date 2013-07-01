(ns mortimer.web
  "### The web app server"
  (:gen-class)
  (:use compojure.core)
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
            [ring.middleware.stacktrace :refer [wrap-stacktrace]]
            [aleph.http :refer [start-http-server
                                wrap-ring-handler]]))

(defn json-response
  "Transform `obj` to JSON and create a ring response object of it."
  [obj]
  (-> (response/response (json/generate-string obj))
      (response/content-type "application/json; charset=utf-8")))

(defn delist 
  "Takes a string of the form `\"thing1, thing2, thing3\"`, and returns
   `[\"thing1\" \"thing2\" \"thing3\"]`, or `:all` if the string contains
   only whitespace and commas."
  [lstring]
  (if lstring
    (if-let [els (s/split lstring #",")]
      (let [els (map s/trim els)]
        (if-let [els (seq (remove empty? els))]
          els :all)) :all) :all))

(def statopts
  {"derivative" [opt/derivative :cubic]})

(defn statfunc
  "Get function over stat in memory db across the given files and buckets.
   Stat name can be given as `\"stat:option\"` (such as `\"cmd_get:derivative\"`)
   to wrap with a function from statopts."
  [stat files buckets]
  (let [[stat opt] (s/split stat #":")
        [optf & interpargs] (statopts opt [identity])
        statsets (mdb/across files buckets)]
    (update-in (mdb/combined (keyword stat) statsets interpargs)
               [:func] optf)))

(defroutes app-routes
  (GET "/files" [] (json-response (mdb/list-files)))
  (GET "/buckets" [] (json-response (mdb/list-buckets)))
  (GET "/stats" [] (json-response (mdb/list-stats)))
  (GET "/statdata" {{stats :stat
                     buckets :buckets
                     res :res
                     files :files} :params}
       (let [res (read-string (or res "1")) ; default to 1s resoluton
             [stats buckets files] (map delist [stats buckets files])
             combinedfuns (for [stat stats] (statfunc stat files buckets))
             ;; The juxtaposition of the requested stat functions.
             ;; (pointfun time-in-seconds) returns
             ;; [time-in-milliseconds stat1value stat2value ...etc].
             pointfun (apply juxt (concat [(partial * 1000)]
                                          (map :func combinedfuns)))
             ;; Find the time interval where all the requested stats overlap
             [mint maxt] (iv/intersect (map :interval combinedfuns))]
         (json-response
           {:interval [mint maxt]
            :stats stats
            ;; Calculate points at every `res` seconds in the overlapping interval
            :points (for [x (range mint (inc maxt) res)]
                      (pointfun x))})))
  (GET "/" [] {:status 302
               :headers {"location" "/index.html"}})
  (route/resources "/")
  (route/not-found "404!"))

(def handler
  (-> #'app-routes
      api
      wrap-stacktrace))

(defn start-server [{:keys [port]}]
  (-> #'handler
      wrap-ring-handler
      (start-http-server {:port port}))
  (println (str "Listening on http://localhost:" port "/")))

(defn -main [& args]
  (let [[opts more usage]
        (cli args
             ["-p" "--port" "Start webserver on this port" :parse-fn read-string :default 18334]
             ["-d" "--dir" "Directory to search for collectinfo .zips" :default "."]
             ["-h" "--help" "Display help" :flag true])]
    (if (:help opts)
      (println usage)
      ;otherwise
      (let [dir (io/file (:dir opts))
            files (->> (.listFiles dir)
                       (filter #(.endsWith (.getName %) ".zip")))
            numfiles (count files)
            numloaded (atom 0)]
        (start-server opts)
        (print (str "Loading files... 0/" numfiles))
        (flush)
        ;; Load the found .zips file into the memory DB in parallel
        (doseq [f files]
         (future (mdb/load-collectinfo f :as (.getName f))
                 (print (str "\rLoading files... " (swap! numloaded inc) "/" numfiles)) (flush)
                 (when (= numfiles @numloaded)
                   (println "\nDone!"))))))))


