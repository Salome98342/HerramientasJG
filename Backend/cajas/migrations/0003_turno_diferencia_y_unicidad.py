from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('cajas', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='turnocaja',
            name='diferencia',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddConstraint(
            model_name='turnocaja',
            constraint=models.UniqueConstraint(
                fields=('negocio', 'usuario'),
                condition=Q(estado='ABIERTO'),
                name='uq_turno_abierto_usuario',
            ),
        ),
        migrations.AddConstraint(
            model_name='turnocaja',
            constraint=models.UniqueConstraint(
                fields=('negocio', 'caja'),
                condition=Q(estado='ABIERTO'),
                name='uq_turno_abierto_caja',
            ),
        ),
    ]
