from django.apps import AppConfig


class RequoraAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Requora_backend.RequoraApp'
    verbose_name = 'Requora'
    label = 'ACIApp'

    def ready(self):
        from Requora_backend.RequoraApp import checks
