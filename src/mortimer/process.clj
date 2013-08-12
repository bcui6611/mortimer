(ns mortimer.process
  "### Data processing and expression evaluation"
  (:use clojure.pprint)
  (:require [instaparse.core :as insta]
            [instaparse.failure :as instafail]
            [clojure.java.io :as io]
            [clojure.string :as s]
            [incanter.optimize :as opt]
            [incanter.interpolation :as interp]
            [mortimer.debug :as dbg]
            [mortimer.data :as mdb]))

;; Create a parser from resources/expr.g
(def parse-expr (-> "expr.g" io/resource slurp insta/parser))

(def ^:dynamic *messages* nil)

(defn add-warning [warning & [extra]]
  (when *messages*
    (swap! *messages* conj
           {:kind :warning
            :short warning
            :extra extra})))

(defn moving-average [pointseries window]
  (let [vecseries (vec pointseries)] ; make sure we have fast random access
    (for [n (range 0 (count pointseries))]
      (let [samples (map second (map #(nth vecseries % nil) (range (- n window) (+ n window 1))))
            orig (nth vecseries n)
            [t _] orig]
        (if (or (some nil? samples) (nil? (nth vecseries (- n window 1) nil))) 
          [t nil]
          [t (/ (apply + samples) (count samples))])))))

(defn derivative [pointseries & interpargs]
  (cond 
    (empty? pointseries) []
    :else (let [interpargs (or interpargs [:linear])
                derivseries (filter (complement (comp nil? second)) pointseries)
                interped (apply interp/interpolate derivseries interpargs)
                derif (opt/derivative interped)]
            (for [[t v] pointseries]
              [t (derif (+ t 1/2))]))))

(defn series-by-name
  [seriesname context]
  (let [result (let [{:keys [file bucket]} context] 
    (mdb/extract (keyword seriesname)
                 (get-in @mdb/stats [file bucket])))]
    (when (empty? result)
      (add-warning (str "Expression references empty or unknown stat '" seriesname "'"))) 
    result))

(def expr-fun-table
  {:rate (fn [{:keys [smoothing-window]
               :or {smoothing-window 0}
               :as context}
              series] 
           (let [uprate
                 (-> (series-by-name "uptime" context)
                     (moving-average smoothing-window)
                     (derivative))]
             (-> series
                 (moving-average smoothing-window)
                 (derivative)
                 (->> (map (fn [[ut uv] [dt dv]]
                             (if-not (neg? uv) [dt dv] [dt nil]))
                           uprate)))))})

(def oper-fun-table {"+" + "-" - "*" * "/" /})

(defn apply-operator-series
  "Apply operator to two series (two series must be from the same bucket/file!)"
  [op argA argB]
  (map (fn [[t1 v1] [t2 v2]]
         [(or t1 t2) (op v1 v2)])
       argA argB))

(defn apply-operator
  [opname argA argB]
  (if-let [op (oper-fun-table opname)]
    (cond
      (and (number? argA) (number? argB)) (op argA argB)

      (and (coll? argA) (coll? argB)) (apply-operator-series op argA argB)

      (and (number? argA) (coll? argB)) (apply-operator-series op
                                          (repeat [nil argA])
                                          argB)
      (and (coll? argA) (number? argB)) (apply-operator-series op
                                          argA
                                          (repeat [nil argB]))

      :else (throw (ex-info (str "can't " opname " args of types "
                                 (pr-str (map type [argA argB]))) 
                            {:types (map type [argA argB])})))
    (throw (ex-info (str opname " is not a valid operator") {}))))


(defn expr-evaluate
  [expr-tree context]
  (let [[root-type & more] expr-tree]
    (case root-type
      :expr (expr-evaluate (first more) context)
      :identifier (series-by-name (first more) context)
      :number (read-string (first more))
      :operator_call
      (let [[expA [_ opname] expB] more
            argA (expr-evaluate expA context)
            argB (expr-evaluate expB context)]
        (apply-operator opname argA argB))
      :funcall (let [fname (second (first more))
                     args (map #(expr-evaluate % context) (rest more))]
                 (if-let [fun (expr-fun-table (keyword fname))]
                   (apply fun context args)
                   (throw (ex-info (str "Unknown function " fname) 
                                   {:ast expr-tree}))))
      (throw (ex-info (str "Don't know how to eval " root-type)
                      {:ast expr-tree})))))

(defn expr-eval-string
  [expr-string context]
  (let [parsed (parse-expr (s/trim expr-string))]
    (dbg/debug "Eval" expr-string "ctx" (pr-str context))
    (when (insta/failure? parsed)
      (throw (ex-info (str "Expression Parse Failure") 
                      {:extra (with-out-str (instafail/pprint-failure parsed))})))
    (expr-evaluate parsed context)))

(comment
  (defn test-expr [expr context]
    (let [parsed (parse-expr expr)]
      (pprint parsed)
      (expr-evaluate parsed context)))
  (test-expr "cmd_get" {})
  (test-expr "9 + 9" {})
  (test-expr "rate(cmd_get)" {})
  )

