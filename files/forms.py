from django import forms

from .models import DriveItem


class CreateFolderForm(forms.Form):
    name = forms.CharField(max_length=255, strip=True)
    parent_id = forms.IntegerField(required=False)


class RenameItemForm(forms.Form):
    name = forms.CharField(max_length=255, strip=True)


class MoveItemForm(forms.Form):
    parent_id = forms.IntegerField(required=False)


class UploadFilesForm(forms.Form):
    parent_id = forms.IntegerField(required=False)
    files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True}),
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        # Multi-file comes from request.FILES.getlist in the view.
        return cleaned
