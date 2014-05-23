# mortimer

[![Build Status](https://drone.io/github.com/couchbaselabs/mortimer/status.png)](https://drone.io/github.com/couchbaselabs/mortimer/latest)

Currently I can

 * Read ep\_engine stat information from `ns_server.stats.log` in `cbcollect_info` zip files (2.0+)
 * Graph those on a Web UI

TODOs: [see tag `mortimer` on cbugg][cbg]

File feature requests and bugs on
[cbugg](http://cbugg.hq.couchbase.com/), and tag them `mortimer`

[cbg]: http://cbugg.hq.couchbase.com/search/tags:mortimer%20AND%20status:(inbox%20OR%20new%20OR%20open%20OR%20inprogress)

Download the .jar at <http://s3.amazonaws.com/cb-support/mortimer-build/mortimer.jar>

To run from a git checkout, install [Leiningen][lein]. Now any
`java -jar ~/path/to/mortimer.jar` command below can be replaced with
typing `lein run --` in the checkout
directory:

    lein run -- -d /my/directory/of/zips

[lein]: https://github.com/technomancy/leiningen

# How to Use

## Starting mortimer

Mortimer is a JVM application. Download the .jar, and place it in a
well known location.

To run it, type

    java -jar ~/path/to/mortimer.jar

By default, the current working directory will be searched for
`cbcollect_info` ZIP files, and the mortimer web UI will be started on
port 18334.

Each of these can be changed with command line flags.

    Usage:

      Switches                   Default  Desc
      --------                   -------  ----
      -p, --port                 18334    Start webserver on this port
      -d, --dir                  .        Directory to search for collectinfo .zips
      -v, --no-debug, --debug    false    Enable debugging messages
      -u, --no-update, --update  true     Check for updates
      -n, --no-browse, --browse  true     Auto open browser
      -h, --no-help, --help      false    Display help   

If loading files is slow (or you get an `OutOfMemoryError` exception),
try giving the JVM more RAM:

    java -Xmx2g -jar ~/path/to/mortimer.jar

Adding the option `-Djava.awt.headless=true` to the `java` command line
to prevent java from unecessarily adding an icon to your OSX dock.

    java -Djava.awt.headless=true -jar ~/path/to/mortimer.jar

It can be useful to keep mortimer in a well known location and create a
shell alias to launch it:

    wget -O ~/mortimer.jar http://s3.crate.im/mortimer-build/mortimer.jar

And in your `.bashrc` or equivalent:

    alias mortimer='java -Djava.awt.headless=true -jar ~/mortimer.jar'

## Keyboard Shortcuts

* `/` - focus search field, opening drawer if closed
* `ds` - clear current search
* `j`, `k` - choose next/previous series
* `cmd+j`, `cmd+k` - choose next/previous file
* `shift+j`, `shift+k` - choose next/previous bucket
* `enter` - chart series at cursor
* `cmd+enter` - add series at cursor to chart
* `r` - chart rate of series at cursor
* `cmd+r` - add rate of series under at to chart
* `>`, `<` - open or close drawer
* `q` - toggle multi-window sync push from this window
* `gg` - move cursor to top of series list
* `p` - increase smoothing of rates
* `o` - decrease smoothing of rates
* `` ` `` - add a series using a series expression
* `?` - display this README

## Expressions

You can hit the backtick key to enter an *expression* to add to the
charting area.

### Examples

Plot a single series:

    cmd_get

Plot the rate of a single series:

    rate(cmd_get)

Or the second derivative:

    rate(rate(cmd_get))

Plot the sum of two series:

    cmd_get + cmd_set

Memory remaining before reaching 90% of `ep_max_data_size`:

    (ep_max_data_size * 0.9) - mem_used

**NOTE**: Order-of-operations is currently *not* followed. If
you use `-` or `/`, you should use parentheses to indicate 
the intended order of evaluation.

## Charting series

Click the name of the series you want to chart, and that series will be
plotted in the chart area.

You can click and drag on the chart to zoom in, hold Shift to pan, and
double click to reset the zoom level.

You can click "rate" next to a series to plot its rate of change.

## Showing multiple lines

You can hold down the Command or Control keys while clicking on series to
add multiple series to the chart.

You can compare a series across files or buckets by clicking a series,
selecting a new file or bucket, and Command/Control clicking the series
again.

## Presets

Mortimer comes with preset combinations of series selections that are
commonly useful.

You can also *save* your current selection of series as a preset using the
Save Preset button.

## Setting Markers

You can hold Command or Control and click on the chart, to place a
marker.

Markers will stay on the chart while selecting different series, allowing
you to keep track of significant points in time as you explore data.

You can hold Shift and click on a marker to delete it.

