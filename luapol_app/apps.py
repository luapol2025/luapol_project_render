from django.apps import AppConfig


class LuapolAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'luapol_app'

    def ready(self):
        import luapol_app.signals  # Registrar las señales
