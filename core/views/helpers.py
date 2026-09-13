"""Shared private helpers for core views."""

import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

from core.models import AccountProvisioningAudit, UserInvite
from core.utils import get_client_ip

INVITE_TOKEN_TTL_HOURS = getattr(settings, 'USER_INVITE_TOKEN_TTL_HOURS', 72)

_get_client_ip = get_client_ip


def _hash_invite_token(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _create_user_invite(user, created_by):
    now = timezone.now()
    UserInvite.objects.filter(
        user=user,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    raw_token = secrets.token_urlsafe(32)
    invite = UserInvite.objects.create(
        user=user,
        created_by=created_by,
        token_hash=_hash_invite_token(raw_token),
        expires_at=now + timezone.timedelta(hours=INVITE_TOKEN_TTL_HOURS),
    )
    return invite, raw_token


def _log_provisioning_action(request, actor, target_user, action, metadata=None):
    AccountProvisioningAudit.objects.create(
        actor=actor,
        target_user=target_user,
        action=action,
        ip_address=_get_client_ip(request),
        metadata=metadata or {},
    )
