# Generated by Django 4.0.3 on 2022-04-06 08:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentik_tenants", "0002_tenant_flow_user_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
