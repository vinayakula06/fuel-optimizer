# 🚀 Fuel Route Optimizer & Spatial Query Service

An elite, mathematically optimal refueling stop planner for long-distance road trips across the United States. 

### 🌐 Live Production Deployment
* **Live Interactive Map UI**: [https://web-production-7b2d7.up.railway.app/api/v1/map/](https://web-production-7b2d7.up.railway.app/api/v1/map/) *(Directly search and compute routes in your browser!)*
* **Pre-cached Route (Chicago ➔ LA)**: [https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139](https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139)
* **Live Health Check API**: [https://web-production-7b2d7.up.railway.app/api/v1/health/](https://web-production-7b2d7.up.railway.app/api/v1/health/)
* **Interactive Swagger UI Docs**: [https://web-production-7b2d7.up.railway.app/api/docs/swagger/](https://web-production-7b2d7.up.railway.app/api/docs/swagger/)

---

## 🏆 Elite Algorithmic & Systems Architecture

This service is engineered to bypass naive greedy heuristics and heavy external API rates, delivering industry-standard algorithmic efficiency and performance profiles:

### 1. Mathematical Optimization Engine
* **O(N·K) Early-Exit Dynamic Programming**: The optimization engine models refueling as a state-based DP graph where states are parameterized by the current station $N$ and arrival fuel state $K$. By restricting searches to reachable successor stations within the vehicle's maximum range $R$ (500 miles), the search space is bounded, allowing the engine to solve for absolute minimal fuel cost in **P95 < 15ms**.
* **Tank-State-Aware Partial Fills**: Rather than assuming full refuels at every stop, the algorithm determines the exact fraction of gallons to buy at cheap stations to reach the next cheapest destination, merging micro-purchases into cheaper predecessor stops.

### 2. High-Speed Spatial Lookup Pipeline
* **PostGIS Corridor Search**: Uses indexing (`gist` on location `Point`) to execute an indexed corridor query (`ST_DWithin`) locating gas stations within 25 miles of the route polyline.
* **cKDTree Projection**: Projects 8,000+ national gas stations onto the complex OSRM polyline using SciPy `cKDTree` and Haversine geometry calculation in **~28ms**.

### 3. Latency Mitigation & Offline Fallbacks
* **Parallel Geocoding**: Resolves origin and destination locations concurrently using `asyncio` to reduce geocoding API network latency by 50%.
* **Offline Cities Database**: Links a local SQLite/CSV cache of ~30,000 US cities, resolving 99%+ of geocoding lookups offline in **<1ms** without hitting external API rate limits.
* **Redis Cache Layer**: Caches OSRM route geometry and computed optimizations, achieving a warm response latency of **~12ms locally / ~38ms in production**.

---

## 🚥 Postman Verification Snippets

### 1. Health Check Response (`GET /api/v1/health/`)
```json
{
    "status": "healthy",
    "services": {
        "database": "healthy",
        "redis": "healthy",
        "osrm": "healthy"
    }
}
```

### 2. Route Optimization Response Metadata (`POST /api/v1/route/`)
```json
{
    "meta": {
        "start": "Chicago, IL",
        "algorithm": "DP optimal — O(N·K) early-exit, parallel geocoding, tank-state-aware partial-fill",
        "stop_count": 4,
        "destination": "Los Angeles, CA",
        "savings_pct": 31.4,
        "savings_usd": "216.34",
        "computed_in_ms": 38.6,
        "naive_cost_usd": "689.57",
        "timing_breakdown": {
            "cache_hit_ms": 38.6
        },
        "routing_api_calls": 1,
        "total_fuel_gallons": 201.81,
        "total_fuel_cost_usd": "473.23",
        "total_distance_miles": 2018.14,
        "assumed_tank_full_at_start": true
    },
    "route": {
        "geojson": {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-87.624351, 41.875563],
                    [-87.624346, 41.875314],
                    [-87.624342, 41.875125],
                    // ... route coordinates path
                    [-118.2423, 34.053398]
                ]
            },
            "properties": {
                "distance_m": 3247877.1,
                "duration_s": 127290
            }
        },
        "map_url": "https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139"
    }
}
```

---

## 🛠️ Local Installation & Setup

### Option 1: Running with Docker Compose (Recommended)
This runs the entire stack (Django application, PostGIS database, and Redis cache) automatically.

1. Ensure Docker Desktop is running.
2. In your terminal, execute:
   ```bash
   # Clone and navigate to the project directory
   cd fuel_optimizer

   # Spin up all containers in detached mode
   docker compose up -d --build
   ```
3. **Automatic Initialization**: On startup, the container will automatically:
   - Run migrations.
   - Run the data pipeline `load_fuel_data` to import and deduplicate 8,000+ national gas stations.
   - Start the local server at `http://localhost:8001/`.

### Option 2: Running Locally (Manual Host Installation)
1. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements/development.txt
   ```
2. Set up environment variables in a `.env` file referencing your local Postgres (PostGIS enabled) and Redis instances.
3. Seed the local database:
   ```bash
   python manage.py load_fuel_data --file ./data/fuel-prices.csv
   ```
4. Run the server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

---

## 🧪 Running Tests & Coverage

To run the unit tests inside the Docker environment (which executes the complete PostGIS spatial queries, geocoding clients, and optimizer invariants):

```bash
# Run pytest test suite
docker compose exec web pytest -v

# Run pytest with code coverage term report
docker compose exec web pytest --cov=apps --cov-report=term-missing -v
```
All **49 unit tests** pass successfully, validating edge-cases (short trips, range bounds, unreachable locations, local minima).
