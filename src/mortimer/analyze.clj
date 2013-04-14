(ns mortimer.analyze
  (:import java.util.zip.ZipFile)
  (:require [clojure.java.io :as io]
            [clojure.string :as string]))

(def test-201-dir "/Users/apage43/dex/couchbase_test_results/201s")
(def test-201-fil "/Users/apage43/dex/couchbase_test_results/201s/cbcollect_info.2.0.1.node1.zip")

;; General ZIP utilities

(defn open-zip [file]
  (ZipFile. (io/file file)))

(defn zip-entries [zipfile]
  (enumeration-seq (.entries zipfile)))

(defn suffixed [zipfile suffix]
  (filter #(.endsWith (.getName %) suffix) (zip-entries zipfile)))

(defn suffixed-1 [zipfile suffix] (first (suffixed zipfile suffix)))

(defn zipslurp [zipfile entry]
  (slurp (.getInputStream zipfile entry)))

(defn try-slurp [zipfile suffix]
  (some->> (suffixed-1 zipfile suffix)
           (zipslurp zipfile)))

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

(comment
  (use 'clojure.pprint)

  (with-open [collectinfo (open-zip test-201-fil)]
    (let [inilog-data (try-slurp collectinfo "/ini.log")
          chopped (ini-log-chop inilog-data)
          runtime (chopped "runtime.ini") ]
      (pprint (ini-map-dumb runtime))))

  )
