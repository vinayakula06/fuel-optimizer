from django.db import models

class RouteCache(models.Model):
    cache_key = models.CharField(max_length=64, unique=True, db_index=True)
    start_location = models.CharField(max_length=200, db_index=True)
    finish_location = models.CharField(max_length=200, db_index=True)
    total_miles = models.FloatField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    stop_count = models.IntegerField()
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['-created_at'])]

class RouteRequestLog(models.Model):
    start_location = models.CharField(max_length=200)
    finish_location = models.CharField(max_length=200)
    external_api_call_count = models.IntegerField(default=0)
    was_route_cached = models.BooleanField(default=False)
    response_time_ms = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['-created_at'])]
