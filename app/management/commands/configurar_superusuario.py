import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Substitui os superusuários por uma conta administrativa definida.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        senha = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not senha:
            raise CommandError('DJANGO_SUPERUSER_PASSWORD não foi definida.')

        modelo = get_user_model()
        modelo.objects.filter(is_superuser=True).delete()
        usuario, _ = modelo.objects.get_or_create(username=options['usuario'])
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.is_active = True
        usuario.set_password(senha)
        usuario.save()

        self.stdout.write(self.style.SUCCESS(
            f'Superusuário {usuario.username} configurado com sucesso.'
        ))
