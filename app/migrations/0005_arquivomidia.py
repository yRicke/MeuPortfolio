from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0004_projeto_data_desenvolvimento_imagemprojeto'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArquivoMidia',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('nome', models.CharField(max_length=500, unique=True)),
                ('conteudo', models.BinaryField(editable=False)),
                (
                    'tipo_conteudo',
                    models.CharField(
                        default='application/octet-stream',
                        max_length=255,
                    ),
                ),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'arquivo de mídia',
                'verbose_name_plural': 'arquivos de mídia',
                'ordering': ('nome',),
            },
        ),
    ]
