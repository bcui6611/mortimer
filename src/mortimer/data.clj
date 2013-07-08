(ns mortimer.data
  "### The in-memory stats database"
  (:import org.apache.commons.io.input.CountingInputStream)
  (:require [mortimer.demangle :as demangle]
            [cheshire.generate :as json-enc]
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
(defonce stats (atom {}))

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
    (swap! progress assoc id
           {:endsize endsize
            :counted counted})
    counted))

(json-enc/add-encoder 
  CountingInputStream
  (fn [c gen]
    (json-enc/encode-long (.getByteCount c) gen)))

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
            diagstream (some->> (zip/suffixed-1 zf "/diag.log")
                                (.getInputStream zf))
            counted (watched-stream as zf statfile)]
        (try
          (when-not diagstream
            (println "No diag.log found in file" as))
          (when diagstream 
            (swap! events merge {as (demangle/diag-parse diagstream)}))
          (swap! stats merge {as (demangle/stats-parse counted)})
          (finally (swap! progress dissoc as)
                   (notice-progress-watchers)))
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
