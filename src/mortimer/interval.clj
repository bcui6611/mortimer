(ns mortimer.interval)

(defn intersect-1 [[a b] [c d]] [(max a c) (min b d)])

(defn intersect [is]
  (reduce intersect-1 is))
