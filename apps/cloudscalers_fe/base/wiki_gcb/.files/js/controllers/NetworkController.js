angular.module('cloudscalers.controllers')
    .controller('NetworkController', ['$scope', 'NetworkBuckets', '$modal', '$timeout',
        function ($scope, NetworkBuckets, $modal, $timeout) {
            $scope.search = "";
            $scope.portforwardbyID = "";
            $scope.$watch('currentSpace.id',function(){
                if ($scope.currentSpace){
                    $scope.managementui = "http://" + $scope.currentSpace.publicipaddress + "/webfig/";
                }
            });
            NetworkBuckets.listPortforwarding($scope.currentSpace.id).then(function(data) {
                $scope.portforwarding = data;
                $scope.search = $scope.portforwarding[0];
            });
            var addRuleController = function ($scope, $modalInstance) {
                $scope.newRule = {
                    ip: $scope.portforwarding[0],
                    publicPort: '',
                    VM: $scope.portforwarding[0],
                    localPort: '',
                    commonPort: '',
                    // message: false,
                    statusMessage: ''
                };
                NetworkBuckets.commonports().then(function(data) {
                    $scope.commonports = data;
                });
                $scope.updateCommonPorts = function () {
                    $scope.newRule.publicPort  = $scope.newRule.commonPort.port;
                    $scope.newRule.localPort = $scope.newRule.commonPort.port;
                };
                
                $scope.submit = function () {
                    NetworkBuckets.createPortforward($scope.newRule.ip.ip, $scope.newRule.publicPort, $scope.newRule.VM.vmName, $scope.newRule.localPort).then(
                        function (result) {
                            $scope.portforwarding.push({ip: $scope.newRule.ip.ip, puplicPort: $scope.newRule.publicPort, 
                            vmName: $scope.newRule.VM.vmName, localPort: $scope.newRule.localPort});
                            $modalInstance.close({});
                        }
                    );
                };
                $scope.cancel = function () {
                    $modalInstance.dismiss('cancel');
                };
            };
            $scope.portForwardPopup = function () {
                var modalInstance = $modal.open({
                    templateUrl: 'portForwardDialog.html',
                    controller: addRuleController,
                    resolve: {},
                    scope: $scope
                });
            };
            $scope.tableRowClicked = function (index) {
              var modalInstance = $modal.open({templateUrl: 'editPortForwardDialog.html', scope: $scope , resolve: {}});
              $scope.editRule = [];
              NetworkBuckets.listPortforwarding($scope.currentSpace.id).then(function(data) {
                $scope.portforwardbyID = data;
                $scope.editRule = {
                    id: index.id,
                    ip: $scope.portforwardbyID[index.id].publicIp,
                    publicPort: $scope.portforwardbyID[index.id].publicPort,
                    VM: $scope.portforwardbyID[index.id].vmName,
                    localPort: $scope.portforwardbyID[index.id].localPort
                };
              });
              NetworkBuckets.commonports().then(function(data) {
                    $scope.commonports = data;
              });
              $scope.update = function () {
                  NetworkBuckets.updatePortforward($scope.editRule.id, $scope.editRule.ip, $scope.editRule.publicPort, $scope.editRule.VM, $scope.editRule.localPort).then(
                      function (result) {
                          $scope.portforwarding = result.data;
                          $scope.search = $scope.portforwarding[0];
                          modalInstance.close({});
                          $scope.message = true;
                          $scope.statusMessage = "Saved!";
                          $timeout(function() {
                              $scope.message = false;
                          }, 3000); 
                      }
                  );
              };
              $scope.delete = function () {
                  NetworkBuckets.deletePortforward($scope.currentSpace.id, $scope.editRule.id).then(
                      function (result) {
                          $scope.portforwarding = result.data;
                          $scope.search = $scope.portforwarding[0];
                          modalInstance.close({});
                          $scope.message = true;
                          $scope.statusMessage = "Removed!";
                          $timeout(function() {
                              $scope.message = false;
                          }, 3000); 
                      }
                  );
              };
              $scope.cancel = function () {
                    modalInstance.dismiss('cancel');
              };
              $scope.updateCommonPorts = function () {
                    $scope.editRule.publicPort  = $scope.editRule.commonPort.port;
                    $scope.editRule.localPort = $scope.editRule.commonPort.port;
                };
            }
            
        }
    ]).filter('groupBy', function(){
        return function(list, group_by) {
        var filtered = [];
        var prev_item = null;
        var group_changed = false;
        var new_field = group_by + '_CHANGED';
        angular.forEach(list, function(item) {
            group_changed = false;
            if (prev_item !== null) {
                if (prev_item[group_by] !== item[group_by]) {
                    group_changed = true;
                }
            } else {
                group_changed = true;
            }
            if (group_changed) {
                item[new_field] = true;
            } else {
                item[new_field] = false;
            }
            filtered.push(item);
            prev_item = item;
        });
        return filtered;
        };
    }).filter('unique', function() {
       return function(collection, keyname) {
          var output = [], 
              keys = [];

          angular.forEach(collection, function(item) {
              var key = item[keyname];
              if(keys.indexOf(key) === -1) {
                  keys.push(key);
                  output.push(item);
              }
          });

          return output;
       };
    }).directive('numbersOnly', function(){
   return {
     require: 'ngModel',
     link: function(scope, element, attrs, modelCtrl) {
       modelCtrl.$parsers.push(function (inputValue) {
           if (inputValue == undefined) return '' 
           var transformedInput = inputValue.replace(/[^0-9]/g, ''); 
           if (transformedInput!=inputValue) {
              modelCtrl.$setViewValue(transformedInput);
              modelCtrl.$render();
           }         

           return transformedInput;         
       });
     }
   };
});