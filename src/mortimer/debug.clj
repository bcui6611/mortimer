(ns mortimer.debug
  (:use clojure.pprint))

(def ^:dynamic *debug* false)

(defn debug [& args]
  (when *debug* (apply println args)))

(defmacro trace [message & expr]
  `(let [res# ~expr]
     (when *debug* 
       (println message)
       (pprint res#)) 
     res#))
