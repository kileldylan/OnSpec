from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ACIApp", "0012_githubaccount"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="github_installation_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pullrequest",
            name="aci_comment_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pullrequest",
            name="aci_comment_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
