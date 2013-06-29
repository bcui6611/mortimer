(ns mortimer.data
  (:require [mortimer.analyze :as aly]
            [mortimer.zip :as zip]
            [mortimer.interval :as iv]
            [incanter.interpolation :as interp]))

;; This atom holds all the data we've loaded
;; It's a big map:
;; {"filename"
;;  {"bucketname" 
;;   [{:stat val :stat2 val}
;;    {:stat val :stat2 val}]}}
(def db (atom {}))

(defn list-files []
  (keys @db))

(defn list-buckets []
  (distinct (or (mapcat keys (vals @db)) [])))

;; find only stats that are numbers
(defn list-stats []
  (->> (map first (mapcat vals (vals @db)))
       (map #(filter (comp number? val) %))
       (mapcat keys)
       distinct sort))

(defn load-collectinfo
  "(load-collectinfo filename) or
   (load-collectinfo filename :as \"nodename\")"
  [zipfile & options]
  (let [{:keys [as]} (apply hash-map options)
        as (or as zipfile)]
    (with-open [zf (zip/open zipfile)]
      (let [statfile
            (or (zip/suffixed-1 zf "/ns_server.stats.log")
                (zip/suffixed-1 zf "/ns_server.debug.log")
                (throw (ex-info "Couldn't find stats file" {:zipfile zipfile})))
            instream (.getInputStream zf statfile)
            stat-data (aly/stats-parse instream)]
        (swap! db merge {as stat-data})
        :ok))))

(defn interpolate-stat
  "Fill in [seconds datum] pairs in messy data.
   can optionally supply args for incanter.interpolation/interpolate.
   
   Returns a function of time. ((interpolate-stat-data points) time)"
  [points & interpargs]
  (let [args (or interpargs [:linear])
        statf (apply interp/interpolate points args)]
    statf))

(defn combined 
  "Create a function that adds and interpolates statname within statsets"
  [statname statsets]
  (let [pointsets (map (fn [sset]
                         (map (juxt :time #(get % statname)) sset))
                       statsets)
        interped (map interpolate-stat pointsets)
        [mintime maxtime]
        (iv/intersect
          (for [ps pointsets]
            (apply (juxt min max)
                   (map first ps))))
        combined (fn [t] (apply + (map #(% t) interped)))]
    {:interval [mintime maxtime]
     :stat statname
     :func combined}))

(defn across [files buckets]
  (let [files (if (= files :all) (list-files) files)
        buckets (if (= buckets :all) (list-buckets) buckets)]
    (remove nil? (for [b buckets
                       f files]
                   (get-in @db [f b])))))
