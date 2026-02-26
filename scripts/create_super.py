from core.models import UsuarioDjango
u = 'admin'
if not UsuarioDjango.objects.filter(username=u).exists():
    UsuarioDjango.objects.create_superuser(username='admin', email='admin@localhost', password='Admin1234')
    print('Superuser created')
else:
    print('Superuser exists')
