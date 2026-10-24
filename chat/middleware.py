from django.conf import settings
from django.http import HttpResponseRedirect


class FrontendPagesMiddleware:
    """Keep old Django page links pointed at the current Next.js interface."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        page = request.path_info == '/' or request.path_info.startswith(('/accounts/', '/invite/'))
        if settings.FRONTEND_URL and page and request.method in ('GET', 'HEAD'):
            return HttpResponseRedirect(settings.FRONTEND_URL + request.get_full_path())
        return self.get_response(request)
