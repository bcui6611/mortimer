(ns mortimer.demangle
  "### Functions for parsing data out of text logs"
  (:import [java.util TimeZone]
           java.text.SimpleDateFormat)
  (:require [clojure.java.io :as io]
            [mortimer.debug :as d]
            [clj-time.format :as tformat]
            [clj-time.coerce :as tcoerce]))

(defn stats-kv
  "Takes \"statname value\" lines and returns a map, with
   the statname keywordized."
  [lines]
  (reduce (fn [acc line]
            (let [[_ k v] (re-matches #"([^\s]+)\s+(.*)" line)]
              (if (and k v)
                (assoc acc
                       (keyword k)
                       (if (re-matches #"[\-\d]+(.\d+)?" v)
                         (read-string v) v))
                acc)))
          {} lines))

(def statslogdateformat
  (tformat/formatter "yyyy-MM-dd'T'HH:mm:ss.SSS"))

(def oldstatslogdateformat
  (tformat/formatter "yyyy-MM-dd HH:mm:ss"))

(defn try-parse-20 [line]
  (if-let [[_ localts bucket]
           (re-matches
             #"^\[stats:debug,([^,]+),.*Stats for bucket \"(.*)\".*$" line)]
    [(-> (tformat/parse statslogdateformat localts)
         tcoerce/to-long (/ 1000))
     bucket]))

(defn try-parse-181 [line]
  (if-let [[_ localts bucket]
           (re-matches
             #"^\[stats:debug] \[([^\]]+)] .*Stats for bucket \"(.*)\".*$" line)]
    [(-> (tformat/parse oldstatslogdateformat localts)
         tcoerce/to-long (/ 1000))
     bucket]))

(defn try-parse [line]
  (or (try-parse-20 line)
      (try-parse-181 line)))

(defn stats-parse
  "Given an input stream over a log file, searches for `Stats for bucket \"bucketname\"`
   sections and parses them, returns a map of buckets to lists
   of collected stats samples."
  [input-stream]
  (with-open [reader (io/reader input-stream)]
    (loop [lines (line-seq reader)
           stats {}]
      (if-let [line (first lines)]
        (if-let [[localtime bucket] (try-parse line)]
          (let [statlines (take-while (complement empty?) (rest lines))]
            (recur
              (drop (count statlines) lines)
              (update-in stats [bucket]
                         #(conj (or % [])
                                (assoc (stats-kv statlines)
                                       :localtime localtime)))))
          (recur (rest lines) stats))
        stats))))

(def diaglogdateformat
  (tformat/formatter "yyyy-MM-dd HH:mm:ss.SSS"))

(defn parse-diag-log-date [s]
  (tformat/parse diaglogdateformat s))

;; A list of [regex function] pairs.
;;
;; Each line in `diag.log` is tested against each regex.  If it matches, the
;; groups will be passed to the accompanying function to generate an event.
(def diag-events
  [[#"^([^ ]+ [^ ]+) ([^: ]+)[^ ]+ - Starting rebalance.*$"
    (fn [groups]
      (let [[_ timestamp _module] groups]
        {:category :rebalance
         :icon "icon-truck"
         :timestamp (parse-diag-log-date timestamp)
         :label "Rebalance Started"}))]
   [#"^([^ ]+ [^ ]+) ([^: ]+)[^ ]+ - Rebalance ([^ ]+).*$"
    (fn [groups]
      (let [[_ timestamp _module stopword] groups
            reason (case stopword
                     "completed" :success
                     "stopped" :canceled
                     "exited" :error
                     :unknown)]
        {:category :rebalance
         :timestamp (parse-diag-log-date timestamp)
         :icon "icon-stop"
         :label (str "Rebalance Ended (" (name reason) ")")
         :reason reason}))]])

(defn diag-parse
  "Find events in the diag.log log"
  [input-stream]
  (with-open [reader (io/reader input-stream)]
    (reduce
      (fn [events line]
        (into events
              (keep (fn [[re fun]]
                      (when-let [groups (re-matches re line)]
                        (try (fun groups)
                             (catch Exception e nil))))
                    diag-events)))
      [] (line-seq reader))))
