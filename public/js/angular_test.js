(function(){

//var gems= [{ id: 1, name: 'gem1', price: 2}, { id: 2, name: 'gem2', price: 1}];

    var gems = [];

    var randomIntFromInterval = function (min,max)
    {
        return Math.floor(Math.random()*(max-min+1)+min);
    };


var app = angular.module('gemStore',[]);

    app.service('StoreService', function ($http) {
        this.loadGems = function () {
            return $http.get('./gems.json');
        };
    });

    app.controller('StoreController', function(StoreService, $scope){
        this.init = function () {
            StoreService.loadGems().then(function(response){$scope.products=response.data;});
        };

        this.addRandomItem = function (){
            var lastGem = $scope.products[$scope.products.length-1];
            $scope.products.push({id: lastGem.id + 1, name: 'gem' + (lastGem.id + 1), price: randomIntFromInterval(1,20)});
        };

        this.SetCurrentProduct = function(productIndex){
            this.currentProductIndex = productIndex;
        };

        this.currentProductIndex = null;
    });

})();