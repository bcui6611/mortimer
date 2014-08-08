import re
import urllib2


def get_stats_desc():
    ''' The stats.org file is a copy of the following file from the ep-engine repository
        https://raw.githubusercontent.com/membase/ep-engine/master/docs/stats.org'''
    
    stats_file = open('./resources/stats.org', 'r')
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
    stats_file.close()
    return statsdesc
