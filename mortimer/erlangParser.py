#!/usr/bin/env python2.7

from __future__ import print_function
import sys
import time

try:
    from pyparsing import *
except ImportError:
    is_pypy = '__pypy__' in sys.builtin_module_names
    print("ERROR: erlangParser requires the 'pyparsing' module. Install using:\n")
    if is_pypy:
        print("    pip_pypy install pyparsing\n")
    else:
        print("    pip install pyparsing\n"
              "or\n"
              "    easy_install pyparsing\n", file=sys.stderr)
    exit(1)

TRUE = Keyword("true").setParseAction( replaceWith(True) )
FALSE = Keyword("false").setParseAction( replaceWith(False) )
NULL = Keyword("null").setParseAction( replaceWith(None) )

# Erlang config file definition:
erlangQuotedAtom = sglQuotedString.setParseAction( removeQuotes )
erlangRegExAtom = Regex(r'[a-z][a-z0-9_]+')
erlangAtom = ( erlangRegExAtom | erlangQuotedAtom )
erlangString = Regex(r'"(?:[^"\\]|(?:"")|(?:\\x[0-9a-fA-F]+)|(?:\\.))*"').setName("string enclosed in double quotes")

erlangBitString = Suppress('<<') + Optional(erlangString) + Suppress('>>')
erlangNumber = Regex(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?')
erlangPid = Regex("<\d+\.\d+\.\d+>")
erlangConfig = Forward()
erlangValue = Forward()
erlangList = Forward()

erlangElements = delimitedList( erlangValue )
erlangCSList = Suppress('[') + Optional(erlangElements) + Suppress(']')
erlangHeadTailList = Suppress('[') + erlangValue + Suppress('|') + erlangValue + Suppress(']')
erlangList <<= Group( erlangCSList | erlangHeadTailList )
erlangTuple = Group( Suppress('{') + Optional(erlangElements) + Suppress('}') )

erlangDictKey = erlangAtom | erlangBitString
erlangTaggedTuple = Suppress('{') + Group( erlangDictKey + Suppress(',') + erlangValue ) + Suppress('}')
erlangTaggedTupleList = delimitedList( erlangTaggedTuple )
erlangDict = Group( Suppress('[') + Dict( erlangTaggedTupleList ) + Suppress(']') )

erlangValue <<= ( erlangAtom | erlangNumber | erlangString |
                  erlangBitString | erlangPid | erlangTaggedTuple |
                  erlangTuple | erlangDict | erlangList )


erlangConfig << Dict( Suppress('[') + Optional(erlangElements) + Suppress(']') )

def convertNumbers(s,l,toks):
    n = toks[0]
    try:
        return int(n)
    except ValueError, ve:
        return float(n)

erlangNumber.setParseAction( convertNumbers )
erlangString.setParseAction( removeQuotes )

def listToTuple ( l ):
    """Convert a list (and any sublists) to a tuple."""
    for index, val in enumerate(l):
        if isinstance(val, list):
            l[index] = tuple(val)
    return tuple(l)

def convertToDict( p ):
    """Converts a ParseResults 'dict' (as returned by asDict()) into a
    proper dictionary."""

    # Check for a ParseResult which is actually a list (i.e. all values are
    # empty)
    if not p.keys():
        out = []
        for item in p:
            if isinstance( item, ParseResults):
                out.append(convertToDict(item))
            else:
                out.append(item)
        return out
    else:
        out = {}
        for k in p.keys():
            v = p[k]
            if isinstance( k, ParseResults):
                k = listToTuple(k.asList())
            if isinstance( v, ParseResults):
                v = convertToDict(v)
            out[k] = v
        return out


def parseErlangConfig(string):
    """Given Erlang config data in the specified string, parse it."""
    try:
        config = erlangConfig.parseString(string)
        # Convert to plain dict (so it can be pickled when using
        # multiprocessing).
        config = convertToDict(config)
        return config
    except ParseException, err:
        print(err.line, file=sys.stderr)
        print(" "*(err.column-1) + "^", file=sys.stderr)
        print(err, file=sys.stderr)
        raise

def parseErlangValue(string):
    """Given Erlang value, parse and return as Python dict."""
    try:
        d = erlangValue.parseString(string)
        return convertToDict(d)
    except ParseException, err:
        print(err.line, file=sys.stderr)
        print(" "*(err.column-1) + "^", file=sys.stderr)
        print(err, file=sys.stderr)
        raise


if __name__ == "__main__":
    testdata = """
[{'ns_1@ldsrptibemsp001.ladsys.net',
     [{last_heard,{1408,775909,362385}},
      {now,{1408,775909,356046}},
      {active_buckets,["Content","Sportsbook"]},
      {ready_buckets,["Content","Sportsbook"]},
      {status_latency,6041},
      {outgoing_replications_safeness_level,
          [{"Content",green},{"Sportsbook",green}]},
      {incoming_replications_conf_hashes,
          [{"Content",
            [{'ns_1@ldsrptibemsp003.ladsys.net',126600017},
             {'ns_1@ldsrptibemsp004.ladsys.net',105096953}]},
           {"Sportsbook",
            [{'ns_1@ldsrptibemsp003.ladsys.net',71126298},
             {'ns_1@ldsrptibemsp004.ladsys.net',69314512}]}]},
      {local_tasks,
          [[{pid,<<"<0.3210.6457>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getSelectionsFromMarket">>,
                 <<"_design/dev_getSelectionsFromMarket">>]},
            {indexer_type,replica},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"cfa5df9b2f45729865064e0138eed91b">>},
            {started_on,1408775909},
            {total_changes,5001},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.3216.6457>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getNextRaces">>,<<"_design/dev_getNextRaces">>]},
            {indexer_type,replica},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"c529d6bcec2d8a98e44d633a3d3c053c">>},
            {started_on,1408775909},
            {total_changes,5001},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.3267.6457>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getSelectionsFromEvent">>,
                 <<"_design/dev_getSelectionsFromEvent">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"f703bc269018ac71b8226ab8febfcd04">>},
            {started_on,1408775909},
            {total_changes,1},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.3317.6457>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getEventsForType">>,
                 <<"_design/dev_getEventsForType">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"bdb667a324d7c3b448cb0927a1eed4ed">>},
            {started_on,1408775909},
            {total_changes,5},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.3333.6457>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getLiveEventsForSport">>,
                 <<"_design/dev_getLiveEventsForSport">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"540a7c6b56f096a01a39922f4747a0ec">>},
            {started_on,1408775909},
            {total_changes,7},
            {type,indexer},
            {updated_on,1408775909}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Sportsbook/Sportsbook_AU">>},
            {errors,[]},
            {changes_left,6},
            {docs_checked,15568286},
            {docs_written,15567169},
            {docs_opt_repd,666873},
            {data_replicated,15499639183},
            {active_vbreps,6},
            {waiting_vbreps,0},
            {time_working,7364417},
            {time_committing,161902},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,28},
            {bandwidth_usage,28437},
            {meta_latency_aggr,7283},
            {meta_latency_wt,24},
            {docs_latency_aggr,7434},
            {docs_latency_wt,24}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Content/Content_AU">>},
            {errors,[]},
            {changes_left,0},
            {docs_checked,1736540},
            {docs_written,1736347},
            {docs_opt_repd,9},
            {data_replicated,2250153318},
            {active_vbreps,0},
            {waiting_vbreps,0},
            {time_working,1084626},
            {time_committing,96066},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,0},
            {bandwidth_usage,0},
            {meta_latency_aggr,0},
            {meta_latency_wt,0},
            {docs_latency_aggr,0},
            {docs_latency_wt,0}]]},
      {memory,
          [{total,788627384},
           {processes,469386832},
           {processes_used,468397488},
           {system,319240552},
           {atom,1371777},
           {atom_used,1347604},
           {binary,43865520},
           {code,13729530},
           {ets,246229664}]},
      {system_memory_data,
          [{system_total_memory,168881328128},
           {free_swap,8589926400},
           {total_swap,8589926400},
           {cached_memory,18983817216},
           {buffered_memory,4289507328},
           {free_memory,61908844544},
           {total_memory,168881328128}]},
      {node_storage_conf,
          [{db_path,
               "/opt/tibco/data/instance_AM/couchbase_db/ldsrptibemsp001"},
           {index_path,"/opt/couchbase/var/lib/couchbase/data"}]},
      {statistics,
          [{wall_clock,{1477623211,5002}},
           {context_switches,{76529483512,0}},
           {garbage_collection,{10311922334,30895490676434,0}},
           {io,{{input,23929355160601},{output,4542611997678}}},
           {reductions,{10509026147644,47580788}},
           {run_queue,0},
           {runtime,{2406666260,11690}},
           {run_queues,
               {0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                0}}]},
      {system_stats,
          [{cpu_utilization_rate,10.9375},
           {swap_total,8589926400},
           {swap_used,0},
           {mem_total,168881328128},
           {mem_free,85165658112}]},
      {interesting_stats,
          [{cmd_get,1208.2082082082081},
           {couch_docs_actual_disk_size,5960869728},
           {couch_docs_data_size,4207169561},
           {couch_views_actual_disk_size,395674232},
           {couch_views_data_size,159238279},
           {curr_items,3543379},
           {curr_items_tot,7087328},
           {ep_bg_fetched,0.0},
           {get_hits,1206.2062062062062},
           {mem_used,6121546472},
           {ops,1209.2092092092091},
           {vb_replica_curr_items,3543949}]},
      {per_bucket_interesting_stats,
          [{"Sportsbook",
            [{cmd_get,1208.2082082082081},
             {couch_docs_actual_disk_size,5781417325},
             {couch_docs_data_size,4083738421},
             {couch_views_actual_disk_size,393206724},
             {couch_views_data_size,156921483},
             {curr_items,3474896},
             {curr_items_tot,6950490},
             {ep_bg_fetched,0.0},
             {get_hits,1206.2062062062062},
             {mem_used,5916818544},
             {ops,1209.2092092092091},
             {vb_replica_curr_items,3475594}]},
           {"Content",
            [{cmd_get,0.0},
             {couch_docs_actual_disk_size,179452403},
             {couch_docs_data_size,123431140},
             {couch_views_actual_disk_size,2467508},
             {couch_views_data_size,2316796},
             {curr_items,68483},
             {curr_items_tot,136838},
             {ep_bg_fetched,0.0},
             {get_hits,0.0},
             {mem_used,204727928},
             {ops,0.0},
             {vb_replica_curr_items,68355}]}]},
      {processes_stats,
          [{<<"proc/(main)beam.smp/cpu_utilization">>,1000},
           {<<"proc/(main)beam.smp/major_faults">>,0},
           {<<"proc/(main)beam.smp/major_faults_raw">>,0},
           {<<"proc/(main)beam.smp/mem_resident">>,1758642176},
           {<<"proc/(main)beam.smp/mem_share">>,41963520},
           {<<"proc/(main)beam.smp/mem_size">>,4364124160},
           {<<"proc/(main)beam.smp/minor_faults">>,29967},
           {<<"proc/(main)beam.smp/minor_faults_raw">>,35484125980},
           {<<"proc/(main)beam.smp/page_faults">>,29967},
           {<<"proc/(main)beam.smp/page_faults_raw">>,35484125980},
           {<<"proc/beam.smp/cpu_utilization">>,0},
           {<<"proc/beam.smp/major_faults">>,0},
           {<<"proc/beam.smp/major_faults_raw">>,0},
           {<<"proc/beam.smp/mem_resident">>,28565504},
           {<<"proc/beam.smp/mem_share">>,2215936},
           {<<"proc/beam.smp/mem_size">>,412430336},
           {<<"proc/beam.smp/minor_faults">>,0},
           {<<"proc/beam.smp/minor_faults_raw">>,8907},
           {<<"proc/beam.smp/page_faults">>,0},
           {<<"proc/beam.smp/page_faults_raw">>,8907},
           {<<"proc/memcached/cpu_utilization">>,0},
           {<<"proc/memcached/major_faults">>,0},
           {<<"proc/memcached/major_faults_raw">>,0},
           {<<"proc/memcached/mem_resident">>,6564708352},
           {<<"proc/memcached/mem_share">>,3354624},
           {<<"proc/memcached/mem_size">>,6864855040},
           {<<"proc/memcached/minor_faults">>,0},
           {<<"proc/memcached/minor_faults_raw">>,1619544},
           {<<"proc/memcached/page_faults">>,0},
           {<<"proc/memcached/page_faults_raw">>,1619544}]},
      {cluster_compatibility_version,131077},
      {version,
          [{public_key,"0.13"},
           {asn1,"1.6.18"},
           {lhttpc,"1.3.0"},
           {ale,"8ca6d2a"},
           {os_mon,"2.2.7"},
           {couch_set_view,"1.2.0a-a425d97-git"},
           {compiler,"4.7.5"},
           {inets,"5.7.1"},
           {couch,"1.2.0a-a425d97-git"},
           {mapreduce,"1.0.0"},
           {couch_index_merger,"1.2.0a-a425d97-git"},
           {kernel,"2.14.5"},
           {crypto,"2.0.4"},
           {ssl,"4.1.6"},
           {sasl,"2.1.10"},
           {couch_view_parser,"1.0.0"},
           {ns_server,"2.5.1-1083-rel-enterprise"},
           {mochiweb,"2.4.2"},
           {syntax_tools,"1.6.7.1"},
           {xmerl,"1.2.10"},
           {oauth,"7d85d3ef"},
           {stdlib,"1.17.5"}]},
      {supported_compat_version,[2,5]},
      {advertised_version,[2,5,1]},
      {system_arch,"x86_64-unknown-linux-gnu"},
      {wall_clock,1477623},
      {memory_data,{168881328128,106939338752,{<0.8750.0>,19371648}}},
      {disk_data,
          [{"/",16251816,48},
           {"/var",42501320,5},
           {"/home",8125880,22},
           {"/tmp",2031440,4},
           {"/opt/tibco",30472188,7},
           {"/var/log/tibco",30472188,11},
           {"/boot",101086,21},
           {"/dev/shm",82461584,0},
           {"/dev/vx",4,0},
           {"/opt/tibco/data/instance_AM",104766464,21},
           {"/opt/tibco/data/instance_F",104766464,1},
           {"/opt/tibco/data/instance_C",104766464,1},
           {"/opt/tibco/data/instance_E",104766464,1},
           {"/opt/tibco/data/instance_D",104766464,1},
           {"/opt/tibco/data/instance_A",104766464,1},
           {"/opt/tibco/data/instance_B",104766464,1}]},
      {meminfo,
          <<"MemTotal:     164923172 kB\nMemFree:      60457856 kB\nBuffers:       4188972 kB\nCached:       18538884 kB\nSwapCached:          0 kB\nActive:       29559412 kB\nInactive:      3842748 kB\nHighTotal:           0 kB\nHighFree:            0 kB\nLowTotal:     164923172 kB\nLowFree:      60457856 kB\nSwapTotal:     8388600 kB\nSwapFree:      8388600 kB\nDirty:           15568 kB\nWriteback:           0 kB\nAnonPages:    10446412 kB\nMapped:         113676 kB\nSlab:         70388128 kB\nPageTables:      31020 kB\nNFS_Unstable:        0 kB\nBounce:              0 kB\nCommitLimit:  90850184 kB\nCommitted_AS: 15025924 kB\nVmallocTotal: 34359738367 kB\nVmallocUsed:    637888 kB\nVmallocChunk: 34359097915 kB\nHugePages_Total:     0\nHugePages_Free:      0\nHugePages_Rsvd:      0\nHugepagesize:     2048 kB\n">>}]},
 {'ns_1@ldsrptibemsp003.ladsys.net',
     [{last_heard,{1408,775909,383202}},
      {now,{1408,775909,388049}},
      {active_buckets,["Content","Sportsbook"]},
      {ready_buckets,["Content","Sportsbook"]},
      {status_latency,4555},
      {outgoing_replications_safeness_level,
          [{"Content",green},{"Sportsbook",green}]},
      {incoming_replications_conf_hashes,
          [{"Content",
            [{'ns_1@ldsrptibemsp001.ladsys.net',90481693},
             {'ns_1@ldsrptibemsp004.ladsys.net',12754605}]},
           {"Sportsbook",
            [{'ns_1@ldsrptibemsp001.ladsys.net',86256472},
             {'ns_1@ldsrptibemsp004.ladsys.net',77417352}]}]},
      {local_tasks,
          [[{pid,<<"<0.27250.6519>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getEventsForType">>,
                 <<"_design/dev_getEventsForType">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"bdb667a324d7c3b448cb0927a1eed4ed">>},
            {started_on,1408775909},
            {total_changes,6},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.27266.6519>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getLiveEventsForSport">>,
                 <<"_design/dev_getLiveEventsForSport">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"540a7c6b56f096a01a39922f4747a0ec">>},
            {started_on,1408775909},
            {total_changes,9},
            {type,indexer},
            {updated_on,1408775909}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Sportsbook/Sportsbook_AU">>},
            {errors,[]},
            {changes_left,10},
            {docs_checked,15573630},
            {docs_written,15572443},
            {docs_opt_repd,665144},
            {data_replicated,15507890395},
            {active_vbreps,9},
            {waiting_vbreps,0},
            {time_working,7415548},
            {time_committing,160265},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,9},
            {bandwidth_usage,8417},
            {meta_latency_aggr,10681},
            {meta_latency_wt,36},
            {docs_latency_aggr,10134},
            {docs_latency_wt,36}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Content/Content_AU">>},
            {errors,[]},
            {changes_left,1},
            {docs_checked,1701209},
            {docs_written,1700930},
            {docs_opt_repd,2},
            {data_replicated,2195986242},
            {active_vbreps,1},
            {waiting_vbreps,0},
            {time_working,1073403},
            {time_committing,92745},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,0},
            {bandwidth_usage,0},
            {meta_latency_aggr,1121},
            {meta_latency_wt,4},
            {docs_latency_aggr,1124},
            {docs_latency_wt,4}]]},
      {memory,
          [{total,943632656},
           {processes,622866776},
           {processes_used,622125824},
           {system,320765880},
           {atom,1370969},
           {atom_used,1346865},
           {binary,48981568},
           {code,13743939},
           {ets,242723536}]},
      {system_memory_data,
          [{system_total_memory,168881328128},
           {free_swap,8589926400},
           {total_swap,8589926400},
           {cached_memory,44578971648},
           {buffered_memory,5089595392},
           {free_memory,89529049088},
           {total_memory,168881328128}]},
      {node_storage_conf,
          [{db_path,
               "/opt/tibco/data/instance_AM/couchbase_db/ldsrptibemsp003"},
           {index_path,"/opt/couchbase/var/lib/couchbase/data"}]},
      {statistics,
          [{wall_clock,{1477832552,5001}},
           {context_switches,{76526421218,0}},
           {garbage_collection,{10612307139,32123555929005,0}},
           {io,{{input,24241235678159},{output,4509871001272}}},
           {reductions,{11086605568970,47431409}},
           {run_queue,1},
           {runtime,{2338838530,9740}},
           {run_queues,
               {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                0}}]},
      {system_stats,
          [{cpu_utilization_rate,11.298904538341159},
           {swap_total,8589926400},
           {swap_used,0},
           {mem_total,168881328128},
           {mem_free,139182800896}]},
      {interesting_stats,
          [{cmd_get,1242.2422422422421},
           {couch_docs_actual_disk_size,6047712869},
           {couch_docs_data_size,4192506886},
           {couch_views_actual_disk_size,362174683},
           {couch_views_data_size,159216662},
           {curr_items,3534056},
           {curr_items_tot,7067466},
           {ep_bg_fetched,0.0},
           {get_hits,1239.2392392392392},
           {mem_used,6105053768},
           {ops,1246.246246246246},
           {vb_replica_curr_items,3533410}]},
      {per_bucket_interesting_stats,
          [{"Sportsbook",
            [{cmd_get,1239.2392392392392},
             {couch_docs_actual_disk_size,5895691518},
             {couch_docs_data_size,4069937500},
             {couch_views_actual_disk_size,359671601},
             {couch_views_data_size,156971481},
             {curr_items,3465687},
             {curr_items_tot,6930970},
             {ep_bg_fetched,0.0},
             {get_hits,1236.2362362362362},
             {mem_used,5901082208},
             {ops,1243.2432432432431},
             {vb_replica_curr_items,3465283}]},
           {"Content",
            [{cmd_get,3.003003003003003},
             {couch_docs_actual_disk_size,152021351},
             {couch_docs_data_size,122569386},
             {couch_views_actual_disk_size,2503082},
             {couch_views_data_size,2245181},
             {curr_items,68369},
             {curr_items_tot,136496},
             {ep_bg_fetched,0.0},
             {get_hits,3.003003003003003},
             {mem_used,203971560},
             {ops,3.003003003003003},
             {vb_replica_curr_items,68127}]}]},
      {processes_stats,
          [{<<"proc/(main)beam.smp/cpu_utilization">>,750},
           {<<"proc/(main)beam.smp/major_faults">>,0},
           {<<"proc/(main)beam.smp/major_faults_raw">>,0},
           {<<"proc/(main)beam.smp/mem_resident">>,1890983936},
           {<<"proc/(main)beam.smp/mem_share">>,41963520},
           {<<"proc/(main)beam.smp/mem_size">>,4495339520},
           {<<"proc/(main)beam.smp/minor_faults">>,41201},
           {<<"proc/(main)beam.smp/minor_faults_raw">>,34570583360},
           {<<"proc/(main)beam.smp/page_faults">>,41201},
           {<<"proc/(main)beam.smp/page_faults_raw">>,34570583360},
           {<<"proc/beam.smp/cpu_utilization">>,0},
           {<<"proc/beam.smp/major_faults">>,0},
           {<<"proc/beam.smp/major_faults_raw">>,0},
           {<<"proc/beam.smp/mem_resident">>,28344320},
           {<<"proc/beam.smp/mem_share">>,2215936},
           {<<"proc/beam.smp/mem_size">>,411930624},
           {<<"proc/beam.smp/minor_faults">>,0},
           {<<"proc/beam.smp/minor_faults_raw">>,8883},
           {<<"proc/beam.smp/page_faults">>,0},
           {<<"proc/beam.smp/page_faults_raw">>,8883},
           {<<"proc/memcached/cpu_utilization">>,0},
           {<<"proc/memcached/major_faults">>,0},
           {<<"proc/memcached/major_faults_raw">>,0},
           {<<"proc/memcached/mem_resident">>,6551195648},
           {<<"proc/memcached/mem_share">>,3354624},
           {<<"proc/memcached/mem_size">>,6849122304},
           {<<"proc/memcached/minor_faults">>,0},
           {<<"proc/memcached/minor_faults_raw">>,1599661},
           {<<"proc/memcached/page_faults">>,0},
           {<<"proc/memcached/page_faults_raw">>,1599661}]},
      {cluster_compatibility_version,131077},
      {version,
          [{public_key,"0.13"},
           {asn1,"1.6.18"},
           {lhttpc,"1.3.0"},
           {ale,"8ca6d2a"},
           {os_mon,"2.2.7"},
           {couch_set_view,"1.2.0a-a425d97-git"},
           {compiler,"4.7.5"},
           {inets,"5.7.1"},
           {couch,"1.2.0a-a425d97-git"},
           {mapreduce,"1.0.0"},
           {couch_index_merger,"1.2.0a-a425d97-git"},
           {kernel,"2.14.5"},
           {crypto,"2.0.4"},
           {ssl,"4.1.6"},
           {sasl,"2.1.10"},
           {couch_view_parser,"1.0.0"},
           {ns_server,"2.5.1-1083-rel-enterprise"},
           {mochiweb,"2.4.2"},
           {syntax_tools,"1.6.7.1"},
           {xmerl,"1.2.10"},
           {oauth,"7d85d3ef"},
           {stdlib,"1.17.5"}]},
      {supported_compat_version,[2,5]},
      {advertised_version,[2,5,1]},
      {system_arch,"x86_64-unknown-linux-gnu"},
      {wall_clock,1477832},
      {memory_data,{168881328128,79353700352,{<13070.8604.0>,205624840}}},
      {disk_data,
          [{"/",16251816,45},
           {"/var",42501320,4},
           {"/home",8125880,14},
           {"/tmp",2031440,22},
           {"/opt/tibco",30472188,12},
           {"/var/log/tibco",30472188,100},
           {"/boot",101086,21},
           {"/dev/shm",82461584,0},
           {"/dev/vx",4,0},
           {"/opt/tibco/data/instance_AM",104766464,21},
           {"/opt/tibco/data/instance_E",104766464,1},
           {"/opt/tibco/data/instance_C",104766464,1},
           {"/opt/tibco/data/instance_B",104766464,1},
           {"/opt/tibco/data/instance_A",104766464,1},
           {"/opt/tibco/data/instance_D",104766464,1},
           {"/opt/tibco/data/instance_F",104766464,1}]},
      {meminfo,
          <<"MemTotal:     164923172 kB\nMemFree:      87430712 kB\nBuffers:       4970308 kB\nCached:       43534152 kB\nSwapCached:          0 kB\nActive:       55566720 kB\nInactive:      4423624 kB\nHighTotal:           0 kB\nHighFree:            0 kB\nLowTotal:     164923172 kB\nLowFree:      87430712 kB\nSwapTotal:     8388600 kB\nSwapFree:      8388600 kB\nDirty:           36436 kB\nWriteback:          24 kB\nAnonPages:    11242804 kB\nMapped:         113772 kB\nSlab:         16753520 kB\nPageTables:      32608 kB\nNFS_Unstable:        0 kB\nBounce:              0 kB\nCommitLimit:  90850184 kB\nCommitted_AS: 15624200 kB\nVmallocTotal: 34359738367 kB\nVmallocUsed:    637888 kB\nVmallocChunk: 34359097915 kB\nHugePages_Total:     0\nHugePages_Free:      0\nHugePages_Rsvd:      0\nHugepagesize:     2048 kB\n">>}]},
 {'ns_1@ldsrptibemsp004.ladsys.net',
     [{last_heard,{1408,775909,656537}},
      {now,{1408,775909,651354}},
      {active_buckets,["Sportsbook","Content"]},
      {ready_buckets,["Sportsbook","Content"]},
      {status_latency,4315},
      {outgoing_replications_safeness_level,
          [{"Content",green},{"Sportsbook",green}]},
      {incoming_replications_conf_hashes,
          [{"Content",
            [{'ns_1@ldsrptibemsp001.ladsys.net',114849207},
             {'ns_1@ldsrptibemsp003.ladsys.net',17324431}]},
           {"Sportsbook",
            [{'ns_1@ldsrptibemsp001.ladsys.net',114849207},
             {'ns_1@ldsrptibemsp003.ladsys.net',44682831}]}]},
      {local_tasks,
          [[{pid,<<"<0.28071.6290>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getUpcomingEventsForClass">>,
                 <<"_design/dev_getUpcomingEventsForClass">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"5d6954eeaa5d7c19974c2abd99d25754">>},
            {started_on,1408775909},
            {total_changes,8},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.28084.6290>">>},
            {changes_done,0},
            {design_documents,
                [<<"_design/getSelectionsFromEvent">>,
                 <<"_design/dev_getSelectionsFromEvent">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"f703bc269018ac71b8226ab8febfcd04">>},
            {started_on,1408775909},
            {total_changes,1},
            {type,indexer},
            {updated_on,1408775909}],
           [{pid,<<"<0.28103.6290>">>},
            {changes_done,0},
            {design_documents,[<<"_design/result">>,<<"_design/dev_result">>]},
            {indexer_type,main},
            {initial_build,false},
            {progress,0},
            {set,<<"Sportsbook">>},
            {signature,<<"c22287f1d8bfd2f670fcca38bdc753e0">>},
            {started_on,1408775909},
            {total_changes,1},
            {type,indexer},
            {updated_on,1408775909}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Sportsbook/Sportsbook_AU">>},
            {errors,[]},
            {changes_left,7},
            {docs_checked,15529030},
            {docs_written,15527569},
            {docs_opt_repd,664919},
            {data_replicated,15458082677},
            {active_vbreps,7},
            {waiting_vbreps,0},
            {time_working,7386269},
            {time_committing,160064},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,7},
            {bandwidth_usage,6365},
            {meta_latency_aggr,8995},
            {meta_latency_wt,28},
            {docs_latency_aggr,8426},
            {docs_latency_wt,28}],
           [{type,xdcr},
            {id,<<"010dd65dd0dc50f18b30b46faa0509b5/Content/Content_AU">>},
            {errors,[]},
            {changes_left,2},
            {docs_checked,1693397},
            {docs_written,1693070},
            {docs_opt_repd,5},
            {data_replicated,2182376955},
            {active_vbreps,2},
            {waiting_vbreps,0},
            {time_working,1065396},
            {time_committing,92433},
            {num_checkpoints,10},
            {num_failedckpts,0},
            {docs_rep_queue,0},
            {size_rep_queue,0},
            {rate_replication,0},
            {bandwidth_usage,0},
            {meta_latency_aggr,2241},
            {meta_latency_wt,8},
            {docs_latency_aggr,2246},
            {docs_latency_wt,8}]]},
      {memory,
          [{total,861527016},
           {processes,541837760},
           {processes_used,541040608},
           {system,319689256},
           {atom,1368545},
           {atom_used,1343017},
           {binary,44415944},
           {code,13650938},
           {ets,246282760}]},
      {system_memory_data,
          [{system_total_memory,168881328128},
           {free_swap,8589926400},
           {total_swap,8589926400},
           {cached_memory,21442121728},
           {buffered_memory,4474032128},
           {free_memory,67019137024},
           {total_memory,168881328128}]},
      {node_storage_conf,
          [{db_path,
               "/opt/tibco/data/instance_AM/couchbase_db/ldsrptibemsp004"},
           {index_path,"/opt/couchbase/var/lib/couchbase/data"}]},
      {statistics,
          [{wall_clock,{1478033168,5001}},
           {context_switches,{76155929833,0}},
           {garbage_collection,{10580526965,31487817516428,0}},
           {io,{{input,23843271568424},{output,4529668528842}}},
           {reductions,{10384196671140,39618101}},
           {run_queue,2},
           {runtime,{2386177010,9380}},
           {run_queues,
               {0,0,0,0,0,0,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                0}}]},
      {system_stats,
          [{cpu_utilization_rate,8.03125},
           {swap_total,8589926400},
           {swap_used,0},
           {mem_total,168881328128},
           {mem_free,92925681664}]},
      {interesting_stats,
          [{cmd_get,419.5804195804196},
           {couch_docs_actual_disk_size,5947066050},
           {couch_docs_data_size,4197671948},
           {couch_views_actual_disk_size,356758339},
           {couch_views_data_size,159911712},
           {curr_items,3533449},
           {curr_items_tot,7066975},
           {ep_bg_fetched,0.0},
           {get_hits,419.5804195804196},
           {mem_used,6104462856},
           {ops,419.5804195804196},
           {vb_replica_curr_items,3533526}]},
      {per_bucket_interesting_stats,
          [{"Sportsbook",
            [{cmd_get,401.5984015984016},
             {couch_docs_actual_disk_size,5795831073},
             {couch_docs_data_size,4075172234},
             {couch_views_actual_disk_size,354171928},
             {couch_views_data_size,157687474},
             {curr_items,3465661},
             {curr_items_tot,6931029},
             {ep_bg_fetched,0.0},
             {get_hits,401.5984015984016},
             {mem_used,5901202432},
             {ops,401.5984015984016},
             {vb_replica_curr_items,3465368}]},
           {"Content",
            [{cmd_get,17.982017982017982},
             {couch_docs_actual_disk_size,151234977},
             {couch_docs_data_size,122499714},
             {couch_views_actual_disk_size,2586411},
             {couch_views_data_size,2224238},
             {curr_items,67788},
             {curr_items_tot,135946},
             {ep_bg_fetched,0.0},
             {get_hits,17.982017982017982},
             {mem_used,203260424},
             {ops,17.982017982017982},
             {vb_replica_curr_items,68158}]}]},
      {processes_stats,
          [{<<"proc/(main)beam.smp/cpu_utilization">>,750},
           {<<"proc/(main)beam.smp/major_faults">>,0},
           {<<"proc/(main)beam.smp/major_faults_raw">>,0},
           {<<"proc/(main)beam.smp/mem_resident">>,1785864192},
           {<<"proc/(main)beam.smp/mem_share">>,41963520},
           {<<"proc/(main)beam.smp/mem_size">>,4392157184},
           {<<"proc/(main)beam.smp/minor_faults">>,27280},
           {<<"proc/(main)beam.smp/minor_faults_raw">>,34277454713},
           {<<"proc/(main)beam.smp/page_faults">>,27280},
           {<<"proc/(main)beam.smp/page_faults_raw">>,34277454713},
           {<<"proc/beam.smp/cpu_utilization">>,0},
           {<<"proc/beam.smp/major_faults">>,0},
           {<<"proc/beam.smp/major_faults_raw">>,0},
           {<<"proc/beam.smp/mem_resident">>,29171712},
           {<<"proc/beam.smp/mem_share">>,2285568},
           {<<"proc/beam.smp/mem_size">>,412930048},
           {<<"proc/beam.smp/minor_faults">>,0},
           {<<"proc/beam.smp/minor_faults_raw">>,8956},
           {<<"proc/beam.smp/page_faults">>,0},
           {<<"proc/beam.smp/page_faults_raw">>,8956},
           {<<"proc/memcached/cpu_utilization">>,0},
           {<<"proc/memcached/major_faults">>,0},
           {<<"proc/memcached/major_faults_raw">>,0},
           {<<"proc/memcached/mem_resident">>,6547234816},
           {<<"proc/memcached/mem_share">>,3354624},
           {<<"proc/memcached/mem_size">>,6847029248},
           {<<"proc/memcached/minor_faults">>,0},
           {<<"proc/memcached/minor_faults_raw">>,1598827},
           {<<"proc/memcached/page_faults">>,0},
           {<<"proc/memcached/page_faults_raw">>,1598827}]},
      {cluster_compatibility_version,131077},
      {version,
          [{public_key,"0.13"},
           {asn1,"1.6.18"},
           {lhttpc,"1.3.0"},
           {ale,"8ca6d2a"},
           {os_mon,"2.2.7"},
           {couch_set_view,"1.2.0a-a425d97-git"},
           {compiler,"4.7.5"},
           {inets,"5.7.1"},
           {couch,"1.2.0a-a425d97-git"},
           {mapreduce,"1.0.0"},
           {couch_index_merger,"1.2.0a-a425d97-git"},
           {kernel,"2.14.5"},
           {crypto,"2.0.4"},
           {ssl,"4.1.6"},
           {sasl,"2.1.10"},
           {couch_view_parser,"1.0.0"},
           {ns_server,"2.5.1-1083-rel-enterprise"},
           {mochiweb,"2.4.2"},
           {syntax_tools,"1.6.7.1"},
           {xmerl,"1.2.10"},
           {oauth,"7d85d3ef"},
           {stdlib,"1.17.5"}]},
      {supported_compat_version,[2,5]},
      {advertised_version,[2,5,1]},
      {system_arch,"x86_64-unknown-linux-gnu"},
      {wall_clock,1478033},
      {memory_data,{168881328128,101871919104,{<13059.8605.0>,91014512}}},
      {disk_data,
          [{"/",16251816,44},
           {"/var",42501320,6},
           {"/home",8125880,8},
           {"/tmp",2031440,4},
           {"/opt/tibco",30472188,22},
           {"/var/log/tibco",30472188,10},
           {"/boot",101086,21},
           {"/dev/shm",82461584,0},
           {"/dev/vx",4,0},
           {"/opt/tibco/data/instance_C",104766464,1},
           {"/opt/tibco/data/instance_AM",104766464,21},
           {"/opt/tibco/data/instance_D",104766464,1},
           {"/opt/tibco/data/instance_E",104766464,1},
           {"/opt/tibco/data/instance_B",104766464,1},
           {"/opt/tibco/data/instance_F",104766464,1},
           {"/opt/tibco/data/instance_A",104766464,1}]},
      {meminfo,
          <<"MemTotal:     164923172 kB\nMemFree:      65448996 kB\nBuffers:       4369172 kB\nCached:       20939572 kB\nSwapCached:          0 kB\nActive:       32957072 kB\nInactive:      3707132 kB\nHighTotal:           0 kB\nHighFree:            0 kB\nLowTotal:     164923172 kB\nLowFree:      65448996 kB\nSwapTotal:     8388600 kB\nSwapFree:      8388600 kB\nDirty:           63472 kB\nWriteback:           0 kB\nAnonPages:    11162332 kB\nMapped:         113748 kB\nSlab:         62087964 kB\nPageTables:      32860 kB\nNFS_Unstable:        0 kB\nBounce:              0 kB\nCommitLimit:  90850184 kB\nCommitted_AS: 18242644 kB\nVmallocTotal: 34359738367 kB\nVmallocUsed:    637888 kB\nVmallocChunk: 34359097915 kB\nHugePages_Total:     0\nHugePages_Free:      0\nHugePages_Rsvd:      0\nHugepagesize:     2048 kB\n">>}]}]
"""
    import pprint
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            testdata = f.read()
            for i in range(100):
                result = parseErlangValue(testdata)
            #pprint.pprint( result )

    else:
        t = time.clock() 
        results = parseErlangConfig(testdata)
        process_time = time.clock() - t
        print("Took {0}".format(process_time))
        #pprint.pprint( results['ns_1@ldsrptibemsp001.ladsys.net'] )
        print
