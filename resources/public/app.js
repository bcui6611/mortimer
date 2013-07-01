var app = angular.module('mortimer', []);

function DataCtrl($scope, $http) {
  function fetch(list) {
    $http.get('/'+list).success(function(data) {
      $scope[list] = data;
    });
  }
  _(['files','buckets','stats']).each(fetch);

  $scope.activeFiles = {};
  $scope.activeBuckets = {};
  $scope.activeStats = {'curr_connections':true};
  var chart = document.getElementById('chart');
  var container = document.getElementById('charthaver');
  $scope.updating = false;
  $scope.toggle = function(tgl, item) {
    if($scope[tgl][item]) {
      delete $scope[tgl][item]
    } else {
      $scope[tgl][item] = true;
    }
    makechart();
  };

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
      if(s == stat || s == stat + ':derivative') {
        return true;
      }
    }
    return false;
  }

  function toCS(ob) {
    return _(ob).keys().join(',');
  }
  var g = new Dygraph(chart, [[0,0]],
    {labels: ['Time', '?'],
     digitsAfterDecimal: 0,
     legend: 'always',
     axes: {
       y: {
         valueFormatter: d3.format('2.3s'),
         axisLabelFormatter: d3.format('2.3s')
       }
     }
    });
  function makechart() {
    if($scope.updating) {
      $scope.retrigger = true;
      return;
    }
    $scope.updating = true;
    $http.get('/statdata', {params: {
      stat: toCS($scope.activeStats),
      res: 10,
      buckets: toCS($scope.activeBuckets),
      files: toCS($scope.activeFiles)
    }}).
    success(function(data) {
      var points = data.points;
      for(p in points) {
        points[p][0] = new Date(points[p][0]);
      }
      g.updateOptions({
        file: points,
        labels: ['Time'].concat(data.stats)
        });
      g.resize();
      $scope.updating = false;
      if($scope.retrigger) {
        $scope.retrigger = false;
        makechart();
      }
    });
  }
  $scope.statclicked = function(stat, e) {
    if(e.ctrlKey || e.metaKey) {
      $scope.toggle('activeStats', stat);
    } else {
      $scope.activeStats = {};
      $scope.activeStats[stat] = true;
    }
    makechart();
  }
  makechart();
}
