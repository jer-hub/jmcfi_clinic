from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, Subquery, OuterRef
from django.utils import timezone

from .forms import ANNOUNCEMENT_AUDIENCE_CHOICES, DIRECT_MESSAGE_ROLES
from .models import Conversation, ConversationParticipant, Message


User = get_user_model()
ANNOUNCEMENT_AUDIENCE_VALUES = {choice[0] for choice in ANNOUNCEMENT_AUDIENCE_CHOICES}


def can_start_direct_conversation(user):
    return getattr(user, "role", None) in DIRECT_MESSAGE_ROLES


def is_direct_pair_allowed(user_a, user_b):
    role_a = getattr(user_a, "role", None)
    role_b = getattr(user_b, "role", None)
    allowed = {
        frozenset(["student", "staff"]),
        frozenset(["student", "doctor"]),
    }
    return frozenset([role_a, role_b]) in allowed


def can_send_announcements(user):
    return getattr(user, "role", None) in {"admin", "staff", "doctor"}


def get_or_create_direct_conversation(sender, recipient):
    if not is_direct_pair_allowed(sender, recipient):
        raise PermissionError("Direct messaging is only allowed between students and staff/doctors.")

    conversation = (
        Conversation.objects.filter(
            conversation_type=Conversation.ConversationType.DIRECT,
            is_active=True,
        )
        .annotate(
            active_participants=Count(
                "participant_links",
                filter=Q(participant_links__is_active=True),
                distinct=True,
            ),
            sender_present=Count(
                "participant_links",
                filter=Q(participant_links__user=sender, participant_links__is_active=True),
                distinct=True,
            ),
            recipient_present=Count(
                "participant_links",
                filter=Q(participant_links__user=recipient, participant_links__is_active=True),
                distinct=True,
            ),
        )
        .filter(active_participants=2, sender_present=1, recipient_present=1)
        .distinct()
        .first()
    )
    if conversation:
        return conversation, False

    with transaction.atomic():
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.DIRECT,
            created_by=sender,
        )
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(conversation=conversation, user=sender, last_read_at=timezone.now()),
            ConversationParticipant(conversation=conversation, user=recipient),
        ])

    return conversation, True


def get_announcement_recipients(audience):
    if audience not in ANNOUNCEMENT_AUDIENCE_VALUES:
        return User.objects.none()

    if audience == "students":
        return User.objects.filter(role="student", is_active=True)
    if audience == "staff":
        return User.objects.filter(role="staff", is_active=True)
    if audience == "doctors":
        return User.objects.filter(role="doctor", is_active=True)
    if audience == "clinical_staff":
        return User.objects.filter(role__in=["staff", "doctor"], is_active=True)
    if audience == "non_students":
        return User.objects.filter(role__in=["staff", "doctor", "admin"], is_active=True)
    if audience == "admins":
        return User.objects.filter(role="admin", is_active=True)
    return User.objects.filter(is_active=True)


def get_user_conversation_or_none(user, conversation_id):
    return Conversation.objects.for_user(user).filter(pk=conversation_id).first()


def get_inbox_conversations(user):
    latest_message = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at")
    conversations = list(
        Conversation.objects.for_user(user)
        .prefetch_related(
            Prefetch(
                "participant_links",
                queryset=ConversationParticipant.objects.filter(is_active=True).select_related("user"),
                to_attr="prefetched_participant_links",
            )
        )
        .annotate(last_message_preview=Subquery(latest_message.values("body")[:1]))
        .order_by("-last_message_at", "-updated_at", "-created_at")
    )

    if not conversations:
        return []

    conversation_ids = [conversation.id for conversation in conversations]
    unread_rows = (
        Message.objects.filter(
            conversation_id__in=conversation_ids,
            conversation__participant_links__user=user,
            conversation__participant_links__is_active=True,
        )
        .exclude(sender=user)
        .filter(
            Q(conversation__participant_links__last_read_at__isnull=True)
            | Q(created_at__gt=F("conversation__participant_links__last_read_at"))
        )
        .values("conversation_id")
        .annotate(unread_count=Count("id"))
    )
    unread_map = {row["conversation_id"]: row["unread_count"] for row in unread_rows}

    for conversation in conversations:
        conversation.unread_count = unread_map.get(conversation.id, 0)
        conversation.display_title = conversation.display_name_for(user)
        last_preview = (conversation.last_message_preview or "").strip().replace("\n", " ")
        conversation.last_message_excerpt = last_preview[:117] + "..." if len(last_preview) > 120 else last_preview

    return conversations


def get_unread_message_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0

    return (
        Message.objects.filter(
            conversation__participant_links__user=user,
            conversation__participant_links__is_active=True,
            conversation__is_active=True,
        )
        .exclude(sender=user)
        .filter(
            Q(conversation__participant_links__last_read_at__isnull=True)
            | Q(created_at__gt=F("conversation__participant_links__last_read_at"))
        )
        .count()
    )


def get_unread_conversation_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0

    return (
        Message.objects.filter(
            conversation__participant_links__user=user,
            conversation__participant_links__is_active=True,
            conversation__is_active=True,
        )
        .exclude(sender=user)
        .filter(
            Q(conversation__participant_links__last_read_at__isnull=True)
            | Q(created_at__gt=F("conversation__participant_links__last_read_at"))
        )
        .values("conversation_id")
        .distinct()
        .count()
    )


def mark_conversation_read(conversation, user):
    updated = conversation.participant_links.filter(
        user=user,
        is_active=True,
    ).update(last_read_at=timezone.now())
    if updated:
        _publish_unread_count(user)


def send_conversation_message(conversation, sender, body):
    cleaned_body = (body or "").strip()
    if not cleaned_body:
        raise ValueError("Message body cannot be empty.")

    participant = conversation.participant_links.filter(user=sender, is_active=True).exists()
    if not participant:
        raise PermissionError("You are not allowed to send messages in this conversation.")
    if conversation.conversation_type == Conversation.ConversationType.DIRECT:
        direct_participants = list(
            conversation.participant_links.filter(is_active=True).select_related("user")
        )
        if len(direct_participants) != 2:
            raise PermissionError("Invalid direct conversation configuration.")

        first_user = direct_participants[0].user
        second_user = direct_participants[1].user
        if not is_direct_pair_allowed(first_user, second_user):
            raise PermissionError("Direct messaging is only allowed between students and staff/doctors.")

    if (
        conversation.conversation_type == Conversation.ConversationType.ANNOUNCEMENT
        and conversation.created_by_id != sender.pk
    ):
        raise PermissionError("Only the announcement sender can post in this thread.")

    with transaction.atomic():
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            body=cleaned_body,
        )
        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at)
        ConversationParticipant.objects.filter(conversation=conversation, user=sender).update(last_read_at=message.created_at)

        transaction.on_commit(lambda: _publish_message_created(message.pk))

    return message


def create_announcement_conversation(sender, subject, body, audience):
    recipients = list(get_announcement_recipients(audience).exclude(pk=sender.pk))
    if not recipients:
        raise ValueError("No recipients found for the selected audience.")

    subject = (subject or "").strip()
    if not subject:
        raise ValueError("Announcement title is required.")

    with transaction.atomic():
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.ANNOUNCEMENT,
            subject=subject,
            created_by=sender,
        )
        participant_rows = [
            ConversationParticipant(conversation=conversation, user=sender, last_read_at=timezone.now())
        ]
        participant_rows.extend(
            ConversationParticipant(conversation=conversation, user=recipient)
            for recipient in recipients
        )
        ConversationParticipant.objects.bulk_create(participant_rows)
        send_conversation_message(conversation, sender, body)

    return conversation, len(recipients)


def serialize_message(message):
    sender_name = message.sender.get_full_name() or str(message.sender)
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "body": message.body,
        "sender_id": message.sender_id,
        "sender_name": sender_name,
        "sender_role": message.sender.get_role_display(),
        "created_at": timezone.localtime(message.created_at).strftime("%b %d, %Y %I:%M %p"),
        "created_iso": message.created_at.isoformat(),
    }


def _publish_message_created(message_id):
    message = Message.objects.select_related("sender", "conversation").get(pk=message_id)
    payload = serialize_message(message)
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"conversation_{message.conversation_id}",
        {
            "type": "message_created",
            "message": payload,
        },
    )

    recipients = User.objects.filter(
        message_participant_links__conversation=message.conversation,
        message_participant_links__is_active=True,
    ).distinct()
    for recipient in recipients:
        _publish_unread_count(recipient, sender_id=message.sender_id, channel_layer=channel_layer)
        # Also publish conversation-specific update for sidebar
        _publish_conversation_update(recipient, message.conversation, sender_id=message.sender_id, channel_layer=channel_layer)


def _publish_unread_count(user, sender_id=None, channel_layer=None):
    if channel_layer is None:
        channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"user_messages_{user.pk}",
        {
            "type": "unread_count_event",
            "unread_count": get_unread_conversation_count(user),
            "sender_id": sender_id,
        },
    )


def _publish_conversation_update(user, conversation, sender_id=None, channel_layer=None):
    """Publish conversation updates for sidebar (unread count, last message, etc)"""
    if channel_layer is None:
        channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    # Get unread count specifically for this conversation
    participant = conversation.participant_links.filter(user=user, is_active=True).first()
    if not participant:
        return

    # Calculate unread count for this conversation
    query = Message.objects.filter(conversation=conversation).exclude(sender=user)
    if participant.last_read_at:
        unread_count = query.filter(created_at__gt=participant.last_read_at).count()
    else:
        unread_count = query.count()

    # Get last message preview
    last_message = conversation.messages.order_by('-created_at').first()
    last_message_preview = ""
    if last_message:
        preview = (last_message.body or "").strip().replace("\n", " ")
        last_message_preview = preview[:100] + "..." if len(preview) > 100 else preview

    async_to_sync(channel_layer.group_send)(
        f"user_messages_{user.pk}",
        {
            "type": "conversation_update",
            "conversation_id": conversation.id,
            "conversation_title": conversation.display_name_for(user),
            "unread_count": unread_count,
            "last_message_preview": last_message_preview,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            "sender_id": sender_id,
        },
    )