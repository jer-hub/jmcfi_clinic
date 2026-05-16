from django.apps import AppConfig


class MedicalRecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medical_records'

    def ready(self):
        from .signals import connect_medical_record_prescription_signals

        connect_medical_record_prescription_signals()
