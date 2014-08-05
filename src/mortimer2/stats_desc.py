import re
import urllib2


def get_stats_desc():
    stats_file = urllib2.urlopen('https://raw.githubusercontent.com/membase/ep-engine/master/docs/stats.org')
    statsdesc = {}
    previous = None
    for line in stats_file:
        m = re.match("^\| .*", line)
        if m:
            m = re.match("^\| Stat.*", line)
            n = re.match("^\| ---.*", line)
            o = re.match("^\|.*?\|.*?\|.*?\|", line)
            if m or n or o:
                next
            m = re.match("^\|(.*?)\| (.*?)\|", line)
            if m:
                stat = m.group(1)
                stat = stat.replace("\"", "")
                desc = m.group(2)
                desc = desc.replace("\"", "")
                if stat and not stat.isspace():
                    statsdesc[stat.strip()] = desc.strip()
                    previous = stat.strip()
                elif desc:
                    statsdesc[previous] += " {0}".format(desc.strip())
    return statsdesc
