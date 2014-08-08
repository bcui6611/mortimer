import Queue
from threading import Lock
from threading import local

versionnumber = 1.0

loading_file = False

sessionData = {'smoothing-window': 0}

q = Queue.Queue()

messageq = {}

threads = {}

threadingDS = Lock()

threadLocal = local()

# It's a big map:
#     {"filename"
#      {"bucketname"
#       [{:stat1 val1 :stat2 val2}
#        {:stat2 val3 :stat2 val4}]}}
stats = dict()
