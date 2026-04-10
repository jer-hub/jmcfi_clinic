from django.urls import re_path

from .consumers import ConversationConsumer, UnreadCountConsumer


websocket_urlpatterns = [
    re_path(r"^ws/messages/unread/$", UnreadCountConsumer.as_asgi()),
    re_path(r"^ws/messages/(?P<conversation_id>\d+)/$", ConversationConsumer.as_asgi()),
]