from unittest.mock import patch
from django.urls import reverse
from django.contrib.gis.geos import Point
from rest_framework import status
from rest_framework.test import APITestCase
from apps.stations.models import FuelStation
from routes.models import RouteCache

class APITests(APITestCase):

    def setUp(self):
        # Create some test fuel stations
        # Station A is 100 miles along a hypothetical route from Chicago to LA
        self.station1 = FuelStation.objects.create(
            opis_id=101,
            name="Loves #1",
            address="123 Route 66",
            city="Joliet",
            state="IL",
            rack_id=12,
            retail_price=3.10000,
            location=Point(-88.08, 41.52, srid=4326) # Close to route
        )
        self.station2 = FuelStation.objects.create(
            opis_id=102,
            name="Loves #2",
            address="456 Route 66",
            city="Bloomington",
            state="IL",
            rack_id=15,
            retail_price=3.50000,
            location=Point(-88.99, 40.48, srid=4326) # Close to route
        )

    def test_health_check(self):
        url = reverse('api:health-check')
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        assert "status" in response.data
        assert "services" in response.data

    def test_station_list(self):
        url = reverse('api:station-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) >= 2

    def test_route_optimization_invalid_input(self):
        url = reverse('api:route-optimize')
        # Missing start and destination
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "INVALID_INPUT"

        # Start and destination same
        response = self.client.post(url, {
            "start": "Chicago, IL",
            "destination": "Chicago, IL"
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('apps.routing.geocoder.NominatimGeocoder.geocode')
    @patch('apps.routing.client.OSRMClient.get_route')
    def test_route_optimization_success(self, mock_get_route, mock_geocode):
        # Setup mocks
        mock_geocode.side_effect = lambda city, state: {
            "Chicago, IL": (41.878, -87.629),
            "Bloomington, IL": (40.48, -88.99),
            "Los Angeles, CA": (34.052, -118.243),
        }.get(city, (41.0, -88.0))

        mock_get_route.return_value = {
            "routes": [{
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-87.629, 41.878],
                        [-88.08, 41.52],
                        [-88.99, 40.48],
                        [-118.243, 34.052]
                    ]
                },
                "distance": 965606,  # ~600 miles
                "duration": 100000
            }]
        }

        url = reverse('api:route-optimize')
        payload = {
            "start": "Chicago, IL",
            "destination": "Los Angeles, CA",
            "tank_size_miles": 500,
            "mpg": 10,
            "max_detour_miles": 25
        }
        
        response = self.client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Verify schema elements
        data = response.data
        assert "meta" in data
        assert "stops" in data
        assert "route" in data
        
        assert data["meta"]["start"] == "Chicago, IL"
        assert data["meta"]["destination"] == "Los Angeles, CA"
        assert data["meta"]["stop_count"] > 0
        assert "map_url" in data["route"]

    @patch('apps.routing.geocoder.NominatimGeocoder.geocode')
    def test_route_optimization_location_not_found(self, mock_geocode):
        mock_geocode.return_value = None

        url = reverse('api:route-optimize')
        payload = {
            "start": "Xyztopolis, ZZ",
            "destination": "Los Angeles, CA"
        }
        response = self.client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "LOCATION_NOT_FOUND"
