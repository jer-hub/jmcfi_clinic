"""Primary navigation active-state helpers (namespace-based, no substring hacks)."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

# Apps grouped under the Services dropdown / mobile Services panel
SERVICES_NAMESPACES = frozenset(
    {
        "appointments",
        "medical_records",
        "dental_records",
        "document_request",
    }
)

# Routes under Appointments that belong to the admin Settings disclosure
APPOINTMENT_SETTINGS_URL_NAMES = frozenset(
    {
        "appointment_type_settings",
        "edit_appointment_type_default",
        "toggle_appointment_type_default",
    }
)

CORE_SETTINGS_URL_NAMES = frozenset(
    {
        "settings_hub",
        "settings_clinic",
        "settings_roles",
        "settings_role_edit",
        "settings_audit",
    }
)


def nav_bar_context(request: HttpRequest) -> dict[str, Any]:
    """
    Exposes ``nav_active`` — booleans for highlighting navbar sections.

    Anonymous users get an empty dict (navbar is not rendered for them).
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    match = getattr(request, "resolver_match", None)
    view_full = ""
    ns = ""
    url_name = ""
    if match:
        view_full = getattr(match, "view_name", "") or ""
        if ":" in view_full:
            ns = view_full.split(":", 1)[0]
        url_name = getattr(match, "url_name", "") or ""

    nav_active = {
        "dashboard": view_full == "core:dashboard",
        "services": ns in SERVICES_NAMESPACES,
        "health_forms": ns == "health_forms_services",
        "health_tips": ns == "health_tips",
        "analytics": ns == "analytics" and url_name == "dashboard",
        "pharmacy": ns == "pharmacy",
        "settings_menu": (
            (ns == "appointments" and url_name in APPOINTMENT_SETTINGS_URL_NAMES)
            or (ns == "core" and url_name in CORE_SETTINGS_URL_NAMES)
        ),
        "messaging": ns == "messaging",
        "feedback": ns == "feedback",
        "notifications": bool(ns == "core" and url_name and "notification" in url_name),
        "user_management": bool(ns == "core" and "user_management" in view_full),
    }

    return {"nav_active": nav_active}
