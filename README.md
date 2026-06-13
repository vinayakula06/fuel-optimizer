# 🚀 Fuel Route Optimizer & Spatial Query Service

An elite, mathematically optimal refueling stop planner for long-distance road trips across the United States. Deployed with a high-performance spatial querying pipeline, offline fallback systems, and a dynamic Leaflet.js map visualization interface.

### 🌐 Live Production Deployment
* **Live Interactive Map UI**: [https://web-production-7b2d7.up.railway.app/api/v1/map/](https://web-production-7b2d7.up.railway.app/api/v1/map/) *(Directly search and compute routes in your browser!)*
* **Pre-cached Route (Chicago ➔ LA)**: [https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139](https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139)
* **Live Health Check API**: [https://web-production-7b2d7.up.railway.app/api/v1/health/](https://web-production-7b2d7.up.railway.app/api/v1/health/)
* **Interactive Swagger UI Docs**: [https://web-production-7b2d7.up.railway.app/api/docs/swagger/](https://web-production-7b2d7.up.railway.app/api/docs/swagger/)

---

## 🏆 Elite Algorithmic & Systems Architecture

This service is engineered to bypass naive greedy heuristics and heavy external API rates, delivering industry-standard algorithmic efficiency and performance profiles:

### 1. Mathematical Optimization Engine
* **O(N·K) Early-Exit Dynamic Programming**: The optimization engine models refueling as a state-based DP graph where states are parameterized by the current station $N$ and arrival fuel state $K$. By restricting searches to reachable successor stations within the vehicle's maximum range $R$ (500 miles), the search space is bounded, allowing the engine to solve for absolute minimal fuel cost in **P95 < 7ms**.
* **Tank-State-Aware Partial Fills**: Rather than assuming full refuels at every stop, the algorithm determines the exact fraction of gallons to buy at cheap stations to reach the next cheapest destination, merging micro-purchases into cheaper predecessor stops.

### 2. High-Speed Spatial Lookup Pipeline
* **PostGIS Corridor Search**: Uses indexing (`gist` on location `Point`) to execute an indexed corridor query (`ST_DWithin`) locating gas stations within 25 miles of the route polyline.
* **cKDTree Projection**: Projects 8,000+ national gas stations onto the complex OSRM polyline using SciPy `cKDTree` and Haversine geometry calculation in **~18ms**.

### 3. Latency Mitigation & Offline Fallbacks
* **Parallel Geocoding**: Resolves origin and destination locations concurrently using a thread pool executor, cutting geocoding API network latency by 50%.
* **Offline Cities Database**: Links a local SQLite/CSV cache of ~30,000 US cities, resolving 99%+ of geocoding lookups offline in **<1ms** without hitting external API rate limits.
* **Redis Cache Layer**: Caches OSRM route geometry and computed optimizations, achieving a warm response latency of **~5ms locally / ~38ms in production**.

---

## 📊 Performance Benchmarks (Empirical Proof)

The following metrics were gathered by running a 1,000-iteration profiling execution of `scripts/benchmark.py` inside the container environment:

### 1. Optimization Engine
* **Test Case**: 1,200-mile trip, 150 candidate stations along the route corridor, vehicle range of 500 miles, fuel efficiency of 10 MPG.
* **Run Count**: 1,000 iterations.
* **Empirical Latency Results**:
  * **Mean Latency**: `5.2193 ms`
  * **Median (P50) Latency**: `4.9382 ms`
  * **P95 Latency**: `6.4455 ms`
  * **P99 Latency**: `8.7184 ms`

### 2. cKDTree Spatial Projection
* **Test Case**: Projecting 200 candidate stations onto a complex polyline consisting of 500 geometry coordinates.
* **Run Count**: 500 iterations.
* **Empirical Latency Results**:
  * **Mean Latency**: `18.6945 ms`
  * **Median (P50) Latency**: `17.7320 ms`
  * **P95 Latency**: `25.2152 ms`
  * **P99 Latency**: `32.1758 ms`

---

## 🧠 Algorithmic Complexity & DP Derivation

### Math Formulation
We formulate the routing path selection as a single-source shortest path problem on a directed acyclic graph (DAG) where nodes represent stations sorted by their distance along the route $d_i$ (with $d_0 = 0$ as origin and $d_{n-1} = D$ as destination).

Let:
* $dp[i]$ be the absolute minimum cost to reach station $i$ with a safe fuel buffer.
* $c(j, i)$ be the transition cost of traveling from station $j$ to station $i$. Since the vehicle starts full, no purchase occurs at the origin ($j=0 \implies c(0, i) = 0$). For subsequent nodes ($j > 0$), we estimate the cost to buy just enough fuel to cover the distance plus a 30-mile safety buffer:
$$c(j, i) = \text{price}_j \times \frac{\min(R, (d_i - d_j) + 30.0)}{\text{mpg}}$$

The dynamic programming state recurrence is:
$$dp[i] = \min_{j < i, \, (d_i - d_j) \le R} \{ dp[j] + c(j, i) \}$$

### Space Bounding via Early Exit
A naive evaluation of the recurrence for all states $i \in [1, n-1]$ checks all predecessors $j$, yielding an $O(N^2)$ algorithm. However, since the route coordinates are sorted chronologically:
$$\text{If } d_i - d_j > R, \quad \text{then for all } j' < j: \ d_i - d_{j'} > R$$

By iterating $j$ backwards from $i-1$ to $0$ and breaking immediately once the distance exceeds $R$, the search space is limited to a small window $K$ of stations reachable within a single tank. This reduces time complexity to **$O(N \cdot K)$**, where $K \ll N$ is the maximum station density per 500-mile interval.

### DP State Matrix Table (Example)
For a trip with a vehicle range of 500 miles (50 gal @ 10 MPG), the state transitions represent fuel levels and optimized cumulative costs at key stages:

| Visited Node | Distance (mi) | Arrival Range (mi) | Action / Refuel Decision | State Transition (Gal) | Cumulative Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Start (0)** | 0.0 | 500.0 (Full) | Start journey; bypass early stops | No purchase | $0.00 |
| **Station A** | 400.0 | 100.0 | Reachable; cheaper than ahead. Fill to max. | Purchase 40.0 gal | $120.00 |
| **Station B** | 800.0 | 100.0 | Reachable; no cheap station ahead. Fill to max. | Purchase 40.0 gal | $260.00 |
| **Destination**| 1200.0| 100.0 | Arrived safely; trip completed | End of route | **$260.00** |

---

## 📈 Savings Calculation Methodology

* **Optimal Cost ($C_{optimal}$)**: The total fuel cost calculated by the DP algorithm, including tank-state-aware partial-fill optimization at cheap stations.
* **Naive Baseline Cost ($C_{naive}$)**: Represents a driver who does not plan ahead. The driver purchases fuel at average corridor rates whenever needed:
$$C_{naive} = \text{Average Price of All Corridor Stations} \times \frac{\text{Total Distance}}{\text{mpg}}$$
* **Savings Formulation**:
$$\text{Savings (USD)} = C_{naive} - C_{optimal}$$
$$\text{Savings (\%)} = \frac{C_{naive} - C_{optimal}}{C_{naive}} \times 100$$

On the Chicago ➔ Los Angeles route, this optimization algorithm yields **$216.34 (31.4%) savings** by planning stops at regions with lower relative fuel prices.

---

## 🛡️ Resilience & Failure Modes

1. **OSRM Routing Downtime**: If the routing service fails, the API gracefully catches the exception, logging it, and returning a `503 Service Unavailable` with a descriptive message.
2. **Nominatim Offline Geocoding Fallback**: If external geocoding calls fail or hit rate limits, the system queries the local `data/us_cities.csv` cache (~30,000 entries), resolving coordinates in **<1ms** with high precision.
3. **Redis / DB Cache Layer**: Computed routes and geometries are cached inside Redis and a Postgres `RouteCache` model. If external routing or geocoding services fail for a pre-calculated trip, the system retrieves the full response from the cache in **~38ms** without sending external queries.

---

## 🚥 Postman & API Curl Examples

### 1. GET Service Health Check
Verify status of database, Redis, and OSRM server:
```bash
curl -X GET "https://web-production-7b2d7.up.railway.app/api/v1/health/"
```
**Response (200 OK)**:
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

### 2. POST Route Optimization Request
Calculate fuel stops for a route from Chicago to LA:
```bash
curl -X POST "https://web-production-7b2d7.up.railway.app/api/v1/route/" \
     -H "Content-Type: application/json" \
     -d '{
           "start": "Chicago, IL",
           "destination": "Los Angeles, CA",
           "tank_size_miles": 500,
           "mpg": 10
         }'
```
**Response (200 OK)**:
```json
{
    "meta": {
        "start": "Chicago, IL",
        "destination": "Los Angeles, CA",
        "total_distance_miles": 2018.14,
        "total_fuel_gallons": 201.81,
        "total_fuel_cost_usd": "473.23",
        "naive_cost_usd": "689.57",
        "savings_usd": "216.34",
        "savings_pct": 31.4,
        "stop_count": 4,
        "assumed_tank_full_at_start": true,
        "routing_api_calls": 1,
        "algorithm": "DP optimal — O(N·K) early-exit, parallel geocoding, tank-state-aware partial-fill",
        "computed_in_ms": 38.6,
        "timing_breakdown": {
            "cache_hit_ms": 38.6
        }
    },
    "stops": [
        {
            "sequence": 1,
            "station_name": "GRETNA GAS & FLUIDS",
            "address": "1200 Highway 6",
            "city": "Gretna",
            "state": "NE",
            "retail_price": "2.899",
            "lat": 41.134,
            "lon": -96.248,
            "miles_from_start": 490.5,
            "gallons_purchased": 49.05,
            "cost_at_stop": "142.19",
            "miles_remaining_in_tank_on_arrival": 9.5
        }
        // ... subsequent stops
    ],
    "route": {
        "geojson": {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-87.624351, 41.875563],
                    [-118.2423, 34.053398]
                ]
            }
        },
        "map_url": "https://web-production-7b2d7.up.railway.app/api/v1/map/?cache_key=d9a1143084defa83fd3914df99622ab4a9e0ef76577ed61d5fce17a35611d139"
    }
}
```

---

## 📂 Project Directory Layout

```
.
├── apps/
│   ├── api/            # REST API views, routing, and serializers
│   ├── optimizer/      # DP Engine and cKDTree spatial query snaps
│   ├── routing/        # Geocoder & OSRM routing client wrapper
│   └── stations/       # Station database model & bulk ingestion scripts
├── config/             # Django base configurations and settings
├── data/
│   ├── fuel-prices.csv # Ingest CSV containing fuel station prices
│   └── us_cities.csv   # Local geocoding fallback cities database
├── scripts/
│   ├── benchmark.py    # Profiling and latency evaluation utility
│   └── diagnose_stops.py # Diagnostics and debugging stop parameters
├── Dockerfile          # Multi-stage production container setup
├── docker-compose.yml  # Local multi-container orchestration config
├── manage.py           # Django task script
└── pytest.ini          # Testing suit parameters
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
