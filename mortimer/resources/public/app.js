var app = angular.module('mortimer', ['ui.bootstrap']);
var graph = null;
var clientid = (new Date()).getTime();
var remoteUpdate = false;

app.config(function($routeProvider, $locationProvider) {
  $routeProvider.
  when('/stats/', { templateUrl: '/partials/stats.html',
                    controller: 'DataCtrl'}).
  when('/files/', { templateUrl: '/partials/files.html',
                    controller: 'FilesCtrl'}).
  otherwise({ redirectTo: '/stats/'});
});

toastr.options = {
  timeOut: 2000
};

app.factory('StatusService', function($rootScope) {
  var mws = new WebSocket("ws://" + location.host + "/status-ws");
  var status = {
    remote: {},
    session: {},
    send: function(obj) {
      mws.send(JSON.stringify(obj));
    }
  };
  mws.onmessage = function(evt) {
    var message = JSON.parse(evt.data);
    var kind = message.kind;
    if(kind == "status-update") {
      status.remote = message.data;
      $rootScope.$apply();
    }
    if(kind == "session-data") {
      status.session = message.data;
      $rootScope.$apply();
    }
    if(kind == "range-update") {
      if(graph && clientid != message.client) {
        remoteUpdate = true;
        graph.updateOptions({
          dateWindow: message.range
        });
        remoteUpdate = false;
      }
    }
    if(kind == "error" || kind == "warning") {
      if(message.extra) {
        toastr[kind](message.short);
        var toast = $("<div>").append($("<pre>").text(message.extra)).html();
        toastr[kind](toast);
      } else {
        toastr[kind](message.short);
      }
    }

  };
  return status;
})

function SaveDialogCtrl($scope, dialog) {
  $scope.save = function() {
    dialog.close({
      name: $scope.pname
    })
  };

  $scope.cancel = function() {
    dialog.close();
  }
}

function AddExprDialogCtrl($scope, $timeout, dialog) {
  $timeout(function() {
    var exprEl = document.getElementById('exprentry');
    if(exprEl) {
      exprEl.focus();
    }
  }, 10);
  $scope.add = function() {
    var stat = $scope.expr;
    if($scope.name) {
      stat += ";name=" + $scope.name;
    }
    dialog.close({
      stat: stat,
      replace: false
    });
  }

  $scope.replace = function() {
    var stat = $scope.expr;
    if($scope.name) {
      stat += ";name=" + $scope.name;
    }
    dialog.close({
      stat: stat,
      replace: true
    });
  }

  $scope.cancel = function() {
    dialog.close();
  }
}

function FilesCtrl($scope, StatusService) {
  $scope.status = StatusService;
}

function DataCtrl($scope, $http, $log, $dialog, $timeout, $document, StatusService) {
  var searchEl = document.getElementById('statsearchinput');
  Mousetrap.bind('/', function(e) {
    if(!$scope.drawerOpen) {
      $scope.$apply($scope.drawer);
    }
    searchEl.focus();
    searchEl.select();
    return false;
  });
  // blur search field on Enter
  $scope.statsearch = function() {
    searchEl.blur();
    $scope.cursorPos = 0;
  }

  Mousetrap.bind('d s', function() {
    $scope.$apply(function() {
      $scope.statfilter='';
    })
  });

  Mousetrap.bind('p', function() {
    $scope.status.send({
      kind: "session-apply",
      code: "(update-in [:smoothing-window] inc)"
    });
  });
  Mousetrap.bind('o', function() {
    $scope.status.send({
      kind: "session-apply",
      code: "(update-in [:smoothing-window] #(if (pos? %) (dec %) %))"
    });
  });
  $scope.$watch("status.session['smoothing-window']", function() {
    makechart();
  });

  Mousetrap.bind(['<','>'], function() {
    $scope.$apply($scope.drawer);
  });

  Mousetrap.bind('q', function() {
    $scope.$apply(function() {
      $scope.master = !$scope.master;
    });
  });

  var mtStatToggle = function(fun, additive) {
    return function(e) {
      var stats = $scope.filteredStats();
      var cursorPos = $scope.cursorPos;
      $scope.$apply(function() {
        var stat = stats[cursorPos];
        if(fun) {
          stat = fun + '(' + stat + ')';
        }
        if(cursorPos < 0 || cursorPos >= stats.length) return;
        $scope.statclicked(stat, {metaKey: additive});
      });
      return false;
    }
  };

  //add selected stat
  Mousetrap.bind('r', mtStatToggle('rate', false));
  //add selected stat rate
  Mousetrap.bind('ctrl+r', mtStatToggle('rate', true));
  //change to selected stat
  Mousetrap.bind('enter', mtStatToggle(null, false));
  //add selected stat rate
  Mousetrap.bind('mod+enter', mtStatToggle(null, true));


  function openExprDialog(source) {
    $scope.$apply(function() {
      var dia = $dialog.dialog({
        backdrop: false,
        templateUrl: 'partials/exprdialog.html',
        controller: 'AddExprDialogCtrl'
      }).open();

      dia.then(function(result) {
        if(!result) {
          return;
        }
        if(result.replace) {
          $scope.activeStats = {};
        }
        setupstat(result.stat, true);
      });
    });
  }
  //add stat by expression
  Mousetrap.bind('`', function() {
    openExprDialog("");
  });

  Mousetrap.bind('?', function() {
    $scope.$apply(function() {
      $dialog.dialog({
        templateUrl: 'partials/README.html'
      }).open();
    });
  });

  //stat cursor
  Mousetrap.bind(['j', 'down'], function() {
    $scope.$apply($scope.cursorDown);
    return false;
  });
  Mousetrap.bind(['k', 'up'], function() {
    $scope.$apply($scope.cursorUp);
    return false;
  });

  Mousetrap.bind('g g', function() {
    $scope.$apply(function() {
      $scope.cursorPos = 0;
    });
  });

  $scope.cursorPos = -1;
  $scope.cursorDown = function() {
    var numstats = $scope.filteredStats().length;
    if($scope.cursorPos !== false) {
      $scope.cursorPos++;
      if($scope.cursorPos >= numstats) {
        $scope.cursorPos--;
      }
    } else if(numstats > 0) {
      $scope.cursorPos = 0;
    }
  }
  $scope.cursorUp = function() {
    var numstats = $scope.filteredStats().length;
    if($scope.cursorPos !== false) {
      $scope.cursorPos--;
      if($scope.cursorPos < 0) {
        $scope.cursorPos++;
      }
    } else if(numstats > 0) {
      $scope.cursorPos = 0;
    }
  }

  $scope.bucketCursor = -1;
  Mousetrap.bind(['shift+j', 'shift+down'], function() {
    $scope.bucketCursor++;
    if($scope.bucketCursor >= $scope.status.remote.buckets.length) {
      $scope.bucketCursor = $scope.status.remote.buckets.length - 1;
    }
    var bucket;
    if(bucket = $scope.status.remote.buckets[$scope.bucketCursor]) {
      $scope.$apply(function(){
        $scope.activeBucket = bucket;
      });
    }
    return false;
  });
  Mousetrap.bind(['shift+k', 'shift+up'], function() {
    $scope.bucketCursor--;
    if($scope.bucketCursor < 0) { $scope.bucketCursor = 0; }
    var bucket;
    if(bucket = $scope.status.remote.buckets[$scope.bucketCursor]) {
      $scope.$apply(function(){
        $scope.activeBucket = bucket;
      });
    }
    return false;
  });


  $scope.fileCursor = -1;
  Mousetrap.bind(['mod+j', 'mod+down'], function() {
    $scope.fileCursor++;
    if($scope.fileCursor >= $scope.status.remote.files.length) {
      $scope.fileCursor = $scope.status.remote.files.length - 1;
    }
    var file;
    if(file = $scope.status.remote.files[$scope.fileCursor]) {
      $scope.$apply(function(){
        $scope.activeFile = file;
      });
    }
    return false;
  });
  Mousetrap.bind(['mod+k', 'mod+up'], function() {
    $scope.fileCursor--;
    if($scope.fileCursor < 0) { $scope.fileCursor = 0; }
    var file;
    if(file = $scope.status.remote.files[$scope.fileCursor]) {
      $scope.$apply(function(){
        $scope.activeFile = file;
      });
    }
    return false;
  });

  $scope.status = StatusService;
  $scope.stats = [];
  $scope.$watch('status.remote.files', function() {
    if(_.isEmpty($scope.stats)) {
     $http.get('/stats').success(function(data) {
        $scope.stats = data;
     });
    }
  });

  $scope.drawerOpen = true;
  $scope.drawer = function() {
    $scope.drawerOpen = !$scope.drawerOpen;
    $timeout(function() {
      g.resize();
    }, 510)
  }

  $timeout(function() {
    g.resize();
  }, 510);

  $scope.$watch('status.remote.loading', function() {
    $scope.loading = {};
    if(_.isEmpty($scope.status.remote.loading)
       && $scope.status.remote
       && $scope.status.remote.files) {
      $scope.activeFile = $scope.status.remote.files[0];
      $scope.activeBucket = $scope.status.remote.buckets[0];
      $scope.bucketCursor = 0;
      $scope.fileCursor = 0;
    }
    _.each($scope.status.remote.loading, function(info, k) {
      $scope.loading[k] = _.map(info.counted, function(num) {
        return 100 * ( num / info.endsize );
      });
    });
  });

  $scope.eventSets = [];
  $scope.eventFile = null;

  //Store saved presets in LocalStorage
  $scope.saved = {};
  var loadSaved = function () {
    var saved_str = window.localStorage.saved;
    try {
      var parsed = JSON.parse(saved_str);
      if(parsed && _.isPlainObject(parsed)) {
        $scope.saved = parsed;
      }
    }
    catch(err) {
      //Couldn't load saved presets.. probably weren't any.
    }
  }
  loadSaved();

  var saveSaved = function() {
    $log.info('Saving presets...', $scope.saved)
    window.localStorage.saved = JSON.stringify($scope.saved);
  };

  $scope.hasSaved = function() {
    return !_.isEmpty($scope.saved);
  }

  $scope.saveActiveStats = function() {
    if(_.isEmpty($scope.activeStats)) {
      $dialog.messageBox(
        "Error",
        "You must have stats selected to save a preset!",
        [{label: 'OK'}]).open();
      return;
    }
    var dia = $dialog.dialog({
      backdrop: true,
      templateUrl: 'partials/savedialog.html',
      controller: 'SaveDialogCtrl'
    }).open();
    dia.then(function(result) {
      if(!result) {
        return;
      }
      var active = _.map($scope.activeStats, function(v, k) {
        var stat = k.match(/^([^;]+(;name=[^,]+)?)([;,].*)?/);
        console.log(stat)
        return stat[1];
      })
      $scope.saved[result.name] = active;
      saveSaved();
    })
  }

  $scope.deleteSaved = function(name) {
    var dia = $dialog.messageBox(
      "Confirm",
      "Really delete preset \'" + name + "\'?",
      [{label: 'Yes', result: true},
       {label: 'No', result: false}]).open();

    dia.then(function(res) {
      if(res) {
        delete $scope.saved[name];
        saveSaved();
      }
    });
  }

  $scope.activeFile = '';
  $scope.activeBucket = '';
  $scope.activeStats = {};
  var chart = document.getElementById('chart');
  var container = document.getElementById('charthaver');
  $scope.updating = false;
  $scope.set = function(field, item) {
    $scope[field] = item;
  }
  $scope.toggle = function(tgl, item) {
    if($scope[tgl][item]) {
      delete $scope[tgl][item]
    } else {
      $scope[tgl][item] = true;
    }
    makechart();
  };

  $scope.clickFile = function(file, ev) {
    $scope.activeFile = file;
    if(ev.ctrlKey || ev.metaKey) {
      $scope.eventFile = file;
      $http.get('/events', {params: {file: file}}).
        success(function(data) {
          if(data) {
            //TODO should be able to show from multiple files
            $scope.eventSets = [data];
            syncAnnotations();
          }
        });
    }
  }


  $scope.statfilter = '';
  $scope.filteredStats = function() {
    var stats = $scope.stats;
    var selected = _.filter(stats, $scope.statOn);
    var remain = _.difference(stats, selected);
    if($scope.statfilter == '') {
      return selected.concat(remain);
    }
    var results = fuzzy.filter($scope.statfilter, stats);
    var filtered = results.map(function(el) { return el.string; });
    return selected.concat(_.difference(filtered, selected));
  }

  $scope.statOn = function(stat) {
    for(s in $scope.activeStats) {
      if( s == stat ||
          s.indexOf(stat + ';') == 0 ||
          s.indexOf('rate(' + stat + ');') == 0) {
        return true;
      }
    }
    return false;
  }

  var annotid = 0;
  var annotations = [];
  function syncAnnotations() {
    var toSet = [];
    if($scope.seriesnames) {
      _.each($scope.eventSets, function(eset) {
        _.each(eset, function(ev) {
          toSet.push({
            xval: (new Date(ev.timestamp)).getTime(),
            shortText: ev.short || '',
            cssClass: ev.icon || '',
            text: ev.label,
            idx: -1,
            attachAtBottom: true,
            series: $scope.seriesnames[0]
          });
        });
      });
    }
    _.each(annotations, function(ann, idx) {
      ann.series = $scope.seriesnames[0];
      ann.attachAtBottom = true;
      ann.idx = idx;
      toSet.push(ann);
    });
    g.setAnnotations(toSet);
  }

  $scope.master = false;
  var g = new Dygraph(chart, [[0,0]],
    {labels: ['Time', '?'],
     digitsAfterDecimal: 0,
     connectSeparatedPoints: true,
     // Selection from Colorbrewer set "Set1" from http://colorbrewer2.org/
     // and https://github.com/mbostock/d3/blob/master/lib/colorbrewer/colorbrewer.js
     colors: ["#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#a65628","#f781bf","#999999"],
     legend: 'always',
     axes: {
       y: {
         valueFormatter: d3.format('2.3s'),
         axisLabelFormatter: d3.format('2.3s')
       }
     },
     clickCallback: function(e, x, p) {
       if(!(e.ctrlKey || e.metaKey)) {
         return;
       }
       var ann = {
         xval: x,
         shortText: ++annotid,
         text: 'Marker #' + annotid,
       };
       annotations.push(ann);
       syncAnnotations();
     },
     annotationClickHandler: function(ann, p, dygraph, e) {
       if(!e.shiftKey) { return; }
       delete annotations[ann.idx];
       annotations = _.compact(annotations);
       syncAnnotations();
     },
     labelsSeparateLines: true,
     labelsDiv: "graphlabels",
     drawCallback: function(me, initial) {
       if(initial || remoteUpdate) return;
       var range = me.xAxisRange();
       var message = {
         kind: 'range-update',
         client: clientid,
         range: range
       };
       if($scope.master) {
         $scope.status.send(message);
       }
     }
    });
  graph = g;
  $scope.errored = false;
  function makechart() {
    if(_.isEmpty($scope.activeStats)) {
      return;
    }
    if($scope.updating) {
      // Daniel Owen - Don't think should re-trigger as causes graph to be drawn too often.
      //$scope.retrigger = true;
      return;
    }
    $scope.updating = true;
    $http.get('/statdata', {params: {
      stat: JSON.stringify(_.keys($scope.activeStats))
    }}).
    success(function(data) {
      $scope.errored = false;
      var points = data.points;
      $scope.seriesnames = data.stats;
      for(p in points) {
        points[p][0] = new Date(points[p][0]);
      }
      g.updateOptions({
        file: points,
        labels: ['Time'].concat(data.stats)
        });
      syncAnnotations();
      g.resize();
      $scope.updating = false;
      if($scope.retrigger) {
        $scope.retrigger = false;
        makechart();
      }
    }).
    error(function(err) {
      $log.error(err);
      $scope.errored = true;
      $scope.updating = false;
    })
  }

  var setupstat = function(stat, add) {
    if(!($scope.activeBucket && $scope.activeFile)) {
      $log.error("Must have a bucket and file selected!");
      toastr.error('You must have a bucket and file selected to add a stat!');
      return false;
    }
    if(stat.indexOf(';') < 0) {
      stat += ';';
    } else {
      stat += ',';
    }
    stat += "bucket=" + $scope.activeBucket;
    stat += ",file=" + $scope.activeFile;
    if(add) {
      $scope.toggle('activeStats', stat);
    } else {
      $scope.activeStats = {};
      $scope.activeStats[stat] = true;
    }
    return true;
  }

  $scope.presets = {
    'memory': ['ep_mem_high_wat', 'mem_used', 'ep_mem_low_wat', 'ep_max_data_size',
               'ep_meta_data_memory', 'ep_value_size'],
    'resident ratios': ['vb_active_perc_mem_resident', 'vb_replica_perc_mem_resident'],
    'operations': ['rate(cmd_get)', 'rate(cmd_set)', 'rate(delete_hits)', 'rate(delete_misses)',
                   'rate(ep_tmp_oom_errors)'],
    'Vbuckets': ['vb_active_num', 'vb_replica_num'],
    'Disk': ['rate(ep_diskqueue_fill)', 'rate(ep_diskqueue_drain)', 'ep_diskqueue_items'],
    'Key and Value Size' : ['ep_value_size / (curr_items_tot - ep_num_non_resident);name=Value Size',
                            '((ep_kv_size - ep_value_size) - (curr_items_tot * 56)) / curr_items_tot;name=Key Size']
  };
    
    
  var mystats = null;
  $http.get('/statsdesc').success(function(data) {mystats = data;});

  $scope.applyPreset = function(preset, e) {
    // Daniel Owen - Set updating to true to stop graphs being drawn prematurely.
    $scope.updating = true;
    if(!(e.ctrlKey || e.metaKey)) {
      $scope.activeStats = {};
    }
    _.each(preset, function(stat) {
      // Daniel Owen - If on last item in list then turn off updating so graph will be drawn.
      if(preset[preset.length-1] == stat) {
        $scope.updating = false;}
      return setupstat(stat, true);
    });
  }
  $scope.presetStats = function(preset) {
    return _(preset).map(_.escape).join("<br>");
  }
    
  $scope.describeStats = function(stat) {
      if (stat in mystats) {
          var description = mystats[stat];
          return (description.concat("<br>"));}
    }

  $scope.statclicked = function(stat, e) {
    if(setupstat(stat, e.ctrlKey || e.metaKey)) {
      makechart();
    }
  }

  $scope.connect = true;
  $scope.$watch('connect', function() {
    g.updateOptions({
      connectSeparatedPoints: $scope.connect
    });
  });

  $scope.logscale = "false";
  $scope.$watch('logscale', function() {
    g.updateOptions({
      logscale: ($scope.logscale === "true") });
  });
}
