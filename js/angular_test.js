/// <reference path="../typings/angularjs/angular.d.ts" />

(function(){

var gems= [{ id: 1, name: 'gem1', price: 2}, { id: 2, name: 'gem2', price: 1}];

var app = angular.module('gemStore',[]);
	
	app.controller('FetchController', ['$scope', '$http', '$templateCache',
	  function($scope, $http, $templateCache) {
	    $scope.url = '/gems.json';

	    // load the data from an external json file
	    $http.get($scope.url).success(function(data){
	    	$scope.products=data;
	    });

	  }]);

	app.controller('ProductController', ProductController);
	function ProductController($scope){
		$scope.SetCurrentProduct = function(productIndex){
			$scope.currentProductIndex = productIndex;
		};
		$scope.IsCurrentProduct = function(productIndex){
			return $scope.currentProductIndex===productIndex;
		};
		$scope.Init = function(){
			$scope.currentProductIndex = null;
		};
		$scope.Init();
	};

})();