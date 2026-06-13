import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.stations.models import RouteCache

cache = RouteCache.objects.first()
if cache is None:
    print("No route cache record found. Please query the API or run optimization first.")
else:
    data = cache.response_json
    stops = data.get('stops', [])
    prev = 0
    for s in stops:
        gap = s['miles_from_start'] - prev
        print(
            "Stop %d | %-22s | %6.1f mi | $%s/gal | %5.2f gal | gap: %5.1f mi"
            % (s['sequence'], s['station_name'][:22], s['miles_from_start'],
               s['retail_price'], s['gallons_purchased'], gap)
        )
        prev = s['miles_from_start']
    print("End | 2018.1 mi | gap from last stop: %.1f mi" % (2018.14 - prev))
