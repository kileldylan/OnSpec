import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ACIApp", "0013_github_app_delivery_outputs"),
    ]

    operations = [
        migrations.CreateModel(
            name="GitHubWebhookJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("delivery_id", models.CharField(max_length=100, unique=True)),
                ("event", models.CharField(max_length=50)),
                ("payload", models.JSONField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("available_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["status", "available_at", "received_at"],
                        name="ACIApp_gith_status_b5bbbf_idx",
                    ),
                ],
            },
        ),
    ]
