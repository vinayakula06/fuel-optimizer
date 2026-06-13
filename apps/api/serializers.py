from rest_framework import serializers

class RouteOptimizationRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        required=True, 
        help_text="Starting location address or city name (e.g. 'Chicago, IL')"
    )
    destination = serializers.CharField(
        required=True, 
        help_text="Destination location address or city name (e.g. 'Los Angeles, CA')"
    )
    tank_size_miles = serializers.FloatField(
        default=500.0, 
        help_text="Range of vehicle on a full tank in miles"
    )
    mpg = serializers.FloatField(
        default=10.0, 
        help_text="Fuel efficiency of the vehicle in miles per gallon"
    )
    max_detour_miles = serializers.FloatField(
        default=25.0, 
        help_text="Max distance off-route in miles to look for gas stations"
    )

    def validate(self, data):
        if data.get('start', '').strip().lower() == data.get('destination', '').strip().lower():
            raise serializers.ValidationError({
                "code": "INVALID_INPUT",
                "message": "Origin and destination must differ.",
                "field": "destination",
            })
        return data


class MetaSerializer(serializers.Serializer):
    start = serializers.CharField()
    destination = serializers.CharField()
    total_distance_miles = serializers.FloatField()
    total_fuel_gallons = serializers.FloatField()
    total_fuel_cost_usd = serializers.CharField()
    stop_count = serializers.IntegerField()
    assumed_tank_full_at_start = serializers.BooleanField()
    routing_api_calls = serializers.IntegerField()
    computed_in_ms = serializers.IntegerField()


class StopSerializer(serializers.Serializer):
    sequence = serializers.IntegerField()
    station_name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    retail_price = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    miles_from_start = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost_at_stop = serializers.CharField()
    miles_remaining_in_tank_on_arrival = serializers.FloatField()


class GeoJSONSerializer(serializers.Serializer):
    type = serializers.CharField()
    geometry = serializers.JSONField()
    properties = serializers.JSONField()


class RouteDetailsSerializer(serializers.Serializer):
    geojson = GeoJSONSerializer()
    map_url = serializers.CharField()


class RouteOptimizationResponseSerializer(serializers.Serializer):
    meta = MetaSerializer()
    stops = StopSerializer(many=True)
    route = RouteDetailsSerializer()
