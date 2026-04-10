from django.urls import path

from . import views


app_name = "messaging"


urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("new/", views.start_conversation, name="start_conversation"),
    path("announcements/new/", views.create_announcement, name="create_announcement"),
    path("<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
    path("<int:conversation_id>/updates/", views.conversation_updates, name="conversation_updates"),
    path("<int:conversation_id>/send/", views.send_message, name="send_message"),
    path("<int:conversation_id>/read/", views.mark_read, name="mark_read"),
]