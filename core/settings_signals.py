"""Invalidate settings cache when clinic or role settings change."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ClinicSettings, RoleSettings
from .settings_service import invalidate_settings_cache


@receiver(post_save, sender=ClinicSettings)
def clinic_settings_saved(sender, instance, **kwargs):
    invalidate_settings_cache()


@receiver(post_save, sender=RoleSettings)
def role_settings_saved(sender, instance, **kwargs):
    invalidate_settings_cache(role=instance.role)


@receiver(post_delete, sender=RoleSettings)
def role_settings_deleted(sender, instance, **kwargs):
    invalidate_settings_cache(role=instance.role)
