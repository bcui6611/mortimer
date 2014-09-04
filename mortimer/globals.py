#
# Some global objects used between mortimer's objects.
#

messageq = {}

versionnumber = 2.0

loading_file = False

sessionData = {'smoothing-window': 0}

# We hang multi process related data/queues etc... off this dictionary
processes = {}

# It's a big map:
#     {"filename"
#      {"bucketname"
#       [{:stat1 val1 :stat2 val2}
#        {:stat2 val3 :stat2 val4}]}}
stats = dict()
