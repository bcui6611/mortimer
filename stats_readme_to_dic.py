#!/usr/bin/python
import pprint
import re

# A tool to parse https://raw.githubusercontent.com/membase/ep-engine/master/docs/stats.org
# into a dict

#Trying to pull down the file  itself.
#import requests
#url = 'https://raw.githubusercontent.com/membase/ep-engine/master/docs/stats.org'
#r = requests.get(url)
#if r.status_code != requests.codes.ok:
#    print "Error: Request to {0} failed.".format(url)
#    sys.exit(2)

stats_file = open('stats-readme.org', 'r')
stats = {}
previous = None

for line in stats_file:
    m = re.match("^\| .*", line)
    if m:
        m = re.match("^\| Stat.*", line)
        n = re.match("^\| ---.*", line)
        o = re.match("^\|.*?\|.*?\|.*?\|", line)
        if m or n or o:
            next
        m = re.match("^\|(?P<stat>.*?)\| (?P<desc>.*?)\|", line)
        if m:
            if m.group('stat') and not m.group('stat').isspace():
                stats[m.group('stat').strip()] = m.group('desc').strip()
                previous = m.group('stat').strip()
            elif m.group('desc'):
                stats[previous] += " {0}".format(m.group('desc').strip())

pprint.pprint(stats)
