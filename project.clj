(defproject mortimer "0.1.0-SNAPSHOT"
  :description "Post-Mortem Log Analysis Tools for Couchbase"
  :main mortimer.web
  :plugins [[lein-marginalia "0.7.1"]]
  :dependencies [[org.clojure/clojure "1.5.1"]
                 [incanter/incanter-core "1.5.1"]
                 [aleph "0.3.0-rc1"]
                 [cheshire "5.2.0"]
                 [compojure "1.1.5"]
                 [ring/ring-devel "1.2.0-RC1"]
                 [org.clojure/tools.cli "0.2.2"]])
