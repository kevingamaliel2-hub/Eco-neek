# core/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import redirect


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Este adaptador intercepta el flujo de Google OAuth.
    
    Si el usuario ya tiene cuenta → lo deja pasar normal.
    Si es cuenta nueva → lo manda a elegir tipo de cuenta (usuario o centro).
    """

    def pre_social_login(self, request, sociallogin):
        """
        Se ejecuta ANTES de que allauth cree/conecte la cuenta.
        Si el email ya existe en la BD, conecta la cuenta automáticamente
        sin crear un duplicado.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if sociallogin.is_existing:
            # Ya tiene cuenta, no hacer nada — entra directo
            return

        # Revisar si ya existe un usuario con ese email
        email = sociallogin.account.extra_data.get('email', '')
        if email:
            try:
                existing_user = User.objects.get(email=email)
                # Conectar la cuenta social al usuario existente
                sociallogin.connect(request, existing_user)
            except User.DoesNotExist:
                # Es cuenta nueva — el flujo continúa normal
                # y get_connect_url redirigirá a completar registro
                pass

    def get_connect_url(self, request, socialaccount):
        return '/completar-registro/'

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Permitir auto-signup para cuentas nuevas.
        Después de crearse, el adaptador redirige a completar perfil.
        """
        return True

    def save_user(self, request, sociallogin, form=None):
        """
        Guarda el usuario nuevo y marca su perfil como incompleto
        para que sea redirigido a completar registro.
        """
        user = super().save_user(request, sociallogin, form)
        user.profile_completed = False
        user.save()
        return user

    def get_login_redirect_url(self, request):
        """
        Después del login con Google:
        - Si el perfil está completo → va al home
        - Si NO está completo → va a completar registro
        """
        user = request.user
        if not user.is_authenticated:
            return '/'
        if not user.profile_completed:
            return '/completar-registro/'
        return '/'