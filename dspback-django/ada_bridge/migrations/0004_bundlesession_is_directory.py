# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ada_bridge', '0003_adajsontable_adarecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='bundlesession',
            name='is_directory',
            field=models.BooleanField(
                default=False,
                help_text='True when bundle_path points to a directory instead of a ZIP file',
            ),
        ),
    ]
