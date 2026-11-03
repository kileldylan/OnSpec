from django.apps import AppConfig


class AciappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ACI_backend.ACIApp'

    def ready(self):
        from ACI_backend.ACIApp import checks
