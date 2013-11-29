'use strict';

angular.module('cloudscalers')
	.directive('swaggerUiContainer', function(){
	    return {
	        restrict: 'A',
	        link: function (scope, elem, attrs) {
			
	        	var loadAPI = function(api_key){
	        		window.swaggerUi = new SwaggerUi({
	                    discoveryUrl:"./.files/docsample/data/catalog",
	                    apiKey:api_key,
	                    apiKeyName:"authkey",
	                    dom_id:"swagger-ui-container",
	                    supportHeaderParams: false,
	                    supportedSubmitMethods: ['get', 'post', 'put'],
	                    onComplete: function(swaggerApi, swaggerUi){
	                      $('pre code').each(function(i, e) {hljs.highlightBlock(e)});
	                    },
	                    onFailure: function(data) {
	                    	if(console) {
	                            	console.log("Unable to Load SwaggerUI");
	                            	console.log(data);
	                        	}
	                    },
	                    docExpansion: "none"
	                });

	                window.swaggerUi.load();

	        	};
        
        		scope.$watch(attrs.apiKey, function(newValue, oldValue) {
        		    loadAPI(newValue);
        		});
			

	        },
	     }
	})

    .directive('persistentDropdown', function() {
        return {
            restrict: 'A',
            link: function(scope, element, attrs) {
                element.addClass('dropdown-menu').on('click', '.accordion-heading', function(e) {
                    // Prevent the click event from propagation to the dropdown & closing it
                    e.preventDefault(); 
                    e.stopPropagation();

                    // If the body will be expanded, then add .open to the header
                    var header = angular.element(this);
                    var body = header.siblings('.accordion-body');
                    if (body.height() === 0) // body is collapsed & will be expanded
                        header.addClass('open');
                    else
                        header.removeClass('open');
                });

                // Keep the left border aligned with the border of the window.
                // Because 'position: absolute' doesn't work inside <ul>, I need to do it with JS.
                setInterval(function() {
                    element.css('margin-left', -element.parent('li').offset().left);
                }, 50);
            }
        };
    })
;
