from django.db import migrations, models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='RouteCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cache_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('start_location', models.CharField(db_index=True, max_length=200)),
                ('finish_location', models.CharField(db_index=True, max_length=200)),
                ('total_miles', models.FloatField()),
                ('total_cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stop_count', models.IntegerField()),
                ('response_json', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['-created_at'], name='routes_rout_created_8a928f_idx')],
            },
        ),
        migrations.CreateModel(
            name='RouteRequestLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_location', models.CharField(max_length=200)),
                ('finish_location', models.CharField(max_length=200)),
                ('external_api_call_count', models.IntegerField(default=0)),
                ('was_route_cached', models.BooleanField(default=False)),
                ('response_time_ms', models.FloatField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['-created_at'], name='routes_requ_created_61cd7c_idx')],
            },
        ),
    ]
