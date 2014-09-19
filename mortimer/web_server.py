import globals
import grammar
import stats_desc

import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import threading
import logging
import json
import Queue

# Note: when porting to python 3 urllib.unquote needs changing to
# urllib.parse.unquote
from urllib import unquote
import re

#from functools import lru_cache

""" This file contains the functions associated with providing the web server functionality.
    When the web server recieves queries for a set of stat it invokes
    multistat_response which in turn invokes create_pointseries for each query.

    The function create_pointseries invokes expr_eval_string, which is responsible for
    parsing the expression and returning the associated data.  See grammar.py for more
    details on this functionality. """


def parse_statqry(qstr):
    """ This function simply separates out the query from the context information. """
    matchObj = re.match(r'^([^;]+);(.*)$', qstr, re.I)
    if matchObj:
        expr = matchObj.group(1)
        context = matchObj.group(2).split(',')
        contextDictionary = dict()
        for item in context:
            kv = item.split('=')
            head, tail = kv[0], kv[1]
            contextDictionary[head] = tail
        return expr, contextDictionary
    else:
        print('Error could not parse query string in parse_statqry(qstr)')
        os._exit(1)


# Implement a LRU cache containing maximum of 100 items
# @lru_cache(maxsize=100)
def create_pointseries(qstr):
    """ Called by multistat_response for each query.
        It returns the data associated with the individual query. """

    expr, contextDictionary = parse_statqry(qstr)
    # merge in sessionData to the contextDictionary
    contextDictionary = dict(
        list(globals.sessionData.items()) + list(contextDictionary.items()))
    #  Calls into grammar file to fully parse the expression and collect the data
    data = grammar.expr_eval_string(expr, contextDictionary)
    if 'name' in contextDictionary.keys():
        namestring = contextDictionary[
            'name'] + ' in ' + contextDictionary['bucket'] + ' on ' + contextDictionary['file']
    else:
        namestring = expr + ' in ' + \
            contextDictionary['bucket'] + ' on ' + contextDictionary['file']
    # In the original mortimer the name is attached as meta-data to the data,
    # we just attach the data.
    pointseries = {'stats': namestring, 'points': data}
    return pointseries


def multistat_response(queries):
    """ Top-level function for returning the data for all of the queries. """
    multipointseries = {}
    multipointseries['stats'] = []
    multipointseries['interpolated'] = 'false'
    multipointseries['points'] = []
    pointseriesmap = {}
    times = []
    pointseriestimes = []

    # first get all the time points for all queries
    for q in queries:
        pointseries = create_pointseries(q)
        # get just the times
        times = times + [x[0] for x in pointseries['points']]

    # remove duplicates
    times = list(set(times))
    times.sort()
    missing_data = False
    for q in queries:
        pointseries = create_pointseries(q)
        if pointseries['points']:
            multipointseries['stats'].append(pointseries['stats'])
            # get just the times
            pointseriestimes = [x[0] for x in pointseries['points']]
            for x in pointseries['points']:
                t = x[0]
                s = x[1]
                if t in pointseriesmap:
                    pointseriesmap[t] = pointseriesmap[t] + [s]
                else:
                    #if not in pointseriesmap what happens if it is a second or third query?
                    pointseriesmap[t] = [s]


            #Now add null for all the times there is no data
            for t in times:
                if t not in pointseriestimes:
                    if t in pointseriesmap.keys():
                        pointseriesmap[t] = pointseriesmap[t] + [None]
                    else:
                        pointseriesmap[t] = [None]
        else:
            #pointseires['points'] is empty so we must be missing some data
            missing_data = True

    if missing_data:

        message = {'kind': 'warning', 'short': 'Missing data or parsing error', 'extra': ''}
        for k,v in globals.messageq.items():
            v.put(message)

    # iterate through the sorted and non-duplicate times
    for t in times:
        multipointseries['points'].append([t * 1000] + pointseriesmap[t])
    return multipointseries


def list_files():
    """ Simple function that returns all the zip files that have been loaded. """
    files = []
    for k, v in globals.stats.items():
        files.append(k)
    files.sort()
    return files


def list_buckets():
    """ Simple function that returns all the buckets that have been loaded. """
    buckets = []
    for k, v in globals.stats.items():
        for a, b in v.items():
            buckets.append(a)
    # Remove any duplicates
    buckets = list(set(buckets))
    buckets.sort()
    return buckets


def list_stats():
    """ Function that returns all the names of all the statistics that have been loaded.
        Actually those beginning with a { have been removed as there are 1000's. """
    statsList = []
    for k, v in globals.stats.items():
        for a, b in v.items():
            # In the original mortimer only use first entry in list.
            # I suspect this was a bug.  We iterate through all elements in
            # the list.
            for item in b:
                for x, y in item.items():
                    matchObj = re.match(r'^{.*', x, re.I)
                    if not matchObj:
                        statsList.append(x)
    statsList = list(set(statsList))
    statsList.sort()
    return statsList


def send_session(websocket):
    """ Function to send initial session data over web socket. """
    message = {'kind': 'session-data', 'data': globals.sessionData}
    jsonmessage = json.dumps(message)
    logging.debug(jsonmessage)
    websocket.write_message(jsonmessage)
    message = {'kind': 'status-update', 'data': {'files': list_files(), 'loading': {}, 'buckets': list_buckets()}}
    jsonmessage = json.dumps(message)
    logging.debug(jsonmessage)
    websocket.write_message(jsonmessage)



class WSHandler(tornado.websocket.WebSocketHandler):

    """ Class for callback handler to respond to Web Socket. """
    def open(self):
        logging.debug('New web socket connection opened.')
        # send session data update
        send_session(self)
        globals.messageq[str(self)] = Queue.Queue()
        self.callback = tornado.ioloop.PeriodicCallback(self.send_update, 100)
        self.callback.start()

    def on_message(self, message):
        logging.debug('Message received %s.' % message)
        decodedmessage = json.loads(message)
        for k,v in globals.messageq.items():
            v.put(decodedmessage)

    def on_close(self):
        logging.debug('Web socket connection closed.')
        try:
            self.callback.stop()
            del globals.messageq[str(self)]
        except:
            logging.debug('Web socket no longer exists.')

    def send_update(self):
        """ This function is called every 100ms and send a message if files are being loaded.
            Or there are any messages in the message queue. """

        if globals.loading_file:
            files_being_loaded = {}

            for filename in globals.processes:
                endsize = 0
                progress = 0
                # compute a progress for this file
                for proc in globals.processes[filename]:
                    try:
                        progress_data = globals.processes[filename][proc]['progress_queue'].get_nowait()
                    except Queue.Empty:
                        progress_data = globals.processes[filename][proc]['cached_progress']

                    endsize = endsize + progress_data['progress_end_size']
                    progress = progress + progress_data['progress_so_far']

                    # Stash progress in-case queue is empty
                    globals.processes[filename][proc]['cached_progress'] = progress_data

                # Now add files progress
                files_being_loaded[filename] = {'endsize': endsize, 'counted': [progress]}

            message = {'kind': 'status-update', 'data': {'files': [],
                                                         'loading': files_being_loaded,
                                                         'buckets': []}}
            jsonmessage = json.dumps(message)
            self.write_message(jsonmessage)

        try:
            while not globals.messageq[str(self)].empty():
                message = globals.messageq[str(self)].get()
                jsonmessage = json.dumps(message)
                self.write_message(jsonmessage)
        except:
            logging.debug('Web socket no longer exists.')


class MainHandler(tornado.web.RequestHandler):
    """ Class for callback handler to respond to root web page access. """
    def initialize(self, relativepath):
        self.relativepath = relativepath

    def get(self):
        self.render(self.relativepath + '/resources/public/index.html')


class FileHandler(tornado.web.RequestHandler):
    """ Class for callback handler to list zip files that have been loaded.
        It is not used by the GUI (so could remove) - but is in the original mortimer."""
    def get(self):
        resource = json.dumps(list_files())
        self.write(resource)


class BucketHandler(tornado.web.RequestHandler):
    """ Class for callback handler to list the buckets that have been loaded.
        If is not used by the GUI (so could remove) - but is in the original mortimer."""
    def get(self):
        resource = json.dumps(list_buckets())
        self.write(resource)


class StatsHandler(tornado.web.RequestHandler):
    """ Class for callback handler to list all of the available stats. """
    def get(self):
        resource = json.dumps(list_stats())
        self.write(resource)

class StatsDescHandler(tornado.web.RequestHandler):
    """ Class for callback handler to provide stats descriptions. """
    def initialize(self, relativepath):
        self.relativepath = relativepath

    def get(self):
        resource = json.dumps(stats_desc.get_stats_desc(self.relativepath))
        self.write(resource)

class StatDataHandler(tornado.web.RequestHandler):
    """ Class for callback handler to process query generated by the GUI. """
    def get(self):
        s = self.request.query
        s2 = unquote(s)
        matchObj = re.match('^stat=\[\"(.*)\"\]$', s2, re.I)
        if matchObj:
            queries = matchObj.group(1)
            queries = queries.split('\",\"')
            result = multistat_response(queries)
            resource = json.dumps(result)
            self.write(resource)
        else:
            print('Error Could not parse query sent by GUI in \
                  StatDataHandler(tornado.web.RequestHandler):get(self)')
            os._exit(1)


class WebServer (threading.Thread):
    """ The class for creating the web server using tornado
        See http://www.tornadoweb.org/ for more details"""
    def __init__(self, args, relativepath):
        threading.Thread.__init__(self)
        self.port = args.port
        self.relativepath = relativepath

    def run(self):
        logging.debug('Web server started on port ' + str(self.port))
        application = tornado.web.Application([
            (r'/status-ws', WSHandler),
            (r'/stats', StatsHandler),
            (r'/statsdesc', StatsDescHandler, {'relativepath': self.relativepath}),
            (r'/', MainHandler, {'relativepath': self.relativepath}),
            (r'/buckets', BucketHandler),
            (r'/files', FileHandler),
            (r'/statdata', StatDataHandler),
            (r'/(.*)', tornado.web.StaticFileHandler,
             {'path': self.relativepath + '/resources/public'})
        ])
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
