(ns mortimer.web
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

(defn json-response [obj]
  (-> (response/response (json/generate-string obj))
      (response/content-type "application/json; charset=utf-8")))

(defn delist [lstring]
  (if lstring
    (if-let [els (s/split lstring #",")]
      (let [els (map s/trim els)]
        (if-let [els (seq (remove empty? els))]
          els :all)) :all) :all))

(def statopts
  {"derivative" opt/derivative})

(defn statfunc [stat files buckets]
  (let [[stat opt] (s/split stat #":")
        optf (statopts opt identity)
        statsets (mdb/across files buckets)]
    (update-in (mdb/combined (keyword stat) statsets)
               [:func] optf)))

(defroutes app-routes
  (GET "/files" [] (json-response (mdb/list-files)))
  (GET "/buckets" [] (json-response (mdb/list-buckets)))
  (GET "/stats" [] (json-response (mdb/list-stats)))
  (GET "/statdata" {{stats :stat
                     buckets :buckets
                     res :res
                     files :files} :params}
       (let [[stats buckets files] (map delist [stats buckets files])
             combinedfuns (for [stat stats] (statfunc stat files buckets))
             res (read-string (or res "1"))
             pointfun (apply juxt (concat [(partial * 1000)]
                                          (map :func combinedfuns)))
             [mint maxt] (iv/intersect (map :interval combinedfuns))]
         (json-response
           {:interval [mint maxt]
            :stats stats
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
      (do
        (let [dir (io/file (:dir opts))
              files (->> (.listFiles dir)
                         (filter #(.endsWith (.getName %) ".zip")))]
          (start-server opts)
          (doseq [f files]
            (println "Loading" f)
            (mdb/load-collectinfo f :as (.getName f))
            (println "Loaded" f)))))))


