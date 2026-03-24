from django.shortcuts import redirect
from django.urls import reverse
from django_otp import user_has_device
from django.contrib.auth.decorators import login_required

class TwoFactorMiddleware:
    """
    Middleware que redirige a usuarios staff/admin sin 2FA configurado
    a la página de setup de 2FA.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            # Si es staff y no tiene dispositivo 2FA, redirige a setup
            if not user_has_device(request.user):
                # Evita loop infinito en páginas de 2FA
                if not request.path.startswith('/account/two_factor/'):
                    return redirect('two_factor:setup')
        return self.get_response(request)