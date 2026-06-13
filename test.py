import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.stations.models import RouteCache
c = RouteCache.objects.first()
if c:
    for s in c.response_json['stops']:
        print(f"{s['sequence']}. {s['station_name']} | {s['city']}, {s['state']} | ${s['retail_price']}/gal | {s['gallons_purchased']} gal | ${s['cost_at_stop']}")
    print('Total:', c.response_json['meta']['total_fuel_cost_usd'])
