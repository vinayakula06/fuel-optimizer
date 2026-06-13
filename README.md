# Fuel Optimizer & Gas Station Routing Service

This is a backend Django REST API service that calculates the mathematically optimal sequence of refueling stops for a long-distance road trip across the United States.

It integrates with:
- **Nominatim** (Geocoding API) to convert free-text addresses or city names into latitude/longitude coordinates.
- **OSRM** (Open Source Routing Machine) to get the routing polyline and leg distances.
- **PostGIS** (PostgreSQL Spatial Database) to query gas stations within a 25-mile corridor along the route using indexed spatial lookup (`location__dwithin`).
- **Redis** to cache geocoding queries, OSRM routes, and final optimization results.
- **Leaflet.js** to generate interactive map views of the route and selected stops.

---

## Technical Stack & Architecture

- **Web Framework**: Django 5.x & Django REST Framework
- **Database**: PostgreSQL 16 + PostGIS 3.4
- **Cache**: Redis 7
- **Dependencies**: `scipy` (for local coordinate parsing/geometry helpers), `httpx` (async HTTP clients)
- **Algorithm**: $O(N^2)$ Dynamic Programming approach, ensuring the absolute minimum cost under a 500-mile vehicle range constraint.

---

## Performance Metrics

| Scenario              | P95 response time |
|-----------------------|------------------|
| Cold request          | ~300 ms          |
| Warm (Redis hit)      | ~12 ms           |
| projection_ms         | ~28 ms           |
| algorithm_ms          | ~12 ms           |

---

## Scaffolding & Setup

### Option 1: Running with Docker Compose (Recommended)

To run the entire ecosystem (Django, PostGIS, Redis) without manual setup, start Docker Desktop on your machine and run:

```bash
# Clone/navigate to the project directory
cd fuel_optimizer

# Spin up containers
docker compose up -d --build
```

On startup, Docker Compose will:
1. Initialize the PostgreSQL database and enable the `postgis` spatial extension.
2. Run database migrations.
3. Automatically execute the `load_fuel_data` command to ingest, deduplicate, and geocode the ~8,000 gas stations from the provided CSV file (resolving 99%+ of cities instantly via our local pre-compiled geocoding cache, falling back to Nominatim only when needed).
4. Start the Django development server at `http://localhost:8001` (forwarded from container port `8000`).

### Option 2: Running Locally (Manual Host Installation)

If you wish to run the app directly on your host machine, you will need local installations of PostgreSQL with PostGIS, and Redis.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements/development.txt

# 3. Configure environment variables in a .env file
# (Create a .env file based on the environment variables defined in docker-compose.yml or base.py)

# 4. Ingest and geocode the CSV dataset
python manage.py load_fuel_data --file ./data/fuel-prices.csv

# 5. Launch development server
python manage.py runserver 0.0.0.0:8000
```

---

## Running the Test Suite

Our testing suite uses `pytest` and covers edge cases like:
- Short trips under 500 miles (0 stops, 0 cost).
- Exact tank range boundary conditions.
- Gaps in refueling stations (raising `ROUTE_IMPOSSIBLE` / 422).
- Sub-optimal local minima (guaranteeing DP outperforms naive greedy).
- External API mocking and geocoding cache lookups.
- Custom geocoder error mapping and error responses.

To run the test suite on your host (bypassing spatial DB dependencies using the `-p no:django` plugin flag):

```bash
$env:PYTHONPATH="."
.venv\Scripts\pytest -p no:django apps/optimizer/tests/test_engine.py
```

Inside the Docker container (runs the full test suite including PostGIS spatial tests and coverage reporting):

```bash
# Run all tests
docker compose exec web pytest -v

# Run tests with coverage reporting (Coverage is configured via .coveragerc to exclude boilerplate files, maintaining >= 80% coverage)
docker compose exec web pytest --cov=apps --cov-report=term-missing -v
```

---

## API Documentation & Endpoint Reference

Once the server is running, the interactive API documentation is accessible at:
- **Swagger UI**: `http://localhost:8001/api/docs/swagger/`
- **Redoc**: `http://localhost:8001/api/docs/redoc/`

### 1. Compute Optimized Route
**Endpoint**: `POST /api/v1/route/`  
**Body**:
```json
{
  "start": "Chicago, IL",
  "destination": "Los Angeles, CA",
  "tank_size_miles": 500,
  "mpg": 10,
  "max_detour_miles": 25
}
```

**cURL Command**:
```bash
curl -X POST http://localhost:8001/api/v1/route/ \
     -H "Content-Type: application/json" \
     -d '{"start": "Chicago, IL", "destination": "Los Angeles, CA"}'
```

**Response Example (Success)**:
```json
{
  "meta": {
    "start": "Chicago, IL",
    "destination": "Los Angeles, CA",
    "total_distance_miles": 2018.14,
    "total_fuel_gallons": 201.81,
    "total_fuel_cost_usd": "473.23",
    "stop_count": 4,
    "assumed_tank_full_at_start": true,
    "routing_api_calls": 1,
    "algorithm": "DP optimal — O(N²), tank-state-aware partial-fill",
    "computed_in_ms": 32.1
  },
  "stops": [
    {
      "sequence": 1,
      "station_name": "KUM & GO #0370",
      "address": "12014 S 143RD ST",
      "city": "GRETNA",
      "state": "NE",
      "retail_price": "2.921",
      "lat": 41.140228,
      "lon": -96.136894,
      "miles_from_start": 484.1,
      "gallons_purchased": 48.41,
      "cost_at_stop": "141.39",
      "miles_remaining_in_tank_on_arrival": 15.9
    }
    // ... remaining stops
  ],
  "route": {
    "geojson": { ... },
    "map_url": "http://localhost:8001/api/v1/map/?route=..."
  }
}
```

### 2. Validation / Geocoding Error Shapes

#### Same City (Start and End match)
Returns a `400 Bad Request` with a flat envelope targeting the destination field:
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Origin and destination must differ.",
    "field": "destination"
  }
}
```

#### Unknown Location (Geocoding failure)
Returns a `404 Not Found` with a flat envelope indicating which field failed:
```json
{
  "error": {
    "code": "LOCATION_NOT_FOUND",
    "message": "Could not geocode start location: 'Xyztopolis, ZZ'. Ensure the city and state are valid US locations.",
    "field": "start"
  }
}
```

### 3. Interactive Web Interface & Leaflet Map
**Endpoint**: `GET /api/v1/map/`

Our service includes a **complete, self-contained interactive web application** (Single Page Application) built directly into the Django project.

- **Direct Web Interface URL**: [http://localhost:8001/api/v1/map/](http://localhost:8001/api/v1/map/)
- **How it works**:
  1. Open the page directly in any web browser.
  2. Input any start and destination locations within the USA (e.g., *Chicago, IL* and *Los Angeles, CA*).
  3. Customize route parameters (Vehicle Range, MPG, Max Detour).
  4. Click **Calculate Optimal Route** to dynamically fetch optimization data via AJAX and render the Leaflet map, route polyline, and markers without reloading.
  5. Click on any route stop marker to view pricing and purchase details, or view the detailed chronological schedule in the glassmorphic sidebar.
- **Direct Link Sharing**: The `map_url` returned in the `POST /api/v1/route/` response will pre-load that exact computed route and map when opened in the browser.

### 4. Health Check
**Endpoint**: `GET /api/v1/health/`  
**cURL Command**:
```bash
curl -X GET http://localhost:8001/api/v1/health/
```

### 5. Paginated Stations List (Debug)
**Endpoint**: `GET /api/v1/stations/`  
**cURL Command**:
```bash
curl -X GET http://localhost:8001/api/v1/stations/
```
