(ns mortimer.data
  "### The in-memory stats database"
  (:import org.apache.commons.io.input.CountingInputStream)
  (:require [mortimer.demangle :as demangle]
            [clojure.core.reducers :as r]
            [clj-time.core :as ttime]
            [clj-time.coerce :as tcoerce]
            [cheshire.generate :as json-enc]
            [mortimer.zip :as zip]
            [mortimer.debug :as d]
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
(defonce stats (atom {}))
(defonce timefns (atom {}))

;; Similar, but events (so far) aren't grouped by bucket.
(defonce events (atom {}))

(defn list-files []
  (sort (keys @stats)))

(defn list-buckets []
  (sort (distinct (or (mapcat keys (vals @stats)) []))))

(defn list-stats []
  ;; find only stats that are numbers
  (->> (map first (mapcat vals (vals @stats)))
       (map #(filter (comp number? val) %))
       (mapcat keys)
       distinct sort))

(defonce progress (atom {}))
(defonce progress-watchers (atom #{}))

(defn watched-stream [id zipfile entry]
  (let [endsize (.getSize entry)
        instream (.getInputStream zipfile entry)
        counted (CountingInputStream. instream)]
    (swap! progress 
           (fn [progmap]
             (merge-with (fn [orig update]
                           {:endsize (+ (:endsize orig) (:endsize update))
                            :counted (concat (:counted orig) (:counted update))})
                         progmap
                         {id 
                          {:endsize endsize
                           :counted [counted]}})))
    counted))

(json-enc/add-encoder 
  CountingInputStream
  (fn [c gen]
    (json-enc/encode-long (.getByteCount c) gen)))

(json-enc/add-encoder
  org.joda.time.DateTime
  json-enc/encode-str)

(defn notice-progress-watchers []
  (doseq [w @progress-watchers]
    (w)))  

(defn progress-updater-start []
  (.start 
    (Thread. 
      (fn []
        (let [ids (keys @progress)] 
          (when (seq ids) 
            (notice-progress-watchers)))
        (Thread/sleep 100)
        (recur)))))

(defn localtime-index [file]
  (let [allstats (r/mapcat val (get @stats file))
        diffs (r/map (juxt :localtime :time) allstats)
        lookup (into (sorted-map) diffs)]
    (fn [localtime]
      (if-let [[local utc] (first (subseq lookup >= localtime))]
        utc 0))))

(defn remap-event [file event]
  (let [differ (@timefns file)]
    (update-in event [:timestamp]
               (fn [t]
                 (let [tsecs (/ (tcoerce/to-long t) 1000)]
                   (tcoerce/from-long (* (differ tsecs) 1000)))))))

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
            diag-counted (when (:diag options)
                           (some->> (zip/suffixed-1 zf "/diag.log")
                                    (watched-stream as zf)))
            stats-counted (watched-stream as zf statfile)]
        (try
          (when-not diag-counted
            (println "No diag.log found in file" as))
          (when diag-counted
            (swap! events assoc as (demangle/diag-parse diag-counted)))
          (d/debug "Parsing stats from" statfile "in" zipfile)
          (swap! stats assoc as (demangle/stats-parse stats-counted))
          (when diag-counted
            (swap! timefns assoc as (localtime-index as)))
          (finally (swap! progress dissoc as :stats)
                   (notice-progress-watchers)))
        :ok))))

(defn get-events [file]
  (mapv (partial remap-event file) (get @events file)))

(defn extract [stat statset]
  (let [ov (transient [])]
    (reduce (fn [acc statsnap]
              (let [t (:time statsnap)
                    v (get statsnap stat)]
                (if (and t v)
                  (conj! acc [t v])
                  acc))) ov statset)
    (persistent! ov)))
