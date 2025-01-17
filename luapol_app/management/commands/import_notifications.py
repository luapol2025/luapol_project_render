import os
from django.core.management.base import BaseCommand
from luapol_app.models import Notifications, User
from django.utils.timezone import now

class Command(BaseCommand):
    help = 'Importar 23 notificaciones para el usuario con ID 3 a la base de datos'

    def handle(self, *args, **kwargs):
        # Obtener el usuario con ID 3
        try:
            user = User.objects.get(id=3)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("No existe un usuario con ID 3 en la base de datos."))
            return

        try:
            # Crear las notificaciones
            notifications_data = [
                Notifications(
                    id=f"notif_{i+1}",
                    user_fk=user,
                    subject=f"Notification Subject {i+1}",
                    message=f"This is the detail of notification {i+1}",
                    is_read=False,
                    created_at=now(),
                )
                for i in range(23)
            ]

            # Insertar las notificaciones en la base de datos
            Notifications.objects.bulk_create(notifications_data)

            self.stdout.write(self.style.SUCCESS("23 notificaciones añadidas con éxito al usuario con ID 3."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al importar notificaciones: {str(e)}"))
