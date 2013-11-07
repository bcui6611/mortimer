(defproject mortimer "0.1.0-SNAPSHOT"
  :description "Post-Mortem Log Analysis Tools for Couchbase"
  :main ^:skip-aot mortimer.web
  :plugins [[lein-marginalia "0.7.1"]
            [org.timmc/lein-otf "2.0.1"]]
  :jvm-opts ["-Xmx4g"]
  :dependencies [[org.clojure/clojure "1.5.1"]
                 [org.clojure/core.memoize "0.5.6"]
                 [org.codehaus.jsr166-mirror/jsr166y "1.7.0"]
                 [incanter/incanter-core "1.5.1"]
                 [instaparse "1.2.2"]
                 [aleph "0.3.0-rc1"]
                 [cheshire "5.2.0"]
                 [clj-time "0.5.1"]
                 [clj-http "0.7.3"]
                 [commons-io "2.4"]
                 [compojure "1.1.5"]
                 [me.raynes/conch "0.5.0"]
                 [ring/ring-devel "1.2.0-RC1"]
                 [org.clojure/tools.cli "0.2.2"]])
