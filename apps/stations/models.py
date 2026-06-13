from django.contrib.gis.db import models
from django.db.models import Index


class FuelStation(models.Model):
    opis_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField(null=True)
    retail_price = models.DecimalField(max_digits=8, decimal_places=5)
    location = models.PointField(srid=4326, null=True, db_index=True)
    geocoded_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('opis_id', 'retail_price')]
        indexes = [
            Index(fields=['state', 'retail_price']),
        ]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) @ ${self.retail_price}"


class RouteCache(models.Model):
    """Store computed routes for analytics / debugging / caching."""
    cache_key = models.CharField(max_length=64, unique=True, db_index=True)
    start_label = models.CharField(max_length=200)
    end_label = models.CharField(max_length=200)
    total_miles = models.FloatField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    stop_count = models.IntegerField()
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [Index(fields=['-created_at'])]
