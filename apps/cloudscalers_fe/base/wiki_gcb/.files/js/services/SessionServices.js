angular.module('cloudscalers.services')

	.factory('authenticationInterceptor',['$q', 'SessionData', '$window', function($q, SessionData, $window){
        return {
            'request': function(config) {
                if (config) {
                    var url = config.url;

                    if(! /((partials)|(template)\/)|(\.html)/i.test(url)){

                    	var currentUser = SessionData.getUser();
                    	if (currentUser){
                    		var uri = new URI(url);
                       		uri.addSearch('authkey', currentUser.api_key);
                       		config.url = uri.toString();
    					}
                    }
                }
                return config || $q.when(config);
    	    },
    	    'response': function(response) {
                return response || $q.when(response);
            },
            
           'responseError': function(rejection) {
        	   if (rejection.status == 401){
        		   var uri = new URI($window.location);

       				uri.filename('Login');
       				uri.fragment('');
       				$window.location = uri.toString();
        	   }
               return $q.reject(rejection);
            }
        };
	}])
    .factory('SessionData', function($window) {
        return {
        	getUser : function(){
        			var userdata = $window.sessionStorage.getItem('gcb:currentUser');
        			if (userdata){
        				return JSON.parse(userdata);
        			}
        		},
        	setUser : function(userdata){
        			if (userdata){
        				$window.sessionStorage.setItem('gcb:currentUser', JSON.stringify(userdata));
        			}
        			else{
        				$window.sessionStorage.removeItem('gcb:currentUser');
        			}
        		},
            getSpace : function() {
                var space = $window.sessionStorage.getItem('gcb:currentSpace');
                if (!space) {   
                    space = $window.localStorage.getItem('gcb:currentSpace');
                }

                if (space) {   
                    return JSON.parse(space);
                }
            },
            setSpace : function(space){
                    if (space){
                        $window.sessionStorage.setItem('gcb:currentSpace', JSON.stringify(space));
                    }
                    else{
                        $window.sessionStorage.removeItem('gcb:currentSpace');
                    }
                },
            };
    })
    .factory('User', function ($http, SessionData, $q) {
        var user = {};
        
        user.current = function() {
            return SessionData.getUser();
        };
        
        user.login = function (username, password) {
            return $http({
                method: 'POST',
                data: {
                    username: username,
                    password: password
                },
                url: cloudspaceconfig.apibaseurl + '/users/authenticate'
            }).then(
            		function (result) {
            			SessionData.setUser({username: username, api_key: JSON.parse(result.data)});
            			return result.data;
            		},
            		function (reason) {
            			SessionData.setUser(undefined);
                        return $q.reject(reason); }
            );
        };

        user.logout = function() {
        	SessionData.setUser(undefined);
        };

        user.signUp = function(username, email, password) {
            var signUpResult = {};
            $http({
                method: 'POST',
                data: {
                    username: username,
                    emailaddress: email,
                    password: password
                },
                url: cloudspaceconfig.apibaseurl + '/users/register'
            })
            .success(function(data, status, headers, config) {
                signUpResult.success = true;
            })
            .error(function(data, status, headers, config) {
                signUpResult.error = data;
            });
            return signUpResult;
        }
        
        return user;
        
    });
