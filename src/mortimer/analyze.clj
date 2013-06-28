(ns mortimer.analyze
  (:require [clojure.java.io :as io]
            [mortimer.zip :as zip]
            [clojure.string :as string]))

;; Collected info mangling

(defn ini-map-dumb [lines]
  (let [kvlines (keep (partial re-matches #"^(\w+)\s*=\s*(.*)$") lines)]
    (->> kvlines
         (map (comp vec rest))
         (into {}))))

(defn ini-log-chop [inilog-data]
  (let [lines (string/split-lines inilog-data)
        files (->> lines
                   (partition-by #(.startsWith % "File: "))
                   (drop 3)
                   (partition 2)
                   (map (comp #(update-in % [0] (fn [[s]] (subs s 8))) vec))
                   (into {}))]
    files))

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

(comment
  (use 'clojure.pprint)
  (def tdir "/Users/apage43/funs/")
  (def tfn (str tdir "cbse614.zip"))
  (def tz (open-zip tfn))
  (.close tz)

  (with-open [collectinfo (open-zip tfn)]
    (let [inilog-data (try-slurp collectinfo "/ini.log")
          chopped (ini-log-chop inilog-data)
          runtime (chopped "runtime.ini") ]
      (pprint (ini-map-dumb runtime))))

  )
