# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class UsuarioDjango(AbstractUser):
    """Usuario para el panel de administración de Django (tabla auth_user)"""
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        verbose_name = 'Usuario Admin'
        verbose_name_plural = 'Usuarios Admin'
    
    def __str__(self):
        return f"{self.username} - {self.email}"


class PerfilFirebase(models.Model):
    """SOLO LECTURA - Mapea la tabla perfiles de Supabase (usuarios de Firebase)"""
    id = models.UUIDField(primary_key=True)
    nombre = models.TextField()
    apellido = models.TextField(blank=True, null=True)
    telefono = models.TextField(blank=True, null=True)
    imagen_url = models.TextField(blank=True, null=True)
    eco_puntos_saldo = models.IntegerField(default=0)
    correo = models.TextField(unique=True)
    tipo_usuario = models.TextField()
    estado_cuenta = models.BooleanField(default=True)
    qr_codigo = models.TextField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'perfiles'
        managed = False
        verbose_name = 'Perfil (Firebase)'
        verbose_name_plural = 'Perfiles (Firebase)'
    
    def __str__(self):
        return f"{self.nombre} {self.apellido or ''} ({self.correo})"


class Centro(models.Model):
    """Centros de acopio - usando tabla centros_acopio de Supabase"""
    id = models.BigAutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        PerfilFirebase, on_delete=models.CASCADE,
        db_column='id_usuario', blank=True, null=True,
        related_name='centros'
    )
    nombre_comercial = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    direccion_texto = models.TextField()
    latitud = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitud = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True)
    correo_contacto = models.EmailField(blank=True, null=True)
    url_foto_portada = models.URLField(blank=True, null=True)
    promedio_calificacion = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    estado_operativo = models.BooleanField(default=True)
    validado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    # Campos legacy
    name = models.CharField(max_length=255)
    address = models.TextField()
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        UsuarioDjango, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='centros_creados'
    )

    class Meta:
        db_table = 'centros_acopio'
        managed = False
        verbose_name = 'Centro de Acopio'
        verbose_name_plural = 'Centros de Acopio'

    def save(self, *args, **kwargs):
        """Sincronizar campos"""
        if not self.nombre_comercial and self.name:
            self.nombre_comercial = self.name
        if not self.direccion_texto and self.address:
            self.direccion_texto = self.address
        if not self.telefono_contacto and self.contact_phone:
            self.telefono_contacto = self.contact_phone
        if not self.correo_contacto and self.contact_email:
            self.correo_contacto = self.contact_email
        if not self.latitud and self.latitude:
            self.latitud = self.latitude
        if not self.longitud and self.longitude:
            self.longitud = self.longitude
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_comercial or self.name


class Material(models.Model):
    """Catálogo de materiales"""
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=20)
    icono_url = models.URLField(blank=True, null=True)
    puntos_por_unidad = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'catalogo_materiales'
        managed = False
        verbose_name = 'Material'
        verbose_name_plural = 'Materiales'

    def __str__(self):
        return self.nombre


class Premio(models.Model):
    """Recompensas"""
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    puntos_requeridos = models.IntegerField()
    imagen_url = models.URLField(blank=True, null=True)
    disponible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    class Meta:
        db_table = 'recompensas'
        managed = False
        verbose_name = 'Premio'
        verbose_name_plural = 'Premios'

    def __str__(self):
        return self.nombre


class Canje(models.Model):
    """Canjes de premios"""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('exitoso', 'Exitoso'),
        ('fallido', 'Fallido'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        PerfilFirebase, on_delete=models.CASCADE,
        db_column='id_usuario', blank=True, null=True
    )
    tipo_recompensa = models.CharField(max_length=50)
    monto_puntos_restados = models.IntegerField()
    monto_dinero_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fecha_canje = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    
    class Meta:
        db_table = 'canjes'
        managed = False
        verbose_name = 'Canje'
        verbose_name_plural = 'Canjes'

    def __str__(self):
        return f"Canje #{self.id} - {self.monto_puntos_restados} pts"


class Evento(models.Model):
    """Eventos"""
    id = models.BigAutoField(primary_key=True)
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    fecha_evento = models.DateTimeField()
    ubicacion = models.TextField(blank=True, null=True)
    imagen_url = models.URLField(blank=True, null=True)
    creado_por = models.ForeignKey(
        PerfilFirebase, on_delete=models.SET_NULL,
        db_column='creado_por', blank=True, null=True,
        related_name='eventos_creados'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    class Meta:
        db_table = 'eventos'
        managed = False
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    def __str__(self):
        return self.titulo


class Sugerencia(models.Model):
    """Sugerencias"""
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        PerfilFirebase, on_delete=models.CASCADE, 
        related_name='sugerencias'
    )
    tipo = models.CharField(max_length=50)
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'sugerencias'
        managed = False
        verbose_name = 'Sugerencia'
        verbose_name_plural = 'Sugerencias'

    def __str__(self):
        return f"Sugerencia de {self.usuario.correo}"