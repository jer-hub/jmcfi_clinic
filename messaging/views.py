from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required

from .forms import AnnouncementForm, MessageForm, StartConversationForm
from .models import Conversation
from .services import (
    can_send_announcements,
    can_start_direct_conversation,
    create_announcement_conversation,
    get_inbox_conversations,
    get_or_create_direct_conversation,
    get_user_conversation_or_none,
    mark_conversation_read,
    serialize_message,
    send_conversation_message,
)


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


def _get_conversation_or_404(request, conversation_id):
    conversation = get_user_conversation_or_none(request.user, conversation_id)
    if conversation is None:
        raise Http404("Conversation not found.")
    return conversation


@login_required
def inbox(request):
    conversations = get_inbox_conversations(request.user)
    can_broadcast = can_send_announcements(request.user)
    active_panel = "broadcast" if can_broadcast and request.GET.get("panel") == "broadcast" else "chat"
    context = {
        "conversations": conversations,
        "can_start_direct": can_start_direct_conversation(request.user),
        "can_send_announcements": can_broadcast,
        "announcement_form": AnnouncementForm() if can_broadcast else None,
        "active_panel": active_panel,
    }
    return render(request, "messaging/inbox.html", context)


@login_required
@role_required("student", "staff", "doctor")
def start_conversation(request):
    if request.method == "POST":
        form = StartConversationForm(request.POST, user=request.user)
        if form.is_valid():
            recipient = form.cleaned_data["recipient"]
            conversation, _ = get_or_create_direct_conversation(request.user, recipient)
            send_conversation_message(conversation, request.user, form.cleaned_data["body"])
            messages.success(request, "Secure conversation started.")
            return redirect("messaging:conversation_detail", conversation_id=conversation.id)
    else:
        form = StartConversationForm(user=request.user)

    return render(request, "messaging/start_conversation.html", {"form": form})


@login_required
def conversation_detail(request, conversation_id):
    conversation = _get_conversation_or_404(request, conversation_id)
    message_form = MessageForm()
    messages_qs = conversation.messages.select_related("sender").order_by("created_at")
    mark_conversation_read(conversation, request.user)
    conversations = get_inbox_conversations(request.user)

    context = {
        "conversation": conversation,
        "conversations": conversations,
        "conversation_title": conversation.display_name_for(request.user),
        "messages_list": messages_qs,
        "message_form": message_form,
        "can_start_direct": can_start_direct_conversation(request.user),
        "can_send_announcements": can_send_announcements(request.user),
        "can_reply": (
            conversation.conversation_type != Conversation.ConversationType.ANNOUNCEMENT
            or conversation.created_by_id == request.user.id
        ),
    }
    return render(request, "messaging/conversation_detail.html", context)


@login_required
@require_POST
def send_message(request, conversation_id):
    conversation = _get_conversation_or_404(request, conversation_id)
    form = MessageForm(request.POST)
    if not form.is_valid():
        if _wants_json(request):
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)
        messages.error(request, "Message body is required.")
        return redirect("messaging:conversation_detail", conversation_id=conversation.id)

    try:
        message = send_conversation_message(conversation, request.user, form.cleaned_data["body"])
    except PermissionError:
        if _wants_json(request):
            return JsonResponse({"status": "error", "message": "Access denied."}, status=403)
        messages.error(request, "Access denied.")
        return redirect("messaging:inbox")
    except ValueError as exc:
        if _wants_json(request):
            return JsonResponse({"status": "error", "message": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("messaging:conversation_detail", conversation_id=conversation.id)

    if _wants_json(request):
        return JsonResponse({
            "status": "success",
            "message": serialize_message(message),
        })
    return redirect("messaging:conversation_detail", conversation_id=conversation.id)


@login_required
@require_GET
def conversation_updates(request, conversation_id):
    conversation = _get_conversation_or_404(request, conversation_id)
    last_id_raw = request.GET.get("after") or "0"
    try:
        last_id = int(last_id_raw)
    except ValueError:
        last_id = 0

    recent_messages = list(
        conversation.messages.select_related("sender")
        .filter(id__gt=last_id)
        .order_by("id")[:50]
    )
    payload = [serialize_message(message) for message in recent_messages]

    if any(message.sender_id != request.user.id for message in recent_messages):
        mark_conversation_read(conversation, request.user)

    return JsonResponse({"status": "success", "messages": payload})


@login_required
@require_POST
def mark_read(request, conversation_id):
    conversation = _get_conversation_or_404(request, conversation_id)
    mark_conversation_read(conversation, request.user)
    return JsonResponse({"status": "success"})


@login_required
@role_required("admin", "staff", "doctor")
def create_announcement(request):
    if request.method != "POST":
        return redirect(f"{reverse('messaging:inbox')}?panel=broadcast")

    form = AnnouncementForm(request.POST)
    if form.is_valid():
        try:
            conversation, recipients_count = create_announcement_conversation(
                request.user,
                form.cleaned_data["title"],
                form.cleaned_data["body"],
                form.cleaned_data["audience"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Announcement sent to {recipients_count} recipients.")
            return redirect("messaging:conversation_detail", conversation_id=conversation.id)

    conversations = get_inbox_conversations(request.user)
    context = {
        "conversations": conversations,
        "can_start_direct": can_start_direct_conversation(request.user),
        "can_send_announcements": True,
        "announcement_form": form,
        "active_panel": "broadcast",
    }
    return render(request, "messaging/inbox.html", context, status=400)