(ns mortimer.analyze
  (:require [clojure.java.io :as io]
            [mortimer.zip :as zip]
            [clojure.string :as string]))

;; Collected info mangling

(defn stats-kv [lines]
  (into {} (for [line lines]
             (let [[_ k v] (re-matches #"([^\s]+)\s+(.*)" line)]
               [(keyword k) 
                (if (re-matches #"[\-\d.]+" v)
                  (read-string v) v)]))))

(defn stats-parse [input-stream]
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
