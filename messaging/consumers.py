from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import get_unread_conversation_count, send_conversation_message


class UnreadCountConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_messages_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            "type": "unread_count",
            "unread_count": await self._get_unread_count(),
        })

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def unread_count_event(self, event):
        await self.send_json({
            "type": "unread_count",
            "unread_count": event["unread_count"],
            "sender_id": event.get("sender_id"),
        })

    async def conversation_update(self, event):
        """Handle real-time conversation updates (unread count, new messages, etc)"""
        await self.send_json({
            "type": "conversation_update",
            "conversation_id": event["conversation_id"],
            "conversation_title": event["conversation_title"],
            "unread_count": event["unread_count"],
            "last_message_preview": event["last_message_preview"],
            "last_message_at": event["last_message_at"],
            "sender_id": event.get("sender_id"),
        })

    @database_sync_to_async
    def _get_unread_count(self):
        return get_unread_conversation_count(self.scope["user"])


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.conversation_id = int(self.scope["url_route"]["kwargs"]["conversation_id"])
        is_allowed = await self._user_has_access()
        if not is_allowed:
            await self.close()
            return

        self.group_name = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = (content.get("body") or "").strip()
        if not body:
            await self.send_json({"type": "error", "message": "Message body cannot be empty."})
            return

        try:
            await self._create_message(body)
        except PermissionError:
            await self.send_json({"type": "error", "message": "Access denied."})
        except ValueError as exc:
            await self.send_json({"type": "error", "message": str(exc)})

    async def message_created(self, event):
        await self.send_json({
            "type": "message_created",
            "message": event["message"],
        })

    @database_sync_to_async
    def _user_has_access(self):
        from .models import ConversationParticipant

        return ConversationParticipant.objects.filter(
            conversation_id=self.conversation_id,
            user=self.scope["user"],
            is_active=True,
            conversation__is_active=True,
        ).exists()

    @database_sync_to_async
    def _create_message(self, body):
        from .models import Conversation

        conversation = Conversation.objects.get(pk=self.conversation_id)
        send_conversation_message(conversation, self.scope["user"], body)