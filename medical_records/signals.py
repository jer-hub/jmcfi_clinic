from django.db.models.signals import post_delete, post_save
from django.utils import timezone

from medical_records.models import MedicalRecord


def _resync_medical_record_status(medical_record_id):
    if not medical_record_id:
        return
    mr = (
        MedicalRecord.objects.select_related('appointment')
        .prefetch_related('prescription_record__items')
        .filter(pk=medical_record_id)
        .first()
    )
    if mr is None:
        return
    new_status = mr.compute_status_value()
    if new_status != mr.status:
        MedicalRecord.objects.filter(pk=mr.pk).update(status=new_status, updated_at=timezone.now())


def _prescription_saved(sender, instance, **kwargs):
    _resync_medical_record_status(instance.medical_record_id)


def _prescription_item_changed(sender, instance, **kwargs):
    _resync_medical_record_status(instance.prescription.medical_record_id)


def connect_medical_record_prescription_signals():
    from health_forms_services.models import Prescription, PrescriptionItem

    post_save.connect(
        _prescription_saved,
        sender=Prescription,
        dispatch_uid='medical_records_prescription_post_save',
    )
    post_delete.connect(
        _prescription_saved,
        sender=Prescription,
        dispatch_uid='medical_records_prescription_post_delete',
    )
    post_save.connect(
        _prescription_item_changed,
        sender=PrescriptionItem,
        dispatch_uid='medical_records_rx_item_post_save',
    )
    post_delete.connect(
        _prescription_item_changed,
        sender=PrescriptionItem,
        dispatch_uid='medical_records_rx_item_post_delete',
    )
