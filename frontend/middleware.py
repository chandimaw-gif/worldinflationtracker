"""
Middleware to prevent caching of dynamic pages and static files.
Ensures fresh content is served after deployments.
"""


class CacheControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevent caching of HTML pages and API responses
        if 'text/html' in response.get('Content-Type', '') or \
           'application/json' in response.get('Content-Type', ''):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = 'Thu, 19 Nov 1981 08:52:00 GMT'

        return response
