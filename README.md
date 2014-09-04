# mortimer

Currently I can:-

 * Read ep\_engine stat information from `ns_server.stats.log` in `cbcollect_info` zip files (2.0+)
 * Graph those on a Web UI

The following additions/improvements have been made over the original clojure implementation:-

 * Shows graph with the date/time in the logs
 * When place cursor over stat name provide stats description.
 
Mortimer requires either `pypy` or `python 2.7.x` to be installed.  In addition the following two python modules are required:-
 
 1. `tornado` - provides web server and web socket functionality
 2. `lepl` - provides grammar parsing functionality.
 
For best performance it is recommended to install `pypy`.  See [pypy.org](http://pypy.org) for more details.  You will also need to install pypy versions of the tornado and lepl modules.  This can be achieved using `pip_pypy` or the pypy version of `easy_install`.  The install instructions for Mac (OSX) are:-
 
	/usr/local/share/pypy/easy_install tornado
	/usr/local/share/pypy/easy_install lepl

If you decide not to use pypy, then python 2.7.x can be used.  On Mac (OSX) the two extra modules can be installed as follows:-
 
    /usr/bin/easy_install tornado
	/usr/bin/easy_install lepl
	
# How to Use

## Starting mortimer

To run mortimer, simply type:-

    ./mortimer.sh
    
If pypy is installed, mortimer will automatically use it, otherwise it will default to use the standard python intepreter.    

By default, the current working directory will be searched for
`cbcollect_info` ZIP files, and the mortimer web UI will be started on
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
      -e, --events               Read various node events from many places.
      --erlang                   Read erlang stats from ns_server.stats
      --version                  Prints out the version number of mortimer

### --erlang (XDCR stats)

Note: This flag will slow down mortimer loading as there's a lot of data to process.

The --erlang flag enables the loading of ns_doctor statistics which contain many useful items. Primarily latency data for XDCR.

If the node logs do have XDCR enabled a new bucket will be created (look for buckets with an xdcr_ prefix). You can use these "buckets" to look at XDCR
statistics.

The following statistic exist (as of 2.5.1). Unfortunately the details behind these stats may need some erlang decryption.

* changes_left
* docs_checked
* docs_written
* docs_opt_repd
* data_replicated
* active_vbreps
* waiting_vbreps
* time_working
* time_committing
* num_checkpoints
* num_failedckpts
* docs_rep_queue
* size_rep_queue
* rate_replication
* bandwidth_usage
* meta_latency_aggr
* meta_latency_wt
* docs_latency_aggr
* docs_latency_wt


### -e, --events

The -e, --events flag enables the loading of various node events, e.g. when memcached logs "Too many open connections", this becomes a statistic which can be graphed with other stats.

See mortimer/node_events.py for the dictionary which drives which files and events are looked at and what keys they are added as.


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
