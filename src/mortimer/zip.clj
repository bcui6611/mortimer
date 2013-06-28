(ns mortimer.zip
  (:import java.util.zip.ZipFile)
  (:require [clojure.java.io :as io]
            [clojure.string :as string]))


;; General ZIP utilities

(defn open [file]
  (ZipFile. (io/file file)))

(defn entries [zipfile]
  (enumeration-seq (.entries zipfile)))

(defn suffixed [zipfile suffix]
  (filter #(.endsWith (.getName %) suffix) (entries zipfile)))

(defn suffixed-1 [zipfile suffix] (first (suffixed zipfile suffix)))

(defn- zipslurp [zipfile entry]
  (slurp (.getInputStream zipfile entry)))

(defn consume [zipfile suffix]
  (some->> (suffixed-1 zipfile suffix)
           (zipslurp zipfile)))

(defn stream [zipfile suffix]
  (some->> (suffixed-1 zipfile suffix)
           (.getInputStream zipfile)))
