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
  };

  function toCS(ob) {
    _(ob).keys().join(',')
  }
  function makechart() {
    $scope.updating = true;
    var stat = $scope.activeStat;
    $http.get('/stat', {params: {
      stat: stat,
      res: 10,
//      buckets: toCS($scope.activeBuckets),
//      files: toCS($scope.activeFiles)
    }}).
    success(function(data) {
      var points = data.points;
      for(p in points) {
        points[p][0] = new Date(points[p][0]);
      }
      var g = new Dygraph(chart, points,
        {labels: ['Time', stat],
          digitsAfterDecimal: 0});
      g.resize();
    });
  }
  makechart();
  $scope.dochart = function(stat) {
    $scope.activeStat = stat;
    makechart();
  }
}
