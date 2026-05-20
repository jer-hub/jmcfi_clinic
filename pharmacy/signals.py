from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from pharmacy.models import Batch
from pharmacy.services.stock_snapshot import refresh_medicine_stock_cache


@receiver(post_save, sender=Batch)
def refresh_stock_cache_on_batch_save(sender, instance, **kwargs):
    refresh_medicine_stock_cache(instance.medicine_id)


@receiver(post_delete, sender=Batch)
def refresh_stock_cache_on_batch_delete(sender, instance, **kwargs):
    refresh_medicine_stock_cache(instance.medicine_id)
