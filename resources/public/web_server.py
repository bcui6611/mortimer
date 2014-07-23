import globals
import grammar

import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import threading
import logging
import json
# Note: when porting to python 3 urllib.unquote needs changing to
# urllib.parse.unquote
from urllib import unquote
import re


def parse_statqry(qstr):
    matchObj = re.match(r'^([^;]+);(.*)$', qstr, re.I)
    if matchObj:
        expr = matchObj.group(1)
        context = matchObj.group(2).split(',')
        contextDictionary = dict()
        for item in context:
            kv = item.split('=')
            head, tail = kv[0], kv[1]
            contextDictionary[head] = tail
        queryDictionary = dict()
        queryDictionary['expr'] = expr
        queryDictionary['context'] = contextDictionary
    return expr, queryDictionary


# Implement a LRU cache containing maximum of 100 items
# @lru_cache(maxsize=100)
def create_pointseries(qstr):
    expr, queryDictionary = parse_statqry(qstr)
    # merge in sessionData to the contextDictionary
    contextDictionary = dict(
        list(globals.sessionData.items()) + list(queryDictionary['context'].items()))
    data = grammar.expr_eval_string(expr, contextDictionary)
    if 'name' in contextDictionary.keys():
        namestring = contextDictionary[
            'name'] + ' in ' + contextDictionary['bucket'] + ' on ' + contextDictionary['file']
    else:
        namestring = expr + ' in ' + \
            contextDictionary['bucket'] + ' on ' + contextDictionary['file']
    # In the original mortimer the name is attached as meta-data to the data -
    # we just attach the data
    pointseries = {'stats': namestring, 'points': data}
    return pointseries


def multistat_response(queries):
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

    # split-up query
    for q in queries:
        pointseries = create_pointseries(q)
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
    if not globals.loading_file:
        for k, v in globals.stats.items():
            for a, b in v.items():
                # In the original mortimer only use first entry in list
                # I suspect this was a bug.  We iterate through all elements in
                # the list
                for item in b:
                    for x, y in item.items():
                        matchObj = re.match(r'^{.*', x, re.I)
                        if not matchObj:
                            statsList.append(x)
        statsList = list(set(statsList))
        statsList.sort()
    return statsList


def send_session(websocket):
    message = {'kind': 'session-data', 'data': globals.sessionData}
    jsonmessage = json.dumps(message)
    logging.debug(jsonmessage)
    websocket.write_message(jsonmessage)


class WSHandler(tornado.websocket.WebSocketHandler):

    def initialize(self):
        self.loaded = False

    def open(self):
        logging.debug('new connection opened')
        # send session data update
        send_session(self)
        self.callback = tornado.ioloop.PeriodicCallback(self.send_update, 250)
        self.callback.start()

    def on_message(self, message):
        logging.debug('message received %s' % message)

    def on_close(self):
        logging.debug('connection closed')
        self.callback.stop()

    def send_update(self):
        if globals.loading_file:
            self.loaded = False
            files_being_loaded = {}
            for a, b in globals.threads.items():
                files_being_loaded[a] = {
                    'endsize': b['progress_end_size'], 'counted': [b['progress_so_far']]}
            message = {'kind': 'status-update', 'data': {'files': [],
                                                         'loading': files_being_loaded, 'buckets': []}}
            jsonmessage = json.dumps(message)
            self.write_message(jsonmessage)
        elif self.loaded == False:
            message = {'kind': 'status-update', 'data': {'files':
                                                         list_files(), 'loading': {}, 'buckets': list_buckets()}}
            jsonmessage = json.dumps(message)
            self.write_message(jsonmessage)
            self.loaded = True


class MainHandler(tornado.web.RequestHandler):

    """ Class for callback handler to respond to root web page access. """

    def get(self):
        self.render('index.html')


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
            print('Error Could not parse query')
            exit(1)


class WebServer (threading.Thread):

    """ The class for creating the web server using tornado
        See http://www.tornadoweb.org/ for more details"""

    def __init__(self, args):
        threading.Thread.__init__(self)
        self.port = args.port

    def run(self):
        logging.debug('Web server started on port ' + str(self.port))
        application = tornado.web.Application([
            (r'/status-ws', WSHandler),
            (r'/stats', StatsHandler),
            (r'/', MainHandler),
            (r'/buckets', BucketHandler),
            (r'/files', FileHandler),
            (r'/statdata', StatDataHandler),
            (r'/(.*)', tornado.web.StaticFileHandler,
             {'path': './'})
        ])
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()
