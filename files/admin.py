from django.contrib import admin

from .models import DriveItem


@admin.register(DriveItem)
class DriveItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'owner', 'parent', 'size_bytes', 'trashed_at', 'updated_at')
    list_filter = ('kind',)
    search_fields = ('name', 'owner__email')
    raw_id_fields = ('owner', 'parent')
