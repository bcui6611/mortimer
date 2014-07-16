#from __future__ import unicode_literals, print_function
import zipfile
import os.path
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import re
import argparse
import logging
import threading
import webbrowser
import signal
import time
import datetime
import calendar
import json
import io
import string
import platform
import Queue
from lepl import *
#import numpy
from bisect import bisect_left

from pypeg2 import *
import urllib
#from functools import lru_cache
from os import _exit
from os import walk
# sys is just required for flushing stderr
import sys

# It's a big map:
#     {"filename"
#      {"bucketname"
#       [{:stat1 val1 :stat2 val2}
#        {:stat2 val3 :stat2 val4}]}}
stats = dict()
sessionData = {"smoothing-window" : 0}
loading_file = False
websocket = 0
q = Queue.Queue()



threads = {}
threadingDS = threading.Lock()
threadLocal = threading.local()

# {"kind": "status-update","data":{"files":[],"loading":{"erlang_node1.zip":{"endsize":202429480,"counted":[201147770]}},"buckets":[]}}
def send_update():
    files_being_loaded = {}
    for a,b in threads.items():
        files_being_loaded[a] = {'endsize':b['progress_end_size'],'counted':[b['progress_so_far']]}
    message = {'kind':'status-update','data':{'files':[], 'loading':files_being_loaded,'buckets':[]}}
    jsonmessage = json.dumps(message)
    if websocket != 0:
     websocket.write_message(jsonmessage)


def progress_thread_function():
    while 1:
        if loading_file:
          send_update()
        time.sleep(0.5)


def progress_updater_start():
    # create a thread
    thread = threading.Thread(target = progress_thread_function)
    thread.start()



def argumentParsing():
    parser = argparse.ArgumentParser(description='Mortimer2')
    parser.add_argument('-p', '--port', type=int, default=18334, help='Start webserver on this port')
    parser.add_argument('-d', '--dir', default='.', help='Directory to search for collectinfo .zips')
    parser.add_argument('-v', '--debug', action="store_true", default=False, help='Enable debugging messages')
    parser.add_argument('-n', '--browse', action="store_false", default=True, help='Auto open browser')
    parser.add_argument('-u', '--update', action="store_true", default=False, help='Check for updates')
    parser.add_argument('-e', '--diag', action="store_true", default=False, help='Read diag.log (events)')
    return parser.parse_args()


def parse_statqry(qstr):
    matchObj = re.match( r'^([^;]+);(.*)$', qstr, re.I)
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


class Identifier(List):
  pass
class Number(List):
  pass
class Add(List):
  pass
class Sub(List):
  pass
class Mul(List):
  pass
class Div(List):
  pass
class FunctionCall(List):
  pass

my_Identifier = Token(r'[a-zA-Z_][a-zA-Z_0-9]*') > Identifier
symbol = Token('[^0-9a-zA-Z \t\r\n]')
my_Value = Token(UnsignedReal())
my_Number = Optional(symbol('-')) + my_Value > Number
group2 = Delayed()
my_Expr = Delayed()


# first layer, most tightly grouped, is parens and numbers
parens = ~symbol('(') & my_Expr & ~symbol(')')
my_Function = my_Identifier & parens > FunctionCall
group1 = my_Function | parens | my_Number | my_Identifier


# second layer, next most tightly grouped, is multiplication
my_Mul = group1 & ~symbol('*') & group2 > Mul
my_Div = group1 & ~symbol('/') & group2 > Div
group2 += my_Mul | my_Div | group1

# third layer, least tightly grouped, is addition
my_Add = group2 & ~symbol('+') & my_Expr > Add
my_Sub = group2 & ~symbol('-') & my_Expr > Sub
my_Expr += my_Add | my_Sub | group2



def parse_expr(expr, context):
        result = my_Expr.parse(expr)
        return result
            #except:
            #print("Parsing Error")
            #print("expr= " + expr)
            #return ""




def series_by_name(seriesname, context):
    print("Identifier = " + str(seriesname))
    print("context = " + str(context))
    keysDictionary = {'keys' : [context['file'],context['bucket']]}
    print("keys dict = " + str(keysDictionary))
    file = context['file']
    bucket = context['bucket']
    data = stats[file][bucket]
    result = []
    for x in data:
        result.append([x['time'],x[seriesname]])
    #print(result)
    return result


def multiplying(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] * op2
        return op1
    elif isinstance(op2, list) and not isinstance(op1, list):
        for x in op2:
            x[1] = x[1] * op1
        return op2
    else:
        if len(op1) != len(op2):
            print("lengths not equal")
            exit(1)
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] * op2[x][1]
            return op1


def dividing(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] / op2
        return op1
    elif isinstance(op2, list) and isinstance(op1, list):
        if len(op1) != len(op2):
            print("lengths not equal")
            exit(1)
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] / op2[x][1]
                return op1
    else:
        print("dividing number by a list")
        exit(1)



def adding(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] + op2
        return op1
    if isinstance(op2, list) and not isinstance(op1, list):
        for x in op2:
            x[1] = x[1] + op1
        return op2
    else:
        if len(op1) != len(op2):
            print("lengths not equal")
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] + op2[x][1]
            return op1


def subtracting(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] - op2
        return op1
    elif isinstance(op2, list) and isinstance(op1, list):
        if len(op1) != len(op2):
            print("lengths not equal")
            exit(1)
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] - op2[x][1]
            return op1
    else:
        print("subtracting list from a number")
        exit(1)



def derivative(f):
  def df(x, h=0.1e-4):
    return ( f(x+h/2) - f(x-h/2) )/h
  return df


def binary_search(a, x, lo=0, hi=None):   # can't use a to specify default for hi
    hi = hi if hi is not None else len(a) # hi defaults to len(a)
    pos = bisect_left(a,x,lo,hi)          # find insertion position
    if pos == 0 or pos == hi:
      return pos
    elif a[pos] >= x and a[pos-1] <= x:
      return pos
    else:
      return -1
    # return (pos if pos != hi and a[pos] == x else -1) # don't walk off the end

def searchsorted(xin, xout):
    xin.sort()
    #print("searchsorted function xin =" + str(xin))
    result = binary_search(xin, xout)
    return result
    #print("searchsorted binary search xout = " + str(xout) + "  result = " + str(result))

def interpolate(derivseries, interpargs):
    xin = []
    yin = []
    for p in derivseries:
        xin.append(p[0])
        yin.append(p[1])
    lenxin = len(xin)
    
    def inter(xout):
        i1 = searchsorted(xin, xout)
        #s1 = numpy.searchsorted(xin, xout)
        #if i1 != s1:
        #  print("s1 = " + str(s1) + " il = " + str(i1))
        # exit(1)
        if i1 == 0:
          i1 = 1
        if i1 == lenxin:
          i1 = lenxin -1
        x0 = xin[i1-1]
        x1 = xin[i1]
        y0 = yin[i1-1]
        y1 = yin[i1]
        if interpargs == 'linear':
            return (xout - x0) / (x1 - x0) * (y1 - y0) + y0
    return inter


def derivativewrapper(pointseries, interpargs):
    print("derivative wrapper function")
    # remove all those that have null as second argument
    derivseries = []
    for x in pointseries:
        if x[1] != None:
          derivseries.append(x)
    inter = interpolate(derivseries, interpargs)
    #first derivative
    dg = derivative(inter)
    # calling the first derivative on the interpolate function
    result = []
    for x in pointseries:
      newx = [x[0], dg(x[0]+0.5)]
      result.append(newx)
    print("result = " + str(result))
    return result

def moving_average(pointseries, window):
    print("Calculating moving average: window = " + str(window))
    print("pointseries 0 = " + str(pointseries[0]))
    print("pointseries -1 = " + str(pointseries[-1]))
    print(str(pointseries))
    smoothed = []
    for n in range(len(pointseries)):
      rangestart = n - window
      rangeend = n + window + 1
      print("n = " + str(n))
      print("rangestart =" + str(rangestart))
      print("rangeend = " + str(rangeend))
      samples = []
      if rangestart < 0:
        rangestart = 0
        samples.append(None)
      if rangeend > len(pointseries):
        rangeend = len(pointseries)
        samples.append(None)
      for x in range(rangestart, rangeend):
        samples.append(pointseries[x][1])
      print("samples =" + str(samples))
      orig = pointseries[n]
      print("orig =" + str(orig))
      print("t = " + str(orig[0]))
      #in clojure code also check that n - window - 1 < 0.
      # Don't know why - does not appear to be required. Bug?
      if None in samples:
        result = [orig[0], None]
      else:
        numofsamples = len(samples)
        samplestotal = sum(samples)
        result = [orig[0], float(samplestotal)/float(numofsamples)]
      print("result = " + str(result))
      print("\n")
      smoothed.append(result)
    return smoothed


def expr_fun_table(fname, seriesname, context):
    print("Doing function call")
    if fname[0] == "rate":
        print("Doing the rate function")
        uptime = series_by_name('uptime', context)
        movingaverage = moving_average(uptime, context['smoothing-window'])
        print("uptime movingaverage = " + str(movingaverage))
        derivativeresult = derivativewrapper(movingaverage, 'linear')
    
        series = series_by_name(seriesname[0], context)
        seriesmovingaverage = moving_average(series, context['smoothing-window'])
        print("series movingaverage = " + str(seriesmovingaverage))
        seriesderivativeresult = derivativewrapper(seriesmovingaverage, 'linear')
        print("length of uptime derivatives =" + str(len(derivativeresult)))
        print("length of series derivatives =" + str(len(seriesderivativeresult)))
        result = []
        for x in range(len(derivativeresult)):
            if derivativeresult[x][1] < 0:
              result.append([seriesderivativeresult[x][0],None])
            else:
              result.append(seriesderivativeresult[x])
        return result
    
    else:
       print("Error don't recognise function")
    return series_by_name(seriesname[0], context)


def expr_evaluate(exprtree, context):
    print("expr=" + str(exprtree))
    print("context=" + str(context))
    if isinstance(exprtree, Number):
        return float(exprtree[0])
    elif isinstance(exprtree, Identifier):
      return series_by_name(exprtree[0], context)
    elif isinstance(exprtree, FunctionCall):
        return expr_fun_table(exprtree[0], exprtree[1], context)
    elif isinstance(exprtree, Mul):
      op1 = expr_evaluate(exprtree[0], context)
      op2 = expr_evaluate(exprtree[1], context)
      return multiplying(op1,op2)
    elif isinstance(exprtree, Div):
      op1 = expr_evaluate(exprtree[0], context)
      op2 = expr_evaluate(exprtree[1], context)
      return dividing(op1,op2)
    elif isinstance(exprtree, Sub):
      op1 = expr_evaluate(exprtree[0], context)
      op2 = expr_evaluate(exprtree[1], context)
      return subtracting(op1,op2)
    elif isinstance(exprtree, Add):
      op1 = expr_evaluate(exprtree[0], context)
      op2 = expr_evaluate(exprtree[1], context)
      return adding(op1,op2)


def expr_eval_string(expr, contextDictionary):
   # remove whitespace from start & end of the string
   # can't see whenever this is required however in original clojure code
   expr = expr.strip()
   parsedExpression = parse_expr(expr, contextDictionary)
   print("Expression = " + str(parsedExpression))
   print("\n\n\n")
   sys.stdout.flush()
   result = expr_evaluate(parsedExpression[0], contextDictionary)
   return result


# Implement a LRU cache containing maximum of 100 items
# #@lru_cache(maxsize=100)
def create_pointseries(qstr):
    expr, queryDictionary = parse_statqry(qstr)
    # merge in sessionData to the contextDictionary
    contextDictionary = dict(list(sessionData.items()) + list(queryDictionary['context'].items()))
    data = expr_eval_string(expr, contextDictionary)
    namestring = expr + " in " + contextDictionary['bucket'] + " on " + contextDictionary['file']
    # In the original mortimer the name is attached as meta-data to the data - we just attach the data
    pointseries = {'stats' : namestring, 'points' : data}
    return pointseries

def multistat_response(queries):
    multipointseries = {}
    multipointseries['stats'] =[]
    multipointseries['interpolated'] ='false'
    multipointseries['points'] = []
    pointseriesmap = {}
    times = []
    
    # split-up query
    for q in queries:
       print("query=" + q)
       pointseries = create_pointseries(q)
       multipointseries['stats'].append(pointseries['stats'])
       # get just the times
       times = times + [x[0] for x in pointseries['points']]
       for x in pointseries['points']:
          t = x[0]
          s = x[1]
          if t in pointseriesmap:
                pointseriesmap[t] = pointseriesmap[t] + [s]
          else:
               pointseriesmap[t] = [s]
    print("pointseries map=")
    print(str(pointseriesmap))
    print("multipoint stats=")
    print(str(multipointseries['stats']))
    # remove duplicates
    times = list(set(times))
    times.sort()
    # iterate through the sorted and non-duplicate times
    for t in times:
       multipointseries['points'].append([t * 1000] + pointseriesmap[t])
    
    print("multipoint points=")
    print(str(multipointseries['points']))
    return multipointseries

def num(s):
    try:
      return int(s)
    except ValueError:
      try :
        return float(s)
      except ValueError:
        print("value="+s)
        return s


def list_files():
  files = []
  for k,v in stats.items():
    files.append(k)
  files.sort()
  return files


def list_buckets():
    buckets = []
    for k,v in stats.items():
      for a,b in v.items():
        buckets.append(a)
    # Remove any duplicates
    buckets = list(set(buckets))
    buckets.sort()
    return buckets

def list_stats():
    statsList = []
    if not loading_file:
      for k,v in stats.items():
        for a,b in v.items():
          # In the original mortimer only use first entry in list
          # I suspect this was a bug.  We iterate through all elements in the list
          for item in b:
            for x,y in item.items():
                matchObj = re.match( r'^{.*', x, re.I)
                if not matchObj:
                  statsList.append(x)
      statsList = list(set(statsList))
      statsList.sort()
    return statsList

# unzip a file
def unzip(file):
    zfile = zipfile.ZipFile(file)
    for name in zfile.namelist():
        (dirname, filename) = os.path.split(name)
        logging.debug("Decompressing " + filename + " in " + dirname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        zfile.extract(name, dirname)


def stats_kv(line, kvdictionary, epoch):
    matchObj = re.match( r'([^\s]+)\s+(.*)$', line, re.I)
    if matchObj:
      key = matchObj.group(1)
      value = matchObj.group(2)
      matchObj = re.match( r'[\-\d]+(.\d+)?$', value, re.I)
      if matchObj:
        value = num(value)
        if key == 'time':
            difference = float(value) - float(epoch)
            difference = difference / 60 / 60
            difference = round(difference)
            if time.daylight:
              difference += 1.0
            print ("value time = " + str(value) + " difference = " + str(difference) + "altzone =" + str(time.daylight))
            value = value - (difference * 60 * 60)
        kvdictionary[key] = value;


# see try-parse in the clojure version
def isStatsForBucket(line):
    matchObj = re.match( r'^\[stats:debug,([^,]+),.*Stats for bucket \"(.*)\".*$', line, re.M|re.I)
    if matchObj:
      dayandtime = matchObj.group(1)
      bucket = matchObj.group(2)
      formatteddayandtime= datetime.datetime.strptime(dayandtime, "%Y-%m-%dT%H:%M:%S.%f")
      logging.debug(formatteddayandtime)
      epochtime = calendar.timegm(formatteddayandtime.timetuple())
      return bucket, epochtime
    else:
      return "", 0



def watched_stream_setendsize(zipfile, entry_file, filename):
    endsize = zipfile.getinfo(entry_file).file_size
    logging.debug(entry_file + " size of stat file= " + str(endsize))
    threadingDS.acquire()
    threads[filename]['progress_end_size'] = endsize
    threadingDS.release()


def stats_parse(bucketDictionary, zipfile, stats_file, filename):
    print("stats_parse" + filename)
    try:
        data = zipfile.open(stats_file, 'rU')
    except KeyError:
        logging.error("Cannot find ns_server.stats.log in " + stats_file)
    else:
        watched_stream_setendsize(zipfile, stats_file, filename)
        data  = io.TextIOWrapper(data)
        bucket = ""
        statsDictionary = dict()
        byte_count = 0
        last_epoch = 0
        for line in data:
            byte_count += len(line)
            line =line.rstrip()
            if line != "":
              (possibleBucket, epoch) = isStatsForBucket(line)
              
              if epoch != 0:
                last_epoch = epoch
                bucket = possibleBucket
                logging.debug("Bucket= " + bucket + " Epoch time= " + str(epoch))
                statsDictionary = dict()
                statsDictionary["localtime"] = epoch
                print("converted time = " + str(time.gmtime(epoch)) + " epoch = " + str(epoch))
                # check if have previous stats for this bucket
                if bucket not in bucketDictionary.keys():
                   bucketDictionary[bucket] = []
              else:
                logging.debug(line)
                # Add to statsDictionary
                stats_kv(line, statsDictionary, last_epoch)
            else:
              # reached an empty line
              threadingDS.acquire()
              threads[filename]['progress_so_far'] += byte_count
              threadingDS.release()
              byte_count = 0
              if bucket != "":
                bucketDictionary.get(bucket).append(statsDictionary)
              bucket = ""
        




# function to load the stats for one of the zip files
def load_collectinfo(filename, args):
    #first open the zipfle for reading
    file = zipfile.ZipFile(args.dir + "/" + filename, "r")
    # now search the zip file for the stats file
    stats_file = ''
    diag_file = ''
    for name in file.namelist():
      if re.match( r'.*/ns_server.stats.log', name, re.M|re.I):
        stats_file = name
      elif re.match( r'.*/diag.log', name, re.M|re.I):
        diag_file = name

    if stats_file == '':
        logging.error("Cannot find ns_server.stats.log in " + filename)
        os._exit(1)

    logging.debug("stats_file= " + stats_file)
    logging.debug("diag_file= " + diag_file)
    #unzip(args.dir + "/" + filename)
    threadLocal.stats = {}
    threadLocal.stats[filename] = dict()
    stats_parse(threadLocal.stats.get(filename), file, stats_file, filename)
    q.put(threadLocal.stats)

    # Temporary debug to print out the complete stats file
    #for k,v in stats.items():
    # print("New filename Map= " + k)
    # for a,b in v.items():
    #    print("New bucket Map= " + a)
    #    for item in b:
    #      print("New List =" + str(item.get('localtime')))
    #      for x,y in item.items():
    #        print(x,y)

    sys.stdout.flush()

def send_session():
    message = {'kind':'session-data','data': sessionData}
    jsonmessage = json.dumps(message)
    print(jsonmessage)
    if websocket != 0:
        websocket.write_message(jsonmessage)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')


class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        global websocket
        websocket = self
        print('new connection opened')
    
        # send session data update
        send_session()
        # Don't see why required but in original
        # Can remove in original and has no effect
        send_update()
    
    def on_message(self, message):
        print('message received %s' % message)
    
    def on_close(self):
        print('connection closed')


class FileHandler(tornado.web.RequestHandler):
    def get(self):
        resource = json.dumps(files_stats())
        self.write(resource)

class BucketHandler(tornado.web.RequestHandler):
    def get(self):
        resource = json.dumps(list_buckets())
        self.write(resource)

class StatsHandler(tornado.web.RequestHandler):
    def get(self):
        resource = json.dumps(list_stats())
        self.write(resource)

class StatDataHandler(tornado.web.RequestHandler):
    def get(self):
        print("got here!!!!!!!!!!!!!!!!!!!!!!")
        s = self.request.query
        if platform.python_implementation() == 'PyPy':
          s2= urllib.unquote(s)
        else:
          s2 = urllib.unquote(s)
        matchObj = re.match( '^stat=\[\"(.*)\"\]$', s2, re.I)
        if matchObj:
            queries = matchObj.group(1)
            queries= queries.split('\",\"')
            print(queries)
        #matchObj = re.match( '^stat=\[\"(.*)\"\]$', s2, re.I)
        #if matchObj:
        #    query = matchObj.group(1)
        #    print(query)
            result = multistat_response(queries)
            resource = json.dumps(result)
            self.write(resource)


# The class for creating the web server using tornado
# See http://www.tornadoweb.org/ for more details
class WebServer (threading.Thread):
    def __init__(self, args):
        threading.Thread.__init__(self)
        self.port = args.port
    
    def run(self):
        print(self.port)
        application = tornado.web.Application([
                                                (r"/status-ws", WSHandler),
                                                (r"/stats",StatsHandler),
                                                (r"/", MainHandler),
                                                (r"/buckets",BucketHandler),
                                                (r"/files",FileHandler),
                                                (r"/statdata",StatDataHandler),
                                                (r'/(.*)', tornado.web.StaticFileHandler, {'path': './'}),
                                                                                               ],
                                              )
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(self.port)
        tornado.ioloop.IOLoop.instance().start()




def signal_handler(signal, frame):
    print('\n\nYou pressed Ctrl+C!...goodbye from Mortimer2')
    # The OS exit causes the Web Server thread to also terminate
    os._exit(0)




if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    # First parse the arguments given.
    args = argumentParsing()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    logging.debug(args)
    fileList = []


    # Start the web server
    web_server_thread = WebServer(args)
    web_server_thread.start()

    # Open the web browser on the correct port
    if args.browse:
      url = 'http://localhost:' + str(args.port)
      webbrowser.open_new(url)


    progress_updater_start()


    for (dirpath, dirnames, filenames) in walk(args.dir):
        fileList.extend(filenames)
        break

    for filename in fileList:
        root, ext = os.path.splitext(filename)
        if ext == '.zip':
           print("filename =" + filename)
    
    for filename in fileList:
        root, ext = os.path.splitext(filename)
        if ext == '.zip':
            logging.debug(filename)
            threadingDS.acquire()
            threads[filename] = {'thread': 0, 'progress_end_size': 0, 'progress_so_far' : 0}
            threadingDS.release()
            t = threading.Thread(name='load_thread', target=load_collectinfo, args = (filename, args))
            threadingDS.acquire()
            threads[filename]['thread'] = t
            threadingDS.release()
            loading_file = True
            t.start()

    for a,b in threads.items():
        b['thread'].join()



    while not q.empty():
      statmap = q.get()
      for k,v in statmap.items():
        stats[k] = v

    print ("finished loading")
    loading_file = False
    message = {'kind':'status-update','data':{'files':list_files(),'loading':{},'buckets':list_buckets()}}
    jsonmessage = json.dumps(message)
    if websocket != 0:
        websocket.write_message(jsonmessage)


    # Wait for user to press ctl-C
    signal.pause()