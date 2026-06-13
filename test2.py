import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.stations.models import FuelStation
from django.db.models import Count, Min
dupes = (FuelStation.objects
    .values('opis_id')
    .annotate(count=Count('id'), min_price=Min('retail_price'))
    .filter(count__gt=1)
    .count())
print(f'OPIS IDs with multiple rows: {dupes}')
print(f'Total stations: {FuelStation.objects.count()}')
