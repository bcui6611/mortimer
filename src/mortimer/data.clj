(ns mortimer.data
  (:require [mortimer.analyze :as aly]
            [mortimer.zip :as zip]
            [incanter.interpolation :as interp]
            [incanter.charts :as charts]))

(def db (atom {}))

(defn list-files []
  (keys @db))

(defn list-buckets []
  (or (mapcat keys (vals @db)) []))

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

(defn combined [statname statsets]
  (let [pointsets (map (fn [sset]
                         (map (juxt :time #(get % statname)) sset))
                       statsets)
        interped (map interpolate-stat pointsets)
        [mintime maxtime] (apply (juxt min max) (mapcat (partial map first) pointsets))
        combined (fn [t] (apply + (map #(% t) interped)))]
    {:interval [mintime maxtime]
     :stat statname
     :func combined}))

(defn stat-plot [combf]
  (let [{f :func [mint maxt] :interval} combf
        xs (range mint (inc maxt))
        ys (map f xs)]
    (charts/time-series-plot
      (map (partial * 1000) xs) ys
      :x-label "Time"
      :y-label (-> combf :stat name))))

(defn across [files buckets]
  (let [files (if (= files :all) (list-files) files)
        buckets (if (= buckets :all) (list-buckets) buckets)]
    (remove nil? (for [b buckets
                       f files]
                   (get-in @db [f b])))))
