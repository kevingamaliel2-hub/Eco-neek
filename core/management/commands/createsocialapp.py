from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create or update Google SocialApp from env vars'

    def handle(self, *args, **options):
        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
        except Exception as e:
            self.stderr.write('django-allauth not installed or migrations not applied: %s' % e)
            return

        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
        secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
        if not client_id or not secret:
            self.stderr.write('GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in settings')
            return

        site = Site.objects.get(pk=settings.SITE_ID)
        app, created = SocialApp.objects.get_or_create(provider='google', defaults={
            'name': 'Google',
            'client_id': client_id,
            'secret': secret,
        })
        if not created:
            app.client_id = client_id
            app.secret = secret
            app.name = 'Google'
            app.save()

        app.sites.add(site)
        self.stdout.write('SocialApp for Google ensured (created=%s)' % created)
