# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UsuarioDjango, PerfilFirebase, Centro, Material, Premio, Canje, Evento, Sugerencia


@admin.register(UsuarioDjango)
class UsuarioDjangoAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('telefono',)}),
    )


@admin.register(PerfilFirebase)
class PerfilFirebaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'correo', 'tipo_usuario', 'eco_puntos_saldo')
    list_filter = ('tipo_usuario', 'estado_cuenta')
    search_fields = ('nombre', 'apellido', 'correo')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)


@admin.register(Centro)
class CentroAdmin(admin.ModelAdmin):
    list_display = ('nombre_comercial', 'direccion_texto', 'validado', 'estado_operativo')
    list_filter = ('validado', 'estado_operativo')
    search_fields = ('nombre_comercial', 'direccion_texto', 'correo_contacto')
    list_editable = ('validado', 'estado_operativo')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'puntos_por_unidad')
    search_fields = ('nombre',)


@admin.register(Premio)
class PremioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'puntos_requeridos', 'disponible')
    list_filter = ('disponible',)
    list_editable = ('disponible',)


@admin.register(Canje)
class CanjeAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_usuario', 'tipo_recompensa', 'monto_puntos_restados', 'estado', 'fecha_canje')
    list_filter = ('estado',)
    search_fields = ('id_usuario__correo', 'tipo_recompensa')
    readonly_fields = ('id', 'fecha_canje')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'fecha_evento', 'ubicacion')
    search_fields = ('titulo', 'ubicacion')
    ordering = ('-fecha_evento',)


@admin.register(Sugerencia)
class SugerenciaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'fecha', 'leida')
    list_filter = ('tipo', 'leida')
    list_editable = ('leida',)