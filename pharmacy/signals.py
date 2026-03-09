from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Batch, Medicine


@receiver(post_save, sender=Batch)
def check_stock_alerts(sender, instance, **kwargs):
    """After a batch is saved, check if the medicine needs stock alerts."""
    medicine = instance.medicine
    # We could create notifications here for low stock or expiry
    # This is a placeholder for future automated notification logic
    pass
