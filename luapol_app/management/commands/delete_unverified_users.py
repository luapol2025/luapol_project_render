from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from luapol_app.models import UserProfile
from datetime import timedelta

class Command(BaseCommand):
    help = 'Delete users who have not verified their email within 30 minutes of registration.'

    def handle(self, *args, **kwargs):
        # Determinar la hora de expiración (30 minutos antes de la hora actual)
        expiration_time = timezone.now() - timedelta(minutes=30)
        
        # Filtrar perfiles de usuario que no han verificado su email y cuyo perfil fue creado hace más de 30 minutos
        unverified_profiles = UserProfile.objects.filter(is_email_verified=False, user__date_joined__lt=expiration_time)
        
        for profile in unverified_profiles:
            user = profile.user
            user.delete()  # Elimina el usuario junto con su perfil asociado y datos relacionados
            self.stdout.write(self.style.SUCCESS(f'Deleted unverified user: {user.username}'))
