from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UsuarioDjango, PerfilFirebase
import uuid


@receiver(post_save, sender=UsuarioDjango)
def crear_perfil_firebase(sender, instance, created, **kwargs):
    """Crea un perfil en la tabla `perfiles` SOLO si la opción
    `CORE_SYNC_CREATE_PROFILES` en settings está activa.

    Esto evita escrituras automáticas en la base de datos por parte de Django
    cuando no se desea alterar el esquema o los datos existentes.
    """
    if not getattr(settings, 'CORE_SYNC_CREATE_PROFILES', False):
        # Protección: no crear perfiles automáticamente
        return

    if created and instance.email:
        perfil_existente = PerfilFirebase.objects.filter(correo=instance.email).first()

        if not perfil_existente:
            PerfilFirebase.objects.create(
                id=uuid.uuid4(),
                nombre=instance.first_name or instance.username,
                apellido=instance.last_name or '',
                correo=instance.email,
                tipo_usuario='comun',
                estado_cuenta=True,
                eco_puntos_saldo=0,
                created_at=instance.date_joined
            )
            print(f"Perfil Firebase creado para {instance.email}")