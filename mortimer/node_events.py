# Module that allows events from other logs to be included in the stats blob.
# Thus you can plot errors/events against stats

import zipfile
import re
import datetime
import calendar
import tempfile
import time
import mortimer
from datetime import datetime

class NodeEvents:

    events = {
    'memcached.log': [
               {'event': "Too many open connections", 'key': u'mcd_too_many_connections'},
               {'event': "Notified the completion of checkpoint persistence for vbucket",
                                'key': u'mcd_notify_checkpoint_persistence', 'bucketr':"\((\w+)\)"}],
    'ns_server.info.log' : [
                            {'event' : "]Starting rebalance", 'key': u'rebalance_start'},
                            {'event' : "]Rebalance completed successfully",'key': u'rebalance_end'},
                            {'event' : "]Started rebalancing bucket", 'key': u'rebalance_bucket_start', 'bucketr':".* bucket (.*)$"},]
            }

    # custom time stamp convert for memcached.log. So much faster than strptime!
    def mcd_fast_time(self, ts):
        month_seconds = {   'Jan':0, 'Feb':2678400,'Mar':5097600,'Apr':7776000,
                            'May':10368000,'Jun':13046400,'Jul':15638400,
                            'Aug':18316800,'Sep':20995200,'Oct':23587200,
                            'Nov':26265600,'Dec':28857600}

        # no year in memcached time-stamp, assume this year.
        epc = self.year

        ts_array = ts.split()
        epc = epc + month_seconds[ts_array[1]]
        epc = epc + (int(ts_array[2]) - 1 ) * 86400

        ts_array = ts_array[3].split(":")

        epc = epc + int(ts_array[0])*3600
        epc = epc + int(ts_array[1])*60

        ts_array = ts_array[2].split(".")
        epc = epc + int(ts_array[0])
        return epc

    # time_regexp contains information to manipulate the event time stamp
    #  "re" is a regular expression for extracting time from the matching log line
    #  "strptime" is a strptime formatter for reading the time data into datetime.
    #  "convert" strptime is slow, optionally define a custom function which does the job.
    time_regexp = {
                'memcached.log' :
                    {'re':"^(.*\.[0-9]*) ", 'strptime':"%a %b %d %H:%M:%S.%f", 'convert' : mcd_fast_time },
                'ns_server.info.log' :
                    {'re':".*info,(.*),ns", 'strptime':"%Y-%m-%dT%H:%M:%S.%f"}
                    }

    def extract_bucket(self, line, regexp):
        return re.search(regexp, line).group(1)

    def add_to_stats(self, node_dictionary, log_name, event_data, line):
        bucket = self.mcd_bucket_name

        # can this event be correlated to a bucket?
        if 'bucketr' in event_data:
            bucket = self.extract_bucket(line, event_data['bucketr'])

        if not self.printed_mcd_bucket_name:
            print "{}: Using \"{}\" as the bucket for events with no bucket.".format(self.filename, self.mcd_bucket_name)
            self.printed_mcd_bucket_name = True

        time_stamp = re.search(self.time_regexp[log_name]['re'], line).group(1)

        if 'convert' in self.time_regexp[log_name]:
            epochtime = self.time_regexp[log_name]['convert'](self, time_stamp)
        else:
            time_struct = datetime.strptime(time_stamp, self.time_regexp[log_name]['strptime'])
            epochtime = calendar.timegm(time_struct.timetuple())

        if bucket not in node_dictionary:
            node_dictionary[bucket] = {}
        if event_data['key'] not in node_dictionary[bucket]:
            node_dictionary[bucket][event_data['key']] = []

        # Store the event for later processing
        node_dictionary[bucket][event_data['key']].append(epochtime)

    def process_log(self, node_dictionary, log_name, file):
        ev = self.events[log_name]
        if ev:
            # Now scan for the presence of our event.
            lines = 0
            for line in file:
                lines += 1
                self.progress_size += len(line)
                for entry in ev:
                    if entry['event'] in line:
                        self.add_to_stats(node_dictionary, log_name, entry, line)
                # Report progress every 300 lines
                if lines == 300:
                    lines = 0
                    mortimer.update_progress_so_far(self.progress_queue, self.total_size, self.progress_size)
        else:
            print "No event entries for {}\n".format(log_name)

    def add_interesting_events(self, node_dictionary, zipfile, zipfilename):
        t = time.clock()
        self.filename = zipfilename

        # Figure out sizes for progress reporting
        for key in self.events.keys():
            for name in zipfile.namelist():
                if name.endswith('/' + key):
                    self.total_size += zipfile.getinfo(name).file_size

        mortimer.update_progress_so_far(self.progress_queue, self.total_size, self.progress_size)

        for key in self.events.keys():
            for name in zipfile.namelist():
                if name.endswith('/' + key):
                    tf = tempfile.TemporaryFile()
                    tf.write(zipfile.open(name).read())
                    tf.seek(0)

                    # some logs don't have a year in the timestamp, assume log file year is the one
                    self.year = int((datetime(zipfile.getinfo(name).date_time[0], 1, 1) - datetime(1970,1,1)).total_seconds())
                    self.process_log(node_dictionary, key, tf)
                    tf.close()

        self.process_time = time.clock() - t

        mortimer.update_progress_so_far(self.progress_queue, self.total_size, self.total_size)

        print "{}: Processing of node events took {} seconds".format(self.filename, self.process_time)

    def __init__(self, progress_queue):
        self.printed_mcd_bucket_name = False
        self.mcd_bucket_name = "@system"
        self.total_size = 0
        self.progress_size = 0
        self.progress_queue = progress_queue

def insert_stat(bucket_data, event, timestamp):
    lo = 0
    hi = len(bucket_data)
    upper_bound = hi

    if bucket_data[-1]['localtime'] < timestamp:
        # Our timestamp is above the last one.
        return

    if bucket_data[0]['localtime'] > timestamp:
        # Our timestamp is below the first one.
        return

    # localtime and our timestamp is unlikely to line up
    # Find a best match for our update
    # binary search, but compare a and a+1,a-1 with our time.
    while lo < hi:
        mid = (lo + hi) / 2

        if bucket_data[mid]['localtime'] < timestamp:
            # are we inbetween mid and mid+1?
            if bucket_data[mid+1]['localtime'] >= timestamp:

                # Are we closest to mid or mid + 1?
                z1 = abs(bucket_data[mid]['localtime'] - timestamp)
                z2 = abs(bucket_data[mid+1]['localtime'] - timestamp)
                if z1 <= z2:
                    index = mid + 1
                else:
                    index = mid

                bucket_data[index][event] += 1
                break
            lo = mid + 1
        elif bucket_data[mid]['localtime'] > timestamp:
            # are we inbetween mid and mid-1?
            if bucket_data[mid-1]['localtime'] <= timestamp:

                # Are we closest to mid or mid - 1?
                z1 = abs(bucket_data[mid]['localtime'] - timestamp)
                z2 = abs(bucket_data[mid-1]['localtime'] - timestamp)
                if z1 <= z2:
                    index = mid - 1
                else:
                    index = mid

                bucket_data[index][event] += 1
                break
            hi = mid
        # Might get lucky with a direct match...
        elif bucket_data[mid]['localtime'] == timestamp:
            bucket_data[mid][event] += 1
            break

def merge_events(bucket_stats, node_stats):
        # bucket deleted, skip
        #if bucket not in node_dictionary:
         #   return

    delete_list = []
    for bucket in node_stats:
        if bucket in bucket_stats:
            for event in node_stats[bucket]:
                # First one linear iteration to add our event with 0 hits.
                # every time slice needs the stat and a count, even if 0.
                # keys is the name of each bucket
                for stats in bucket_stats[bucket]:
                    stats[event] = 0
        else:
            # bucket not in bucket_stats, maybe an old bucket. Get rid
            delete_list.append(bucket)

    # Now pop all keys we can't process
    for delete_key in delete_list:
        node_stats.pop(delete_key)

    # Now merge the node_events into the bucket stats
    for bucket in node_stats:
        for event in node_stats[bucket]:
            for timestamp in node_stats[bucket][event]:
                insert_stat(bucket_stats[bucket], event, timestamp)
