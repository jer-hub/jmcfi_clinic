from django.apps import AppConfig


class DocumentRequestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'document_request'
    verbose_name = 'Document Request'

    def ready(self):
        import document_request.signals  # noqa: F401
