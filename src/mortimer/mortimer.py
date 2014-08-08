#!/usr/bin/env python2.7
# -*- mode: Python;-*-

#from __future__ import unicode_literals, print_function
import zipfile
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
import Queue
import sys

from os import _exit
from os import walk
from io import TextIOWrapper

import globals
import grammar
import web_server

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
    parser.add_argument('-e', '--diag', action='store_true',
                        default=False, help='Read diag.log (events). This is currently not supported')
    parser.add_argument('--version',  action='store_true',
                        default=False, help='Prints out the version number of mortimer')
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


def stats_kv(line, kvdictionary, epoch, localtimediff):
    matchObj = re.match(r'([^\s]+)\s+(.*)$', line, re.I)
    if matchObj:
        key = matchObj.group(1)
        value = matchObj.group(2)
        matchObj = re.match(r'[\-\d]+(.\d+)?$', value, re.I)
        if matchObj:
            value = num(value)
            if key == 'time':
                difference = value - epoch
                # round the difference to nearest minute
                difference = int(round(difference / 60.0)) * 60
                value = value - difference - localtimediff
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


def watched_stream_setendsize(zipfile, entry_file, filename):
    endsize = zipfile.getinfo(entry_file).file_size
    logging.debug(entry_file + ' size of stat file= ' + str(endsize))
    globals.threadingDS.acquire()
    globals.threads[filename]['progress_end_size'] = endsize
    globals.threadingDS.release()


def stats_parse(bucketDictionary, zipfile, stats_file, filename):
    try:
        data = zipfile.open(stats_file, 'rU')
    except KeyError:
        logging.error('Error: Cannot find ns_server.stats.log in' + stats_file + \
                      'See stats_parse(bucketDictionary, zipfile, stats_file, filename).')
        os._exit(1)
    else:
        watched_stream_setendsize(zipfile, stats_file, filename)
        data = TextIOWrapper(data)
        bucket = ''
        statsDictionary = dict()
        byte_count = 0
        last_epoch = 0
        # Calculate the mortimer web browser local time difference to UTC.
        utctime = time.gmtime()
        localtime = time.localtime()
        diffseconds = calendar.timegm(localtime) - calendar.timegm(utctime)
        # round the difference to nearest minute
        localtimediff = int(round(diffseconds / 60.0)) * 60
        for line in data:
            byte_count += len(line)
            line = line.rstrip()
            if line != "":
                (possibleBucket, epoch) = isStatsForBucket(line)

                if epoch != 0:
                    last_epoch = epoch
                    bucket = possibleBucket
                    statsDictionary = dict()
                    statsDictionary['localtime'] = epoch
                    # check if have previous stats for this bucket
                    if bucket not in bucketDictionary.keys():
                        bucketDictionary[bucket] = []
                else:
                    # Add to statsDictionary
                    stats_kv(line, statsDictionary, last_epoch, localtimediff)
            else:
                # reached an empty line
                globals.threadingDS.acquire()
                globals.threads[filename]['progress_so_far'] += byte_count
                globals.threadingDS.release()
                byte_count = 0
                if bucket != '':
                    bucketDictionary.get(bucket).append(statsDictionary)
                bucket = ''


def load_collectinfo(filename, args):
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
    globals.threadLocal.stats = {}
    globals.threadLocal.stats[filename] = dict()
    # Get the stats for this zip files and place in thread local storage.
    stats_parse(globals.threadLocal.stats.get(filename), file, stats_file, filename)
    # Add the thread local stats into the queue so can be collected by main thread.
    globals.q.put(globals.threadLocal.stats)


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
if __name__ == '__main__':
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Parse the arguments given.
    args = argumentParsing()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    logging.debug(args)

    if args.version:
        print("Version:" + str(globals.versionnumber))
        exit(0)

    # Find the relative path for where mortimer.py was run
    relativepath = './'
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

    # Load the stats files using a separate thread per file
    for filename in fileList:
        root, ext = os.path.splitext(filename)
        if ext == '.zip':
            logging.debug(filename)
            globals.threadingDS.acquire()
            globals.threads[filename] = {
                'thread': 0, 'progress_end_size': 0, 'progress_so_far': 0}
            globals.threadingDS.release()
            t = threading.Thread(
                name='load_thread', target=load_collectinfo, args=(filename, args))
            globals.threadingDS.acquire()
            globals.threads[filename]['thread'] = t
            globals.threadingDS.release()
            globals.loading_file = True
            t.start()

    # Wait for all the files to be loaded
    for a, b in globals.threads.items():
        b['thread'].join()

    # Merge each threads stat data into one global stats
    while not globals.q.empty():
        statmap = globals.q.get()
        for k, v in statmap.items():
            globals.stats[k] = v

    logging.debug('finished loading zip fles')
    globals.loading_file = False
    message = {'kind': 'status-update', 'data': {'files': web_server.list_files(), 'loading': {}, 'buckets': web_server.list_buckets()}}
    for k,v in globals.messageq.items():
        v.put(message)

    # Wait for user to press ctl-C
    signal.pause()
