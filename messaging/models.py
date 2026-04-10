from django.conf import settings
from django.db import models
from django.utils import timezone


class ConversationQuerySet(models.QuerySet):
    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()

        return self.filter(
            participant_links__user=user,
            participant_links__is_active=True,
            is_active=True,
        ).distinct()


class Conversation(models.Model):
    class ConversationType(models.TextChoices):
        DIRECT = "direct", "Direct"
        ANNOUNCEMENT = "announcement", "Announcement"

    conversation_type = models.CharField(
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.DIRECT,
    )
    subject = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_message_conversations",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConversationParticipant",
        related_name="message_conversations",
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ["-last_message_at", "-updated_at", "-created_at"]

    def __str__(self):
        if self.conversation_type == self.ConversationType.ANNOUNCEMENT:
            return self.subject or f"Announcement {self.pk}"
        return self.subject or f"Conversation {self.pk}"

    def display_name_for(self, user):
        if self.conversation_type == self.ConversationType.ANNOUNCEMENT:
            return self.subject or "Announcement"

        participant_links = getattr(self, "prefetched_participant_links", None)
        if participant_links is None:
            participant_links = self.participant_links.select_related("user").filter(is_active=True)

        others = [
            str(link.user)
            for link in participant_links
            if link.user_id != getattr(user, "id", None)
        ]
        return ", ".join(others) if others else "Direct conversation"

    def mark_read(self, user):
        self.participant_links.filter(user=user, is_active=True).update(last_read_at=timezone.now())


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participant_links",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_participant_links",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("conversation", "user")
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.conversation}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk} in conversation {self.conversation_id}"

    def clean(self):
        body = (self.body or "").strip()
        if not body:
            from django.core.exceptions import ValidationError
            raise ValidationError({"body": "Message body cannot be empty."})

        if self.sender_id and self.conversation_id:
            participant_exists = self.conversation.participant_links.filter(
                user_id=self.sender_id,
                is_active=True,
            ).exists()
            if not participant_exists:
                from django.core.exceptions import ValidationError
                raise ValidationError({"sender": "Sender is not a participant in this conversation."})

    @property
    def preview(self):
        text = self.body.strip().replace("\n", " ")
        return text[:117] + "..." if len(text) > 120 else text