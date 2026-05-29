"""Middleware: normalize HTMX responses for auth redirects and bare 403s."""

from __future__ import annotations

from django.http import HttpResponseForbidden
from django.urls import reverse

from .access_control import AccessReason, access_denied_response
from .htmx_utils import is_htmx_request


class HtmxAccessResponseMiddleware:
    """
    Convert login redirects and empty 403 responses on HTMX requests into
    401/403 responses with HX-Redirect (full-page navigation).
    """

    REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not is_htmx_request(request):
            return response

        if response.status_code in self.REDIRECT_STATUS_CODES:
            location = response.get('Location', '') or ''
            login_paths = (
                reverse('account_login'),
                reverse('core:admin_login'),
            )
            if any(path in location for path in login_paths):
                return access_denied_response(
                    request,
                    status_code=401,
                    reason=AccessReason.UNAUTHENTICATED,
                    redirect_url=location,
                )

        if (
            response.status_code == 403
            and not response.get('HX-Redirect')
            and isinstance(response, HttpResponseForbidden)
        ):
            return access_denied_response(
                request,
                status_code=403,
                reason=AccessReason.FORBIDDEN,
            )

        return response
