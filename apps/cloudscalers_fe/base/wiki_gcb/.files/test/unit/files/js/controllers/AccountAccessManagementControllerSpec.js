describe("AccountAccessManagementController tests", function(){
    var $scope, ctrl, $q, $window = {}, $httpBackend, Account, getAccountDefer, addUserDefer;
    
    beforeEach(module('cloudscalers'));
    
    beforeEach(inject(function($rootScope, _$controller_, _$q_, _$httpBackend_) {
    	$httpBackend = _$httpBackend_;
        $controller = _$controller_;
		defineUnitApiStub($httpBackend);
		
        $q = _$q_;
        getAccountDefer = $q.defer();
        addUserDefer = $q.defer();
        Account = {
            get: jasmine.createSpy('get').andReturn(getAccountDefer.promise),
            addUser: jasmine.createSpy('addUser').andReturn(addUserDefer.promise),
        };

        $scope = $rootScope.$new();
        $scope.currentSpace = {
            cloudSpaceId: 15,
            accountId: 1
        };
        $scope.currentAccount = {};
        ctrl = $controller('AccountAccessManagementController', {
            $scope: $scope,
            Account: Account
        });

        getAccountDefer.resolve({
            name: 'Linny Miller',
            descr: 'Mr. Linny Miller',
            acl: [{
                    "type": "U",
                    "guid": "",
                    "right": "CXDRAU",
                    "userGroupId": "linny"
                }, {
                    "type": "U",
                    "guid": "",
                    "right": "CXDRAU",
                    "userGroupId": "harvey"
                }
            ]
        });
        $scope.$digest();
    }));


    it('addUser adds a new user to the list of users', function() {
        $scope.newUser.nameOrEmail = 'User 4';
        $scope.addUser();
        addUserDefer.resolve("Success");
        $scope.$digest();
        
        expect(Account.addUser).toHaveBeenCalled();
        expect($scope.userError).toEqual(false);
    });

    it("addUser rejects adding a user which doesn't exist", function() {
        $scope.newUser.nameOrEmail = 'Not working';
        $scope.addUser();
        addUserDefer.reject("Failed");
        $scope.$digest();
        
        expect(Account.addUser).toHaveBeenCalled();
        expect($scope.userError).toEqual(true);
    });

});

