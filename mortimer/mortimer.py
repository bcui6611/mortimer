#!/usr/bin/env python2.7
# -*- mode: Python;-*-

#from __future__ import unicode_literals, print_function
import zipfile
import inspect
import os.path
import re
import argparse
import logging
import threading
import webbrowser
import signal
import time
import datetime
import calendar
import string
import sys
import erlangParser
import multiprocessing

from Queue import Full

from os import _exit
from os import walk
from io import TextIOWrapper

import cProfile, pstats, StringIO

import globals
import grammar
import web_server
import node_events

""" This is the top level file for running Mortimer2.  It is responsible for loading the data
    and starting the the web server.  The program relies on three other python files:-
    1) globals.py - contains the globals variables used by mortimer
    2) grammar.py - contains functionality for parsing user query and providing back the data
    3) web_server.py - contains functionality for running the web server. 
    
    Mortimer2 can be running using either python2.7 or pypy.  It requires two additional
    modules to be installed:-
    1) tornado - provides web server functionality (including web socket support)
    2) lepl - provides grammar parsing functionality. """

def argumentParsing():
    parser = argparse.ArgumentParser(description='Mortimer2')
    parser.add_argument(
        '-p', '--port', type=int, default=18334, help='Start webserver on this port')
    parser.add_argument(
        '-d', '--dir', default='.', help='Directory to search for collectinfo .zips')
    parser.add_argument('-v', '--debug', action='store_true',
                        default=False, help='Enable debugging messages')
    parser.add_argument(
        '-n', '--browse', action='store_false', default=True, help='Auto open browser')
    parser.add_argument('-e', '--events', action='store_true',
                        default=False, help='Load node events/errors (warning can slow down loading time)')
    parser.add_argument('--version',  action='store_true',
                        default=False, help='Prints out the version number of mortimer')

    parser.add_argument('--erlang',  action='store_true',
                        default=False, help='Load erlang stats (including XDCR), can slow down loading time.')

    return parser.parse_args()


def num(s):
    """ Simple function for converting a string to an int or float.
        It is used by the stats_kv function (see below). """
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            print('Error num is not an int or float, see num(s). s = ' + s)
            os._exit(1)


def unzip(file):
    """ Simple function to unzip a file. """
    zfile = zipfile.ZipFile(file)
    for name in zfile.namelist():
        (dirname, filename) = os.path.split(name)
        logging.debug('Decompressing ' + filename + ' in ' + dirname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        zfile.extract(name, dirname)


def stats_kv(line, kvdictionary):
    matchObj = re.match(r'([^\s]+)\s+(.*)$', line, re.I)
    if matchObj:
        key = matchObj.group(1)
        value = matchObj.group(2)
        matchObj = re.match(r'[\-\d]+(.\d+)?$', value, re.I)
        if matchObj:
            value = num(value)
            kvdictionary[key] = value


# see try-parse in the clojure version
def isStatsForBucket(line):
    matchObj = re.match(
        r'^\[stats:debug,([^,]+),.*Stats for bucket \"(.*)\".*$', line, re.M | re.I)
    if matchObj:
        dayandtime = matchObj.group(1)
        bucket = matchObj.group(2)
        formatteddayandtime = datetime.datetime.strptime(
            dayandtime, '%Y-%m-%dT%H:%M:%S.%f')
        epochtime = calendar.timegm(formatteddayandtime.timetuple())
        return bucket, epochtime
    else:
        return "", 0

def isNsDoctorStats(line):
    matchObj = re.match(r'^\[ns_doctor:debug,([^,]+),([^:]+):ns_doc.*$', line)
    if matchObj:
        dayandtime = matchObj.group(1)
        node = matchObj.group(2)
        formatteddayandtime = datetime.datetime.strptime(
            dayandtime, '%Y-%m-%dT%H:%M:%S.%f')
        epochtime = calendar.timegm(formatteddayandtime.timetuple())
        return node, epochtime
    else:
        return "",0

# Lots of useful stuff in ns_doctor which isn't bucket related.
def processNsDoctorStats(node, data, statsDictionary):
    doctor_data = ""
    bytes_read = 0
    for line in data:
        doctor_data = doctor_data + line
        bytes_read+=len(line)
        if line.endswith(">>}]}]\n"):
            break

    erl = erlangParser.parseErlangConfig(doctor_data)

    # return a map of id -> stats_dictionary
    return_map = dict()

    if node in erl:
        for task in erl[node]['local_tasks']:
            if task['type'] == "xdcr":
                idarray = task['id'].split('/')
                task['uptime'] = erl[node]['wall_clock'] # Adding this K/V makes rate() work
                return_map["xdcr_{}".format(idarray[-1])] = task

    return return_map, bytes_read

def watched_stream_getendsize(zipfile, entry_file, filename):
    endsize = zipfile.getinfo(entry_file).file_size
    logging.debug(entry_file + ' size of stat file= ' + str(endsize))
    return endsize

def update_progress_so_far(progress_queue, bytes_total, bytes_read):
    try:
        # Try an update the queue, skip this update if full
        progress_queue.put_nowait({'progress_end_size':bytes_total, 'progress_so_far': bytes_read})
    except Full:
        # Queue is small, this is fine.
        pass

def stats_parse(bucketDictionary, zipfile, stats_file, filename, progress_queue):
    try:
        data = zipfile.open(stats_file, 'rU')
    except KeyError:
        logging.error('Error: Cannot find ns_server.stats.log in' + stats_file + \
                      'See stats_parse(bucketDictionary, zipfile, stats_file, filename).')
        os._exit(1)
    else:
        current_bytes = 0
        endsize = watched_stream_getendsize(zipfile, stats_file, filename)
        update_progress_so_far(progress_queue, endsize, current_bytes)
        data = TextIOWrapper(data)
        bucket = None
        statsDictionary = dict()
        byte_count = 0
        t = time.clock()
        for line in data:
            byte_count += len(line)
            line = line.rstrip()
            if line != "":
                (possibleBucket, epoch) = isStatsForBucket(line)

                if epoch != 0:
                    bucket = possibleBucket
                    statsDictionary = dict()
                    statsDictionary['localtime'] = epoch
                    # check if have previous stats for this bucket
                    if bucket not in bucketDictionary.keys():
                        bucketDictionary[bucket] = []
                else:
                    # Add to statsDictionary
                    stats_kv(line, statsDictionary)
            else:
                # reached an empty line
                current_bytes = current_bytes + byte_count
                update_progress_so_far(progress_queue, endsize, current_bytes)
                byte_count = 0
                if bucket:
                    bucketDictionary.get(bucket).append(statsDictionary)
                bucket = None
        process_time = time.clock() - t
        update_progress_so_far(progress_queue, endsize, endsize)
        print "{}: Processing of ns_server.stats took {} seconds".format(filename, process_time)

def stats_parse_ns_doctor(bucketDictionary, zipfile, stats_file, filename, progress_queue):
    try:
        data = zipfile.open(stats_file, 'rU')
    except KeyError:
        logging.error('Error: Cannot find ns_server.stats.log in' + stats_file + \
                      'See stats_parse(bucketDictionary, zipfile, stats_file, filename).')
        os._exit(1)
    else:
        current_bytes = 0
        scale = 4
        # ns_doctor is slow, so scale the progress
        endsize = watched_stream_getendsize(zipfile, stats_file, filename) * scale
        update_progress_so_far(progress_queue, endsize, current_bytes)
        data = TextIOWrapper(data)
        t = time.clock()
        for line in data:
            (node, epoch) = isNsDoctorStats(line)
            if epoch != 0:
                statsDictionary = dict()
                statsDictionary['localtime'] = epoch
                (doctor_stats, bytes_read) = processNsDoctorStats(node, data, epoch)

                # doctor_stats contains stats for each thing, the key being a thing like xdcr
                # e.g. xdcr_XDCRName = {'latency':100, 'docs_sent':22}
                for key in doctor_stats:
                    if key not in bucketDictionary.keys():
                        bucketDictionary[key] = []
                    doctor_stats[key]['localtime'] = epoch

                    bucketDictionary.get(key).append(doctor_stats[key])

                current_bytes = current_bytes + (bytes_read * scale)
                update_progress_so_far(progress_queue, endsize, current_bytes)

        update_progress_so_far(progress_queue, endsize, endsize)
        process_time = time.clock() - t
        print "{}: Processing of ns_server.stats (ns_doctor) took {} seconds".format(filename, process_time)

def load_collectinfo(filename, args, progress_queue, process_stats_queue):
    """Function to load the stats for one of the zip files.
       The function is invoked by each thread responsible for loading
        a zip file. """
    # First open the zipfle for reading.
    file = zipfile.ZipFile(args.dir + '/' + filename, 'r')

    # Now search the zip file for the stats file.
    stats_file = ''
    diag_file = ''
    for name in file.namelist():
        if re.match(r'.*/ns_server.stats.log', name, re.M | re.I):
            stats_file = name
        elif re.match(r'.*/diag.log', name, re.M | re.I):
            diag_file = name

    if stats_file == '':
        logging.error('Error, Cannot find ns_server.stats.log in ' + filename \
                      + 'see function load_collectinfo(filename, args)')
        os._exit(1)

    logging.debug('stats_file= ' + stats_file)
    logging.debug('diag_file= ' + diag_file)

    bucketDictionary = {}
    # Get the stats for this zip files and place in thread local storage.
    stats_parse(bucketDictionary, file, stats_file, filename, progress_queue)

    # Return the dictionary to the main process
    process_stats_queue.put(bucketDictionary)

def load_erlangs_stats(filename, args, progress_queue, process_stats_queue):
    """ Function to load the ns_doctor/erlang stats """
    # First open the zipfle for reading.
    file = zipfile.ZipFile(args.dir + '/' + filename, 'r')
    stats_file = None
    for name in file.namelist():
        if re.match(r'.*/ns_server.stats.log', name, re.M | re.I):
            stats_file = name

    bucketDictionary = {}
    stats_parse_ns_doctor(bucketDictionary, file, stats_file, filename, progress_queue)

    # Return the dictionary to the main process
    process_stats_queue.put(bucketDictionary)

def load_node_events(filename, args, progress_queue, process_stats_queue):
    """ Function to load the interesting node events """
    # First open the zipfle for reading.
    file = zipfile.ZipFile(args.dir + '/' + filename, 'r')
    bucketDictionary = {}
    node_events.NodeEvents(progress_queue).add_interesting_events(bucketDictionary, file, filename)

    # Return the dictionary to the main process
    process_stats_queue.put(bucketDictionary)

def merge_stats(stats):
    # Use 'ns_server' as the master and merge into it.

    # node_events merges into ns_server data and needs a bin_search
    rval = stats['ns_server.stats']['stats']
    if 'node_events' in stats:
        node_events.merge_events(stats['ns_server.stats']['stats'], stats['node_events']['stats'])

    if 'ns_server.erlang_stats' in stats:
        rval = dict(stats['ns_server.stats']['stats'].items() + stats['ns_server.erlang_stats']['stats'].items())

    return rval

def signal_handler(signal, frame):
    """ Signal handler for SIGINT to terminate all threads.   """
    print('\n\nYou pressed Ctrl+C!...goodbye from Mortimer2.')
    # The OS exit causes the Web Server thread to also terminate
    os._exit(0)


""" This is the start of Mortimer2. The main function is responsible for
    1. Registering the Ctrl+C signal handler
    2. Reading in the command line args
    3. Starting the web server
    4. Opening the web browser
    5. Loading in all the stats files. """
def main():
    signal.signal(signal.SIGINT, signal_handler)

    # Parse the arguments given.
    args = argumentParsing()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    logging.debug(args)

    if args.version:
        print("Version:" + str(globals.versionnumber))
        exit(0)

    # Find the path for the mortimer package
    relativepath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    matchObj= re.match(r'(.*)mortimer.py$', sys.argv[0], re.I)
    if matchObj and matchObj.group(1) != '':
        relativepath = matchObj.group(1)
    logging.debug('relativepath = ' + relativepath)

    # Start the web server
    web_server_thread = web_server.WebServer(args, relativepath)
    web_server_thread.start()

    # Open the web browser on the correct port
    if args.browse:
        url = 'http://localhost:' + str(args.port)
        webbrowser.open_new(url)

    # Find all the files to load
    fileList = []
    for (dirpath, dirnames, filenames) in walk(args.dir):
        fileList.extend(filenames)
        break

    # process entry point map
    process_entry_functions = {
        'ns_server.stats':load_collectinfo
    }

    # Optional features (these can slow down loading)
    if args.events:
        process_entry_functions['node_events'] = load_node_events

    if args.erlang:
        process_entry_functions['ns_server.erlang_stats'] = load_erlangs_stats

    globals.loading_file = True

    # Load the stats files using python's multiprocessing
    # One process per stat type per zipfile.
    for filename in fileList:
        root, ext = os.path.splitext(filename)
        if ext == '.zip':
            logging.debug(filename)

            # Create the process data structures
            # - progress_queue is for sending messages about how far through the data crunching we are
            # - process_return_queue is for returning the final dictionary
            # - cached_progress is for the webserver, as we may always have a new progress to report 
            #   we would report the last known progress.
            globals.processes[filename] = {}
            for k in process_entry_functions:
                progress_queue = multiprocessing.Queue(1)
                process_return_queue = multiprocessing.Queue(1)
                process = multiprocessing.Process(target=process_entry_functions[k],
                                args=(filename, args, progress_queue, process_return_queue))
                globals.processes[filename][k] = {
                    'process' : process,
                    'progress_queue' : progress_queue,
                    'return_queue' : process_return_queue,
                    'cached_progress' : {'progress_end_size':1, 'progress_so_far':0}
                }

            # Start the processes
            for k in globals.processes[filename]:
                globals.processes[filename][k]['process'].start()

    # For each file collect each sub-process return data
    for filename in globals.processes:
        for key in globals.processes[filename]:
            globals.processes[filename][key]['stats'] = globals.processes[filename][key]['return_queue'].get()
            globals.processes[filename][key]['process'].join()

    # Now we need to merge stats into one super stats!
    for filename in globals.processes:
        globals.stats[filename] = merge_stats(globals.processes[filename])

    logging.debug('finished loading zip fles')
    globals.loading_file = False

    message = {'kind': 'status-update', 'data': {'files': web_server.list_files(), 'loading': {}, 'buckets': web_server.list_buckets()}}
    for k,v in globals.messageq.items():
        v.put(message)

    # Wait for user to press ctl-C
    signal.pause()

    return 0

if __name__ == '__main__':
    sys.exit(main())

