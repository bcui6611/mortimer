# mortimer

[![Build Status](https://drone.io/github.com/couchbaselabs/mortimer/status.png)](https://drone.io/github.com/couchbaselabs/mortimer/latest)

Currently I can

 * Read ep\_engine stat information from `ns_server.stats.log` in `cb_collectinfo` zip files (2.0+)
 * Graph those on a Web UI

TODOs: [see tag `mortimer` on cbugg][cbg]

File feature requests and bugs on
[cbugg](http://cbugg.hq.couchbase.com/), and tag them `mortimer`

[cbg]: http://cbugg.hq.couchbase.com/search/tags:mortimer%20AND%20status:(inbox%20OR%20new%20OR%20open%20OR%20inprogress)

Download the .jar at <http://s3.crate.im/mortimer-build/mortimer.jar>

Documented source code at <http://s3.crate.im/mortimer-build/mortimer-doc.html>

## Usage

```
$ java -jar mortimer.jar -h
Usage:

 Switches               Default  Desc
 --------               -------  ----
 -p, --port             18334    Start webserver on this port
 -d, --dir              .        Directory to search for collectinfo .zips
 -h, --no-help, --help  false    Display help

$ java -jar mortimer.jar -d ~/dir/of/infos
Listening on http://localhost:18334/
Loading #<File /Users/apage43/fun/node-0.zip>
Loaded #<File /Users/apage43/fun/node-0.zip>
Loading #<File /Users/apage43/fun/node-1.zip>
Loaded #<File /Users/apage43/fun/node-1.zip>
```
