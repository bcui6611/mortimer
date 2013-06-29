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
  $scope.activeStat = 'curr_connections';
  var chart = document.getElementById('chart');
  var container = document.getElementById('charthaver');
  $scope.updating = false;
  $scope.toggle = function(tgl, item) {
    if($scope[tgl][item]) {
      delete $scope[tgl][item]
    } else {
      $scope[tgl][item] = true;
    }
    dbmakechart();
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

  function toCS(ob) {
    return _(ob).keys().join(',');
  }
  function makechart() {
    console.log('charting...')
    $scope.updating = true;
    var stat = $scope.activeStat;
    $http.get('/stat', {params: {
      stat: stat,
      res: 10,
      buckets: toCS($scope.activeBuckets),
      files: toCS($scope.activeFiles)
    }}).
    success(function(data) {
      var points = data.points;
      for(p in points) {
        points[p][0] = new Date(points[p][0]);
      }
      var g = new Dygraph(chart, points,
        {labels: ['Time', stat],
         digitsAfterDecimal: 0,
         axes: {
           y: {
             valueFormatter: d3.format('.2s'),
             axisLabelFormatter: d3.format('.2s')
           }
         }
        });
      g.resize();
      dbmakechart = _.once(makechart);
      $scope.updating = false;
    });
  }
  var dbmakechart = _.once(makechart);
  $scope.dochart = function(stat) {
    $scope.activeStat = stat;
    dbmakechart();
  }
  dbmakechart();
}
