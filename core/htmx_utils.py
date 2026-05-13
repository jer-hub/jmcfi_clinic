"""
HTMX utilities for Django views.

Provides helpers for detecting HTMX requests, managing responses,
and handling hypermedia-driven interactions.
"""

import json
from django.http import HttpResponse
from django.utils.decorators import decorator_from_middleware
from typing import Optional, Dict, Any


def is_htmx_request(request) -> bool:
    """
    Check if request is from HTMX.
    
    HTMX adds an HX-Request header to all requests.
    
    Usage:
        if is_htmx_request(request):
            return render(request, 'partial.html', {...})
        return render(request, 'full_page.html', {...})
    """
    return request.headers.get('HX-Request') == 'true'


def htmx_partial_render(response):
    """
    Decorator to automatically return partial templates for HTMX requests.
    
    Requires view to return a dict with:
    - 'partial': template name for HTMX
    - 'full': template name for direct navigation
    - 'context': context dict
    
    Usage:
        @htmx_partial_render
        def my_view(request):
            return {
                'partial': 'partial.html',
                'full': 'full.html',
                'context': {'items': items}
            }
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            result = view_func(request, *args, **kwargs)
            
            if not isinstance(result, dict):
                return result
            
            from django.shortcuts import render
            
            if is_htmx_request(request):
                return render(
                    request,
                    result['partial'],
                    result['context'],
                    status=result.get('status', 200)
                )
            else:
                return render(
                    request,
                    result['full'],
                    result['context'],
                    status=result.get('status', 200)
                )
        
        return wrapper
    return decorator


class HTMXMiddleware:
    """
    Middleware to attach HTMX request information to request object.
    
    Adds:
    - request.is_htmx: bool - whether this is an HTMX request
    - request.htmx_target: str - ID of hx-target element
    - request.htmx_trigger: str - ID of element that triggered request
    - request.htmx_trigger_name: str - name of element that triggered request
    - request.htmx_prompt: str - user prompt response (for hx-prompt)
    - request.htmx_current_url: str - URL of page that made request
    
    Usage:
        # settings.py
        MIDDLEWARE = [
            ...,
            'core.htmx_utils.HTMXMiddleware',
        ]
        
        # In views
        def some_view(request):
            if request.is_htmx:
                return render(request, 'partial.html', {...})
            return render(request, 'full.html', {...})
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Attach HTMX headers to request
        request.is_htmx = request.headers.get('HX-Request') == 'true'
        request.htmx_target = request.headers.get('HX-Target')
        request.htmx_trigger = request.headers.get('HX-Trigger')
        request.htmx_trigger_name = request.headers.get('HX-Trigger-Name')
        request.htmx_prompt = request.headers.get('HX-Prompt')
        request.htmx_current_url = request.headers.get('HX-Current-URL')
        
        response = self.get_response(request)
        return response


# Response header helpers

def htmx_redirect(url: str) -> HttpResponse:
    """
    Return HTMX-safe redirect response.
    
    HTMX can't follow standard redirects; use HX-Redirect header instead.
    
    Usage:
        if form.is_valid():
            form.save()
            return htmx_redirect(f'/success/{form.instance.id}/')
    """
    response = HttpResponse(status=200)
    response['HX-Redirect'] = url
    return response


def htmx_location(
    path: str,
    target: Optional[str] = None,
    swap: Optional[str] = None,
    select: Optional[str] = None
) -> HttpResponse:
    """
    Return HTMX location response with fine-grained control.
    
    More flexible than HX-Redirect; allows specifying target and swap strategy.
    
    Args:
        path: URL to navigate to
        target: CSS selector of target element (optional)
        swap: Swap strategy (innerHTML, outerHTML, beforebegin, etc.)
        select: CSS selector to extract from response
    
    Usage:
        response = htmx_location(
            '/dashboard/',
            target='#content',
            swap='outerHTML'
        )
    """
    location_data = {'path': path}
    if target:
        location_data['target'] = target
    if swap:
        location_data['swap'] = swap
    if select:
        location_data['select'] = select
    
    response = HttpResponse(status=200)
    response['HX-Location'] = json.dumps(location_data)
    return response


def htmx_trigger_event(
    *events: str,
    detail: Optional[Dict[str, Any]] = None
) -> HttpResponse:
    """
    Trigger client-side events from server.
    
    Usage:
        response = HttpResponse()
        response['HX-Trigger'] = htmx_trigger_event(
            'taskDeleted',
            'refreshStats',
            detail={'id': 123}
        )
        return response
    """
    trigger_data = {}
    
    for event in events:
        if detail and len(events) == 1:
            trigger_data[event] = detail
        else:
            trigger_data[event] = None
    
    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps(trigger_data)
    return response


def htmx_add_trigger(response: HttpResponse, event_name: str, detail: Optional[Dict[str, Any]] = None) -> HttpResponse:
    """Append an HTMX trigger event to an existing response."""
    current_value = response.get('HX-Trigger')
    trigger_data: Dict[str, Any] = {}

    if current_value:
        try:
            trigger_data = json.loads(current_value)
        except (TypeError, json.JSONDecodeError):
            trigger_data = {}

    trigger_data[event_name] = detail if detail is not None else None
    response['HX-Trigger'] = json.dumps(trigger_data)
    return response


def htmx_add_toast(response: HttpResponse, message: str, toast_type: str = 'success') -> HttpResponse:
    """Attach the standard user toast trigger to an existing response."""
    return htmx_add_trigger(
        response,
        'user-toast',
        {
            'message': message,
            'type': toast_type,
        },
    )


def htmx_push_url(response: HttpResponse, url: str) -> HttpResponse:
    """
    Update browser address bar without full page reload.
    
    Usage:
        response = render(request, 'item.html', context)
        response = htmx_push_url(response, f'/items/{item.id}/')
        return response
    """
    response['HX-Push-Url'] = url
    return response


def htmx_replace_url(response: HttpResponse, url: str) -> HttpResponse:
    """
    Replace browser history entry (instead of adding new entry).
    
    Usage:
        response = render(request, 'search_results.html', context)
        response = htmx_replace_url(response, f'/search?q={query}')
        return response
    """
    response['HX-Replace-Url'] = url
    return response


def htmx_refresh(response: HttpResponse) -> HttpResponse:
    """
    Tell HTMX to do a full page refresh.
    
    Usage:
        if not request.is_htmx:
            return redirect('home')
        response = HttpResponse()
        response = htmx_refresh(response)
        return response
    """
    response['HX-Refresh'] = 'true'
    return response


def htmx_reswap(response: HttpResponse, swap: str) -> HttpResponse:
    """
    Tell HTMX how to swap content.
    
    Args:
        swap: innerHTML (default), outerHTML, beforebegin, afterbegin,
              beforeend, afterend, delete, none
    
    Usage:
        response = render(request, 'item.html', context)
        response = htmx_reswap(response, 'outerHTML')
        return response
    """
    response['HX-Reswap'] = swap
    return response


def htmx_retarget(response: HttpResponse, selector: str) -> HttpResponse:
    """
    Tell HTMX to use a different target for swap.
    
    Usage:
        response = render(request, 'item.html', context)
        response = htmx_retarget(response, '#main-content')
        return response
    """
    response['HX-Retarget'] = selector
    return response


# Validation error handling

def htmx_form_error(form, status_code: int = 400):
    """
    Render form with validation errors for HTMX.
    
    Usage:
        if form.is_valid():
            form.save()
            return render(request, 'success.html', {...})
        return htmx_form_error(form)
    """
    from django.shortcuts import render
    
    # Assuming form template is named appropriately
    template_name = f'forms/{form.__class__.__name__.lower()}.html'
    
    response = render(
        None,  # Will use get_template
        template_name,
        {'form': form}
    )
    response.status_code = status_code
    return response


# Decorators

def require_htmx(view_func):
    """
    Decorator to enforce HTMX-only views.
    
    Returns 403 Forbidden for non-HTMX requests.
    
    Usage:
        @require_htmx
        def delete_item(request, item_id):
            item = Item.objects.get(id=item_id)
            item.delete()
            return HttpResponse()
    """
    def wrapper(request, *args, **kwargs):
        if not is_htmx_request(request):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('HTMX request required')
        return view_func(request, *args, **kwargs)
    
    return wrapper


def htmx_response(partial_template: str, full_template: str):
    """
    Decorator to automatically handle HTMX vs full page responses.
    
    Requires view to return context dict.
    
    Usage:
        @htmx_response('tasks/list.html', 'tasks/index.html')
        def task_list(request):
            tasks = Task.objects.all()
            return {'tasks': tasks}
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            from django.shortcuts import render
            
            context = view_func(request, *args, **kwargs)
            
            if not isinstance(context, dict):
                return context
            
            if is_htmx_request(request):
                return render(request, partial_template, context)
            else:
                return render(request, full_template, context)
        
        return wrapper
    return decorator
