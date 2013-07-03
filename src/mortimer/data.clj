(ns mortimer.data
  "### The in-memory stats database"
  (:require [mortimer.demangle :as demangle]
            [mortimer.zip :as zip]
            [mortimer.interval :as iv]
            [incanter.interpolation :as interp]))

;; This atom holds all the data we've loaded
;; It's a big map:
;; 
;;     {"filename"
;;      {"bucketname" 
;;       [{:stat val :stat2 val}
;;        {:stat val :stat2 val}]}}
;;
;; defonce here so that when I'm working on this interactively, reloading the
;; file doesn't clear the db
(defonce db (atom {}))

(defn list-files []
  (keys @db))

(defn list-buckets []
  (distinct (or (mapcat keys (vals @db)) [])))

(defn list-stats []
  ;; find only stats that are numbers
  (->> (map first (mapcat vals (vals @db)))
       (map #(filter (comp number? val) %))
       (mapcat keys)
       distinct sort))

(defn load-collectinfo
  "Loads stats data from a collectinfo .ZIP

   Looks for `ns_server.stats.log` or `ns_server.debug.log` in the zip file.

   `(load-collectinfo filename)` or
   `(load-collectinfo filename :as \"nodename\")`"
  [zipfile & options]
  (let [{:keys [as]} (apply hash-map options)
        as (or as zipfile)]
    (with-open [zf (zip/open zipfile)]
      (let [statfile
            (or (zip/suffixed-1 zf "/ns_server.stats.log")
                (zip/suffixed-1 zf "/ns_server.debug.log")
                (throw (ex-info "Couldn't find stats file" {:zipfile zipfile})))
            instream (.getInputStream zf statfile)
            stat-data (demangle/stats-parse instream)]
        (swap! db merge {as stat-data})
        :ok))))

(defn extract [stat statset]
  (let [ov (transient [])]
    (reduce (fn [acc statsnap]
              (let [t (:time statsnap)
                    v (get statsnap stat)]
                (if (and t v)
                  (conj! acc [t v])
                  acc))) ov statset)
    (persistent! ov)))
