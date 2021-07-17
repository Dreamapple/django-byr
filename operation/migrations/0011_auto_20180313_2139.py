# Generated by Django 2.0.2 on 2018-03-13 21:39

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('operation', '0010_balanceinfo_last_balance'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='signedinfo',
            options={'verbose_name': '用户签到', 'verbose_name_plural': '用户签到'},
        ),
        migrations.AlterField(
            model_name='balanceinfo',
            name='marks',
            field=models.CharField(max_length=100, verbose_name='备注'),
        ),
        migrations.AlterField(
            model_name='signedinfo',
            name='date',
            field=models.CharField(max_length=30, verbose_name='签到日期'),
        ),
        migrations.AlterUniqueTogether(
            name='signedinfo',
            unique_together={('user', 'signed_day')},
        ),
    ]
