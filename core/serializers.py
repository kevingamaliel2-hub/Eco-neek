# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Centro, Material, Premio, Canje, Evento, Sugerencia, PerfilFirebase, UsuarioDjango

User = UsuarioDjango


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'telefono')
        read_only_fields = ('id',)


class PerfilFirebaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilFirebase
        fields = ('id', 'nombre', 'apellido', 'telefono', 'imagen_url', 
                  'eco_puntos_saldo', 'correo', 'tipo_usuario', 'qr_codigo')
        read_only_fields = ('id', 'eco_puntos_saldo')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name', 'telefono')
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CentroSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='nombre_comercial')
    direccion = serializers.CharField(source='direccion_texto')
    telefono = serializers.CharField(source='telefono_contacto')
    email = serializers.EmailField(source='correo_contacto')
    
    class Meta:
        model = Centro
        fields = ('id', 'nombre', 'direccion', 'latitud', 'longitud', 
                  'telefono', 'email', 'descripcion', 'url_foto_portada',
                  'promedio_calificacion', 'estado_operativo', 'validado')
        read_only_fields = ('promedio_calificacion',)


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ('id', 'nombre', 'unidad_medida', 'puntos_por_unidad', 'icono_url')


class PremioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Premio
        fields = ('id', 'nombre', 'descripcion', 'puntos_requeridos', 'imagen_url', 'disponible')


class CanjeSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    premio_nombre = serializers.CharField(source='tipo_recompensa', read_only=True)
    
    class Meta:
        model = Canje
        fields = ('id', 'id_usuario', 'usuario_nombre', 'tipo_recompensa', 'premio_nombre',
                  'monto_puntos_restados', 'fecha_canje', 'estado')
        read_only_fields = ('fecha_canje',)
    
    def get_usuario_nombre(self, obj):
        if obj.id_usuario:
            return f"{obj.id_usuario.nombre} {obj.id_usuario.apellido or ''}"
        return ""


class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = ('id', 'titulo', 'descripcion', 'fecha_evento', 
                  'ubicacion', 'imagen_url', 'creado_por')


class SugerenciaSerializer(serializers.ModelSerializer):
    usuario_email = serializers.EmailField(source='usuario.correo', read_only=True)
    usuario_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = Sugerencia
        fields = ('id', 'usuario', 'usuario_email', 'usuario_nombre', 'tipo', 'mensaje', 'fecha', 'leida')
        read_only_fields = ('fecha',)
    
    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f"{obj.usuario.nombre} {obj.usuario.apellido or ''}"
        return ""