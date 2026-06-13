import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.stations.models import FuelStation
for name in ['KUM & GO', 'CIRCLE K', 'GOLDEN GATE', 'ERNIES']:
    qs = FuelStation.objects.filter(name__icontains=name).order_by('retail_price')
    if qs.exists():
        s = qs.first()
        print(f'{s.name} | {s.city}, {s.state} | ${s.retail_price}')
    else:
        print(f'NOT FOUND: {name}')
