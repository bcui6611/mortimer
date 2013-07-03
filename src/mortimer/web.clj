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
            [incanter.interpolation :as interp]  
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
                      (get-in @mdb/db [file bucket]))
        pointseries (if (options :rate)
                      (derivative pointseries)
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

(defroutes app-routes
  (GET "/files" [] (json-response (mdb/list-files)))
  (GET "/buckets" [] (json-response (mdb/list-buckets)))
  (GET "/stats" [] (json-response (mdb/list-stats)))
  (GET "/statdata" {{stats :stat} :params}
       (let [stats (delist stats)]
         (json-response (multistat-response stats))))
  (GET "/" [] {:status 302
               :headers {"location" "/index.html"}})
  (route/resources "/")
  (route/not-found "404!"))

(def handler
  (-> #'app-routes
      api
      wrap-stacktrace))

(defonce server (atom nil))

(defn start-server [{:keys [port]}]
  (reset! server (-> #'handler
                     wrap-ring-handler
                     (start-http-server {:port port})))
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

        (print (str "Loading files... 0/" numfiles))
        (flush)
        ;; Load the found .zips file into the memory DB in parallel
        (doseq [fut  
                (mapv (fn [f]
                        (future (mdb/load-collectinfo f :as (.getName f))
                                (print (str "\rLoading files... " 
                                            (swap! numloaded inc) "/" numfiles)) (flush)
                                (when (= numfiles @numloaded)
                                  (println "\nDone!"))))
                      files)]
          @fut)
        (start-server opts)))))

