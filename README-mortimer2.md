# mortimer2

Mortimer2 is a port of the original mortimer, replacing the backend written in clojure with one written in python.  The motivation for doing this was to enable Support to more easily modify and add features.     

It currently has all the existing features of the original mortimer, see below:-

 * Read ep\_engine stat information from `ns_server.stats.log` in `cbcollect_info` zip files (2.0+)
 * Graph those on a Web UI

Plus the following additions/improvements:-

 * Shows graph with the date/time in the logs
 * When place cursor over stat name provide stats description.
 
Each time mortimer2 is started the stat descriptions are automatically downloaded from the [ep-engine](http://raw.githubusercontent.com/membase/ep-engine/master/docs/stats.org) repository.  Therefore mortimer2 requires a working external internet connection.
 
Mortimer2 requires either `pypy` or `python 2.7.x` to be installed.  In addition the following two python modules are required:-
 
 1. `tornado` - provides web server and web socket functionality
 2. `lepl` - provides grammar parsing functionality.
 
For best performance it is recommended to install `pypy`.  See [pypy.org](http://pypy.org) for more details.  You will also need to install pypy versions of the tornado and lepl modules.  This can be achieved using `easy_install`.  The install instructions for Mac (OSX) are:-
 
	/usr/local/share/pypy/easy_install tornado
	/usr/local/share/pypy/easy_install lepl

If you decide not to use pypy, then python 2.7.x can be used.  On Mac (OSX) the extra two modules can be installed as follows:-
 
    /usr/bin/easy_install tornado
	/usr/bin/easy_install lepl
	
# How to Use

## Starting mortimer2

To run mortimer2, simply type:-

    ./mortimer2
    
If pypy is installed, mortimer2 will automatically use it, otherwise it will default to use the standard python intepreter.    

By default, the current working directory will be searched for
`cbcollect_info` ZIP files, and the mortimer2 web UI will be started on
port 18334.

Each of these can be changed with command line flags.

    Usage:

      Switches                   Default  Desc
      --------                   -------  ----
      -h, --help                 no-help  show this help message and exit
      -p, --port                 18334    Start webserver on this port
      -d, --dir                  .        Directory to search for collectinfo .zips
      -v, --debug                false    Enable debugging messages
      -n, --browse               true     Auto open browser


## Keyboard Shortcuts

* `/` - focus search field, opening drawer if closed
* `ds` - clear current search
* `j`, `k` - choose next/previous series
* `cmd+j`, `cmd+k` - choose next/previous file
* `shift+j`, `shift+k` - choose next/previous bucket
* `enter` - chart series at cursor
* `cmd+enter` - add series at cursor to chart
* `r` - chart rate of series at cursor
* `ctrl+r` - add rate of series under at to chart
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

Mortimer2 comes with preset combinations of series selections that are
commonly useful.

You can also *save* your current selection of series as a preset using the
Save Preset button.

## Setting Markers

You can hold Command or Control and click on the chart, to place a
marker.

Markers will stay on the chart while selecting different series, allowing
you to keep track of significant points in time as you explore data.

You can hold Shift and click on a marker to delete it.
