from django import forms
from django.contrib.auth import get_user_model


User = get_user_model()


DIRECT_MESSAGE_ROLES = ["student", "staff", "doctor"]
ANNOUNCEMENT_AUDIENCE_CHOICES = [
    ("all_active", "All active users"),
    ("students", "Students only"),
    ("staff", "Staff only"),
    ("doctors", "Doctors only"),
    ("clinical_staff", "Staff and doctors"),
    ("non_students", "Staff, doctors, and admins"),
    ("admins", "Admins only"),
]


class StartConversationForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Recipient",
        widget=forms.Select(attrs={
            "class": "block w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200",
        }),
    )
    body = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            "rows": 5,
            "class": "block w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200",
        }),
        max_length=4000,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        user_role = getattr(user, "role", None)
        allowed_recipient_roles = []
        if user_role == "student":
            allowed_recipient_roles = ["staff", "doctor"]
        elif user_role in {"staff", "doctor"}:
            allowed_recipient_roles = ["student"]

        self.fields["recipient"].queryset = User.objects.filter(
            role__in=allowed_recipient_roles,
            is_active=True,
        ).exclude(pk=getattr(user, "pk", None)).order_by("first_name", "last_name", "email")


class MessageForm(forms.Form):
    body = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Write a secure message...",
            "class": "block min-h-[3.25rem] w-full rounded-2xl border border-gray-300 px-3 py-2.5 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200 sm:min-h-[4rem] sm:px-4 sm:py-3",
        }),
        max_length=4000,
    )


class AnnouncementForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "block w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200",
        }),
    )
    audience = forms.ChoiceField(
        choices=ANNOUNCEMENT_AUDIENCE_CHOICES,
        widget=forms.Select(attrs={
            "class": "block w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200",
        }),
    )
    body = forms.CharField(
        label="Announcement",
        widget=forms.Textarea(attrs={
            "rows": 6,
            "class": "block w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200",
        }),
        max_length=4000,
    )