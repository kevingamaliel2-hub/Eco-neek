# core/api.py

from rest_framework import viewsets, permissions, generics, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Centro, Material, Premio, Canje, Evento, Sugerencia, PerfilFirebase, UsuarioDjango
from .serializers import (
    UserSerializer, RegisterSerializer, CentroSerializer,
    MaterialSerializer, PremioSerializer, CanjeSerializer, 
    EventoSerializer, SugerenciaSerializer, PerfilFirebaseSerializer
)

User = UsuarioDjango


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class PerfilFirebaseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PerfilFirebase.objects.all()
    serializer_class = PerfilFirebaseSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            perfil = PerfilFirebase.objects.get(correo=request.user.email)
            serializer = self.get_serializer(perfil)
            return Response(serializer.data)
        except PerfilFirebase.DoesNotExist:
            return Response({'error': 'Perfil no encontrado'}, status=404)


class CentroViewSet(viewsets.ModelViewSet):
    queryset = Centro.objects.all()
    serializer_class = CentroSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    
    @action(detail=False, methods=['get'])
    def cercanos(self, request):
        """Endpoint para centros cercanos (lat, lng)"""
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        # Lógica simplificada - puedes añadir cálculo de distancia después
        centros = self.get_queryset().filter(estado_operativo=True, validado=True)[:20]
        serializer = self.get_serializer(centros, many=True)
        return Response(serializer.data)


class MaterialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = (permissions.AllowAny,)


class PremioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Premio.objects.filter(disponible=True)
    serializer_class = PremioSerializer
    permission_classes = (permissions.AllowAny,)


class CanjeViewSet(viewsets.ModelViewSet):
    serializer_class = CanjeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Canje.objects.all()
        
        try:
            perfil = PerfilFirebase.objects.get(correo=user.email)
            return Canje.objects.filter(id_usuario=perfil)
        except PerfilFirebase.DoesNotExist:
            return Canje.objects.none()

    def perform_create(self, serializer):
        try:
            perfil = PerfilFirebase.objects.get(correo=self.request.user.email)
            serializer.save(id_usuario=perfil)
        except PerfilFirebase.DoesNotExist:
            raise serializers.ValidationError("Perfil de usuario no encontrado")


class EventoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Evento.objects.all().order_by('-fecha_evento')
    serializer_class = EventoSerializer
    permission_classes = (permissions.AllowAny,)


class SugerenciaViewSet(viewsets.ModelViewSet):
    queryset = Sugerencia.objects.all()
    serializer_class = SugerenciaSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Sugerencia.objects.all()
        
        try:
            perfil = PerfilFirebase.objects.get(correo=user.email)
            return Sugerencia.objects.filter(usuario=perfil)
        except PerfilFirebase.DoesNotExist:
            return Sugerencia.objects.none()

    def perform_create(self, serializer):
        try:
            perfil = PerfilFirebase.objects.get(correo=self.request.user.email)
            serializer.save(usuario=perfil)
        except PerfilFirebase.DoesNotExist:
            raise serializers.ValidationError("Perfil de usuario no encontrado")
        