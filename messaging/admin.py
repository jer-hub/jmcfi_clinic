from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    autocomplete_fields = ("user",)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    autocomplete_fields = ("sender",)
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_type", "subject", "created_by", "last_message_at", "is_active")
    list_filter = ("conversation_type", "is_active", "created_at")
    search_fields = ("subject", "created_by__first_name", "created_by__last_name", "created_by__email")
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    inlines = [ConversationParticipantInline, MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
    list_filter = ("created_at", "conversation__conversation_type")
    search_fields = ("body", "sender__first_name", "sender__last_name", "sender__email")
    readonly_fields = ("created_at",)


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("conversation", "user", "joined_at", "last_read_at", "is_active")
    list_filter = ("is_active", "joined_at")
    search_fields = ("user__first_name", "user__last_name", "user__email", "conversation__subject")
    readonly_fields = ("joined_at",)