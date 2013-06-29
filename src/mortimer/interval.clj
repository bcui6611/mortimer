(ns mortimer.interval
  "### Intervals")

(defn- intersect-1
  "Intersect two intervals"
  [[a b] [c d]] 
  [(max a c) (min b d)])

(defn intersect
  "Intersect a list of intervals"
  [is] (reduce intersect-1 is))
