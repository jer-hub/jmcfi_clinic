# middleware.py
from django.http import HttpResponseForbidden

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'required_roles'):
            if request.user.role not in view_func.required_roles:
                return HttpResponseForbidden()