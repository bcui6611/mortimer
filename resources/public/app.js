var app = angular.module('mortimer', ['ui.bootstrap']);

app.config(function($routeProvider, $locationProvider) {
  $routeProvider.
  when('/stats/', { templateUrl: '/partials/stats.html',
                    controller: 'DataCtrl'}).
  when('/files/', { templateUrl: '/partials/files.html',
                    controller: 'FilesCtrl'}).
  otherwise({ redirectTo: '/stats/'});
});

app.factory('StatusService', function($rootScope) {
  var status = {remote: {}};
  var mws = new WebSocket("ws://" + location.host + "/status-ws");
  mws.onmessage = function(evt) {
    var message = JSON.parse(evt.data);
    if(message.kind == "status-update") {
      status.remote = message.data;
      $rootScope.$apply();
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

function FilesCtrl($scope, StatusService) {
  $scope.status = StatusService;
}

function DataCtrl($scope, $http, $log, $dialog, StatusService) {
  $scope.status = StatusService;
  $scope.stats = [];
  $scope.$watch('status.remote.files', function() {
    if(_.isEmpty($scope.stats)) {
     $http.get('/stats').success(function(data) {
        $scope.stats = data;
     });
    }
  });

  $scope.$watch('status.remote.loading', function() {
    $scope.loading = {};
    _.each($scope.status.remote.loading, function(info, k) {
      $scope.loading[k] = _.map(info.counted, function(num) {
        return 100 * ( num / info.endsize );
      });
    });
    console.log($scope.loading);
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
        var stat = k.match(/^[^:]+(:rate)?/);
        return stat[0];
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
    if($scope.statfilter == '') {
      return stats;
    }
    var results = fuzzy.filter($scope.statfilter, stats);
    return results.map(function(el) { return el.string; });
  }

  $scope.statOn = function(stat) {
    for(s in $scope.activeStats) {
      if( s == stat || 
          s.indexOf(stat + ':') == 0 ||
          s.indexOf(stat + ';') == 0) {
        return true;
      }
    }
    return false;
  }

  function toCS(ob) {
    return _(ob).keys().join(',');
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

  var g = new Dygraph(chart, [[0,0]],
    {labels: ['Time', '?'],
     digitsAfterDecimal: 0,
     connectSeparatedPoints: true,
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
     labelsDiv: "graphlabels"
    });
  $scope.errored = false;
  function makechart() {
    if($scope.updating) {
      $scope.retrigger = true;
      return;
    }
    $scope.updating = true;
    $http.get('/statdata', {params: {
      stat: toCS($scope.activeStats)
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
      console.log(err);
      $scope.errored = true;
      $scope.updating = false;
    })
  }

  var setupstat = function(stat, add) {
    if(!($scope.activeBucket && $scope.activeFile)) {
      $log.error("Must have a bucket and file selected!");
      $dialog.messageBox("Error", "You must have a bucket and file selected!", [{label:'OK', result: true}]).open();
      return false;
    }
    if(stat.indexOf(':') < 0) { 
      stat += ':'
    } else {
      stat += ';'
    }
    stat += "bucket=" + $scope.activeBucket;
    stat += ";file=" + $scope.activeFile;
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
    'operations': ['cmd_get:rate', 'cmd_set:rate', 'delete_hits:rate', 'delete_misses:rate',
                   'ep_tmp_oom_errors:rate']
  };
  $scope.applyPreset = function(preset, e) {
    if(!(e.ctrlKey || e.metaKey)) {
      $scope.activeStats = {};
    }
    _.each(preset, function(stat) {
      return setupstat(stat, true);
    });
  }
  $scope.presetStats = function(preset) {
    return _(preset).map(_.escape).join("<br>");
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
}

