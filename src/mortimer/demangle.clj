(ns mortimer.demangle
  "### Functions for parsing data out of text logs"
  (:import [java.util TimeZone]
           java.text.SimpleDateFormat)
  (:require [clojure.java.io :as io]))

(defn stats-kv
  "Takes \"statname value\" lines and returns a map, with
   the statname keywordized."
  [lines]
  (reduce (fn [acc line]
            (let [[_ k v] (re-matches #"([^\s]+)\s+(.*)" line)]
              (if (and k v)
                (assoc acc 
                       (keyword k) 
                       (if (re-matches #"[\-\d.]+" v)
                         (read-string v) v))
                acc)))
          {} lines))

(defn stats-parse
  "Given an input stream over a log file, searches for `Stats for bucket \"bucketname\"`
   sections and parses them, returns a map of buckets to lists
   of collected stats samples."
  [input-stream]
  (with-open [reader (io/reader input-stream)]
      (loop [lines (line-seq reader)
             stats {}]
        (if-let [line (first lines)]
          (if-let [[_ bucket] (re-matches #"^.*Stats for bucket \"(.*)\".*$" line)]
            (let [statlines (take-while (complement empty?) (rest lines))]
               (recur 
                 (drop (count statlines) lines)
                 (update-in stats [bucket]
                            #(conj (or % [])
                                   (stats-kv statlines)))))
            (recur (rest lines) stats))
          stats))))

(def logdateformat
  (doto
    (SimpleDateFormat. "yyyy-MM-dd HH:mm:ss.SSS")
    (.setTimeZone (TimeZone/getTimeZone "UTC"))))

(defn parse-log-date [s]
  (.parse logdateformat s))

;; A list of [regex function] pairs.
;;
;; Each line in `diag.log` is tested against each regex.  If it matches, the
;; groups will be passed to the accompanying function to generate an event.
(def diag-events
  [[#"^([^ ]+ [^ ]+) ([^: ]+)[^ ]+ - Starting rebalance.*$"
    (fn [groups]
      (let [[_ timestamp _module] groups]
        {:category :rebalance
         :timestamp (parse-log-date timestamp)
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
         :timestamp (parse-log-date timestamp)
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
                        (fun groups)))
                    diag-events)))
      [] (line-seq reader))))
