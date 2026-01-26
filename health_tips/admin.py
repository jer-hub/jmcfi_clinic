from django.contrib import admin
from .models import HealthTip


@admin.register(HealthTip)
class HealthTipAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'is_active', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('category', 'is_active', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['make_active', 'make_inactive']

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Mark selected tips as active"

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Mark selected tips as inactive"
