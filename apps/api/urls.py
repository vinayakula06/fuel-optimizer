from django.urls import path
from apps.api.views import (
    RouteOptimizationView,
    RoutePreviewView,
    HealthCheckView,
    StationListView
)
from apps.api.map_view import RouteMapView

app_name = 'api'

urlpatterns = [
    path('route/', RouteOptimizationView.as_view(), name='route-optimize'),
    path('route/preview/', RoutePreviewView.as_view(), name='route-preview'),
    path('map/', RouteMapView.as_view(), name='route-map'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('stations/', StationListView.as_view(), name='station-list'),
]
