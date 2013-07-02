(ns mortimer.demangle
  "### Functions for parsing data out of text logs"
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
