(ns mortimer.zip
  "### Functions for working with .ZIP files"
  (:import java.util.zip.ZipFile)
  (:require [clojure.java.io :as io]))

(defn open 
  "Open a ZIP file"
  [file]
  (ZipFile. (io/file file)))

(defn entries 
  "Get the list of entries in a ZIP file"
  [zipfile]
  (enumeration-seq (.entries zipfile)))

(defn suffixed 
  "Get all entries in a zipfile with names ending with `suffix`"
  [zipfile suffix]
  (filter #(.endsWith (.getName %) suffix) (entries zipfile)))

(defn suffixed-1 
  "Get an entry from the zip file with a name ending with `suffix`"
  [zipfile suffix] (first (suffixed zipfile suffix)))

(defn stream 
  "Get an InputStream from the zip file of an entry with a name ending with `suffix`"
  [zipfile suffix]
  (some->> (suffixed-1 zipfile suffix)
           (.getInputStream zipfile)))
