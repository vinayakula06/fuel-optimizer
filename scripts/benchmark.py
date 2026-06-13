import os
import sys
import time
import random
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

try:
    import django
    django.setup()
    from apps.optimizer.engine import find_optimal_fuel_stops
    from apps.optimizer.spatial import project_stations_to_route
except ImportError:
    print("Warning: Django environment not fully initialized, running mock benchmarks.")
    find_optimal_fuel_stops = None
    project_stations_to_route = None


def benchmark_engine():
    print("=" * 60)
    print("BENCHMARKING FUEL STOPS OPTIMIZATION ENGINE")
    print("=" * 60)
    
    # Generate mock stations for a 1200 mile road trip
    # We will generate 150 stations along the route (high density)
    total_dist = 1200.0
    random.seed(42)
    np.random.seed(42)
    
    stations = []
    for i in range(150):
        stations.append({
            'id': i,
            'name': f"Station {i}",
            'address': f"{i} Highway St",
            'city': "Anytown",
            'state': "US",
            'retail_price': round(random.uniform(2.80, 4.20), 3),
            'latitude': random.uniform(34.0, 42.0),
            'longitude': random.uniform(-118.0, -87.0),
            'miles_from_start': round(random.uniform(10.0, 1190.0), 2)
        })
    stations.sort(key=lambda s: s['miles_from_start'])
    
    runs = 1000
    times = []
    
    if find_optimal_fuel_stops:
        # Warmup
        for _ in range(50):
            find_optimal_fuel_stops(stations, total_dist, tank_range=500.0, mpg=10.0)
            
        for _ in range(runs):
            t_start = time.perf_counter()
            find_optimal_fuel_stops(stations, total_dist, tank_range=500.0, mpg=10.0)
            t_end = time.perf_counter()
            times.append((t_end - t_start) * 1000.0) # ms
            
        times = np.array(times)
        print(f"Algorithm Runs: {runs}")
        print(f"Number of input stations: {len(stations)}")
        print(f"Mean Latency: {np.mean(times):.4f} ms")
        print(f"Median (P50) Latency: {np.median(times):.4f} ms")
        print(f"P95 Latency: {np.percentile(times, 95):.4f} ms")
        print(f"P99 Latency: {np.percentile(times, 99):.4f} ms")
    else:
        print("Django not configured - skipping algorithm benchmark.")
        
    print("\n" + "=" * 60)
    print("BENCHMARKING SPATIAL PROJECTION PIPELINE (cKDTree)")
    print("=" * 60)
    
    # Generate 500 coordinates for route geometry
    route_coords = [[-87.6298 + i * 0.05, 41.8781 - i * 0.02] for i in range(500)]
    # Generate 200 random stations to project
    spatial_stations = []
    for i in range(200):
        spatial_stations.append({
            'id': i,
            'name': f"Station {i}",
            'retail_price': 3.50,
            'latitude': 41.8781 - random.uniform(-1.0, 1.0),
            'longitude': -87.6298 + random.uniform(-1.0, 1.0),
        })
        
    runs_spatial = 500
    times_spatial = []
    
    if project_stations_to_route:
        # Warmup
        for _ in range(20):
            project_stations_to_route(spatial_stations, route_coords)
            
        for _ in range(runs_spatial):
            t_start = time.perf_counter()
            project_stations_to_route(spatial_stations, route_coords)
            t_end = time.perf_counter()
            times_spatial.append((t_end - t_start) * 1000.0)
            
        times_spatial = np.array(times_spatial)
        print(f"cKDTree Runs: {runs_spatial}")
        print(f"Number of route geometry coordinates: {len(route_coords)}")
        print(f"Number of candidate stations: {len(spatial_stations)}")
        print(f"Mean Latency: {np.mean(times_spatial):.4f} ms")
        print(f"Median (P50) Latency: {np.median(times_spatial):.4f} ms")
        print(f"P95 Latency: {np.percentile(times_spatial, 95):.4f} ms")
        print(f"P99 Latency: {np.percentile(times_spatial, 99):.4f} ms")
    else:
        print("Django not configured - skipping spatial benchmark.")


if __name__ == "__main__":
    benchmark_engine()
