import json
from django.http import HttpResponse
from django.views import View


GOOGLE_MAPS_ICON_BASE64 = "data:image/png;base64,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"

class RouteMapView(View):
    """
    GET /api/v1/map/
    Query params (optional):
      - route: JSON-encoded GeoJSON LineString coordinates [[lon,lat], ...]
      - stops: JSON-encoded list of stop dicts
      - start: start label string
      - end: end label string
    Returns a fully interactive self-contained Leaflet HTML page.
    """

    def get(self, request):
        cache_key = request.GET.get("cache_key", "")
        coordinates = []
        stops = []
        start_label = ""
        end_label = ""
        meta = {}

        if cache_key:
            from routes.models import RouteCache
            route_cache = RouteCache.objects.filter(cache_key=cache_key).first()
            if route_cache:
                data = route_cache.response_json
                try:
                    coordinates = data["route"]["geojson"]["geometry"]["coordinates"]
                    # Thin coordinates for map load performance
                    step = max(1, len(coordinates) // 200)
                    thinned = coordinates[::step]
                    if coordinates and coordinates[-1] not in thinned:
                        thinned.append(coordinates[-1])
                    coordinates = thinned
                    stops = data["stops"]
                    start_label = data["meta"]["start"]
                    end_label = data["meta"]["destination"]
                    meta = data.get("meta", {})
                except (KeyError, TypeError):
                    pass
        
        # If cache_key wasn't found or was empty, fall back to URL query parameters
        if not coordinates:
            try:
                route_param = request.GET.get("route", "")
                coordinates = json.loads(route_param) if route_param else []

                stops_param = request.GET.get("stops", "")
                stops = json.loads(stops_param) if stops_param else []

                start_label = request.GET.get("start", "")
                end_label = request.GET.get("end", "")
                if start_label or end_label:
                    meta = {
                        "start": start_label,
                        "destination": end_label
                    }
            except (json.JSONDecodeError, TypeError):
                coordinates = []
                stops = []
                start_label = ""
                end_label = ""
                meta = {}

        html = self._build_html(coordinates, stops, start_label, end_label, meta)
        return HttpResponse(html, content_type="text/html")

    def _build_html(self, coordinates, stops, start_label, end_label, meta):
        coords_json = json.dumps(coordinates)
        stops_json = json.dumps(stops)

        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Fuel Route Optimizer</title>
  
  <!-- Leaflet Map CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  
  <!-- Premium Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  
  <style>
    :root {
      --primary: #4a90e2;
      --accent: #ff6b35;
      --accent-hover: #e85d24;
      --bg-dark: #0f172a;
      --panel-bg: rgba(30, 41, 59, 0.7);
      --glass-border: rgba(255, 255, 255, 0.08);
      --glass-shine: rgba(255, 255, 255, 0.03);
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --input-bg: rgba(15, 23, 42, 0.6);
      --card-bg: rgba(15, 23, 42, 0.4);
      --error-bg: rgba(239, 68, 68, 0.15);
      --error-border: rgba(239, 68, 68, 0.3);
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    body {
      background-color: var(--bg-dark);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
      display: flex;
    }

    #app-container {
      position: relative;
      width: 100vw;
      height: 100vh;
      display: flex;
    }

    #map {
      flex: 1;
      height: 100%;
      z-index: 1;
      background: #0f172a;
    }

    /* Elegant Glassmorphic Sidebar */
    #sidebar {
      position: absolute;
      top: 20px;
      left: 20px;
      z-index: 1000;
      width: 380px;
      max-height: calc(100vh - 40px);
      background: rgba(10, 16, 30, 0.78);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--glass-border);
      border-radius: 16px;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      overflow-y: auto;
      transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    }
    #sidebar.collapsed {
      width: 52px;
      min-width: 52px;
      padding: 12px;
      overflow: hidden;
      gap: 0;
    }
    #sidebar.collapsed > *:not(#collapse-btn) {
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.15s;
    }
    /* Collapse toggle button */
    #collapse-btn {
      position: absolute;
      top: 12px;
      right: 12px;
      width: 28px;
      height: 28px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1001;
      transition: background 0.2s;
      flex-shrink: 0;
    }
    #collapse-btn:hover { background: rgba(255,255,255,0.16); }
    #collapse-btn svg { transition: transform 0.35s ease; }
    #sidebar.collapsed #collapse-btn {
      right: 50%;
      transform: translateX(50%);
    }
    #sidebar.collapsed #collapse-btn svg { transform: rotate(180deg); }

    /* Custom Scrollbar for Sidebar */
    #sidebar::-webkit-scrollbar {
      width: 6px;
    }
    #sidebar::-webkit-scrollbar-track {
      background: transparent;
    }
    #sidebar::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
    }
    #sidebar::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.25);
    }

    /* Header styling */
    .header {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .header h2 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #fff 40%, var(--text-muted));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header p {
      font-size: 12px;
      color: var(--text-muted);
    }

    .divider {
      height: 1px;
      background: var(--glass-border);
      width: 100%;
    }

    /* Form Input Styles */
    form {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .form-group label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.8px;
    }
    .form-group input {
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--glass-border);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-size: 14px;
      outline: none;
      transition: all 0.2s ease;
    }
    .form-group input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.15);
    }
    .form-row {
      display: flex;
      gap: 12px;
    }
    .half {
      flex: 1;
    }

    /* Premium Button Style */
    button[type="submit"] {
      width: 100%;
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      border: none;
      border-radius: 8px;
      padding: 12px;
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      box-shadow: 0 4px 12px rgba(255, 107, 53, 0.2);
      transition: all 0.2s ease;
    }
    button[type="submit"]:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(255, 107, 53, 0.35);
    }
    button[type="submit"]:active {
      transform: translateY(1px);
    }

    /* Loading Spinner */
    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255,255,255,0.3);
      border-radius: 50%;
      border-top-color: #fff;
      animation: spin 0.8s linear infinite;
      display: none;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* ------------------------------------------------------------------ */
    /* Error Modal Popup                                                   */
    /* ------------------------------------------------------------------ */
    .modal-overlay {
      position: fixed;
      inset: 0;
      z-index: 9999;
      background: rgba(0, 0, 0, 0.65);
      backdrop-filter: blur(6px);
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.25s ease;
    }
    .modal-overlay.show {
      opacity: 1;
      pointer-events: all;
    }
    .modal-card {
      background: rgba(15, 23, 42, 0.92);
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-radius: 18px;
      padding: 36px 40px;
      max-width: 440px;
      width: 90%;
      box-shadow: 0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(239,68,68,0.1);
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 16px;
      animation: modalIn 0.3s cubic-bezier(0.34,1.56,0.64,1);
    }
    @keyframes modalIn {
      from { transform: scale(0.85) translateY(20px); opacity: 0; }
      to   { transform: scale(1)    translateY(0);    opacity: 1; }
    }
    .modal-icon {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: rgba(239, 68, 68, 0.15);
      border: 2px solid rgba(239, 68, 68, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
    }
    .modal-title {
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .modal-message {
      font-size: 13px;
      color: #94a3b8;
      line-height: 1.6;
    }
    .modal-code {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 1px;
      color: #ef4444;
      text-transform: uppercase;
      background: rgba(239,68,68,0.1);
      border-radius: 4px;
      padding: 3px 8px;
    }
    .modal-btn {
      margin-top: 8px;
      padding: 10px 32px;
      background: linear-gradient(135deg, #ef4444, #dc2626);
      border: none;
      border-radius: 8px;
      color: #fff;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .modal-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(239,68,68,0.35); }

    /* Results Dashboard */
    .results-summary {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      background: var(--card-bg);
      border: 1px solid var(--glass-border);
      border-radius: 12px;
      padding: 12px;
    }
    .metric {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
    }
    .metric .val {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }
    .metric .val.text-orange {
      color: var(--accent);
    }
    .metric .lbl {
      font-size: 10px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* Fuel Stops List */
    .stops-section {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .stops-section h4 {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    #stops-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .stop-card {
      background: var(--card-bg);
      border: 1px solid var(--glass-border);
      border-radius: 10px;
      padding: 12px;
      display: flex;
      gap: 12px;
      align-items: flex-start;
      transition: all 0.2s ease;
    }
    .stop-card:hover {
      border-color: rgba(255, 255, 255, 0.15);
      background: rgba(255, 255, 255, 0.02);
    }
    .stop-index {
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      flex-shrink: 0;
      margin-top: 1px;
    }
    .stop-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .gmaps-stop-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-left: auto;
      padding: 4px;
      border-radius: 8px;
      transition: transform 0.2s ease, background 0.2s ease, filter 0.2s ease;
      text-decoration: none;
      align-self: center;
    }
    .gmaps-stop-icon:hover {
      transform: scale(1.25) translateY(-2px);
      background: rgba(234, 67, 53, 0.12);
      filter: drop-shadow(0 3px 6px rgba(234,67,53,0.5));
    }
    .stop-title {
      font-size: 13px;
      font-weight: 600;
      color: #fff;
    }
    .stop-addr {
      font-size: 11px;
      color: var(--text-muted);
    }
    .stop-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 6px;
      font-size: 11px;
    }
    .stop-metric-item {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--glass-border);
      border-radius: 4px;
      padding: 2px 6px;
    }
    .stop-metric-item span {
      color: var(--text-muted);
    }
    .stop-metric-item b {
      color: #fff;
    }
    .stop-metric-item b.orange {
      color: var(--accent);
    }

    /* Custom Map Markers */
    .leaflet-container {
      background: #0f172a !important;
    }
    .custom-marker-end {
      background: #1e293b;
      color: #fff;
      font-weight: 700;
      font-size: 12px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid var(--primary);
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    .custom-marker-fuel {
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      font-size: 11px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid #fff;
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      #app-container {
        flex-direction: column-reverse;
      }
      #sidebar {
        position: relative;
        top: 0;
        left: 0;
        width: 100%;
        max-height: 50vh;
        border-radius: 0;
        border-width: 1px 0 0 0;
        box-shadow: none;
      }
      #map {
        flex: 1;
        height: 50vh;
      }
    }
  </style>
</head>
<body>

  <div id="app-container">
    <!-- Sidebar Panel (Forms + Results) -->
    <div id="sidebar">
      <!-- Collapse toggle -->
      <button id="collapse-btn" onclick="toggleSidebar()" title="Toggle sidebar">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M9 2L4 7L9 12" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <div class="header">
        <h2>Fuel Route Optimizer</h2>
        <p>Dynamic Programming cost-optimal routing service</p>
      </div>
      
      <div class="divider"></div>
      
      <!-- Search Form -->
      <form id="route-form">
        <div class="form-group">
          <label for="start">Start Location</label>
          <input type="text" id="start" placeholder="e.g. Chicago, IL" required/>
        </div>
        <div class="form-group">
          <label for="destination">Destination Location</label>
          <input type="text" id="destination" placeholder="e.g. Los Angeles, CA" required/>
        </div>
        
        <div class="form-row">
          <div class="form-group half">
            <label for="tank_size">Tank Range (mi)</label>
            <input type="number" id="tank_size" value="500" min="50" max="2000" required/>
          </div>
          <div class="form-group half">
            <label for="mpg">Vehicle MPG</label>
            <input type="number" id="mpg" value="10" min="1" max="100" required/>
          </div>
        </div>
        
        <div class="form-group">
          <label for="detour">Max Detour (mi)</label>
          <input type="number" id="detour" value="25" min="1" max="150" required/>
        </div>
        
        <button type="submit" id="btn-submit">
          <span id="btn-label">Calculate Optimal Route</span>
          <div class="spinner" id="btn-spinner"></div>
        </button>
      </form>
      
      <!-- Error Modal -->
      <div id="error-modal" class="modal-overlay">
        <div class="modal-card">
          <div class="modal-icon" id="modal-icon">⚠️</div>
          <div class="modal-code" id="modal-code">ERROR</div>
          <div class="modal-title" id="modal-title">Something went wrong</div>
          <div class="modal-message" id="modal-message">An unexpected error occurred.</div>
          <button class="modal-btn" onclick="closeErrorModal()">Dismiss</button>
        </div>
      </div>
      
      <!-- Results Area -->
      <div id="results-panel" style="display: none;">
        <div class="divider" style="margin-bottom: 16px;"></div>
        
        <!-- Summary Cards -->
        <div class="results-summary">
          <div class="metric">
            <span class="val" id="metric-miles">0.0</span>
            <span class="lbl">Miles</span>
          </div>
          <div class="metric">
            <span class="val text-orange" id="metric-cost">$0.00</span>
            <span class="lbl">Total Cost</span>
          </div>
          <div class="metric">
            <span class="val" id="metric-stops">0</span>
            <span class="lbl">Stops</span>
          </div>
        </div>

        <!-- Savings Badge -->
        <div id="savings-badge" style="display:none; margin-top:12px; background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.1)); border: 1px solid rgba(16,185,129,0.35); border-radius: 10px; padding: 10px 14px; text-align:center;">
          <div style="font-size:11px; color:#6ee7b7; letter-spacing:0.5px; margin-bottom:2px;">💰 OPTIMIZED SAVINGS</div>
          <div style="font-size:16px; font-weight:700; color:#10b981;" id="savings-amount">$0.00 saved</div>
          <div style="font-size:11px; color:#6ee7b7; margin-top:2px;" id="savings-vs">vs average corridor price</div>
        </div>

        <!-- Navigator Export Button -->
        <a id="gmaps-btn" href="#" target="_blank" rel="noopener"
          style="display:none; margin-top:10px; padding:10px 14px;
                 background:linear-gradient(135deg,rgba(66,133,244,0.18),rgba(52,168,83,0.12));
                 border:1px solid rgba(66,133,244,0.35); border-radius:10px;
                 color:#93c5fd; font-size:12px; font-weight:600;
                 text-decoration:none; display:flex; align-items:center; justify-content:center;
                 gap:8px; cursor:pointer; transition:all 0.2s ease;">
          <img src="__GOOGLE_MAPS_ICON_BASE64__" width="18" height="18" alt="Google Maps" style="object-fit: contain; flex-shrink: 0;" />
          Open in Google Maps (with all stops)
        </a>

        <div class="divider" style="margin-top: 16px; margin-bottom: 16px;"></div>
        
        <!-- Refueling Stop List -->
        <div class="stops-section">
          <h4>Refueling Schedule</h4>
          <div id="stops-list"></div>
        </div>
      </div>
    </div>

    <!-- Map Area -->
    <div id="map"></div>
  </div>

  <script>
    // Initial data injected by server
    const googleMapsIconBase64 = "__GOOGLE_MAPS_ICON_BASE64__";
    const initCoordinates = __COORDS_JSON__;
    const initStops = __STOPS_JSON__;
    const initStart = __START_LABEL__;
    const initEnd = __END_LABEL__;
    const initMeta = __META_JSON__;

    // Instantiate map - center of USA by default
    const map = L.map('map', {
      zoomControl: false
    }).setView([37.8, -96.0], 4);
    
    L.control.zoom({
      position: 'bottomright'
    }).addTo(map);

    // Tile layer - dark map background for sleek premium look
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 20
    }).addTo(map);

    let routeLayer = null;
    let markersLayer = L.layerGroup().addTo(map);
    let markerMap = {};   // sequence → Leaflet marker (for card-to-map sync)

    // Event listener for route form submission
    document.getElementById('route-form').addEventListener('submit', function(e) {
      e.preventDefault();
      calculateRoute();
    });

    // Draw route and stops on Leaflet map
    function drawMap(coordinates, stops, startLabel, endLabel) {
      // Clear previous routes/markers
      if (routeLayer) {
        map.removeLayer(routeLayer);
      }
      markersLayer.clearLayers();

      if (!coordinates || coordinates.length === 0) return;

      // Draw route polyline
      const latLngs = coordinates.map(c => [c[1], c[0]]);
      routeLayer = L.polyline(latLngs, {
        color: '#4a90e2',
        weight: 5,
        opacity: 0.85,
        lineJoin: 'round'
      }).addTo(map);

      // Fit map bounds
      map.fitBounds(routeLayer.getBounds(), {
        padding: [50, 50],
        maxZoom: 12,
        animate: true,
        duration: 1.0
      });

      // Start Marker
      const startC = coordinates[0];
      L.marker([startC[1], startC[0]], {
        icon: L.divIcon({
          html: '<div class="custom-marker-end">S</div>',
          className: '',
          iconSize: [28, 28],
          iconAnchor: [14, 14]
        })
      }).addTo(markersLayer).bindPopup(`<b>Start</b><br>${startLabel}`);

      // Destination Marker
      const endC = coordinates[coordinates.length - 1];
      L.marker([endC[1], endC[0]], {
        icon: L.divIcon({
          html: '<div class="custom-marker-end">D</div>',
          className: '',
          iconSize: [28, 28],
          iconAnchor: [14, 14]
        })
      }).addTo(markersLayer).bindPopup(`<b>Destination</b><br>${endLabel}`);

      // Draw stops — register in markerMap for card-to-map sync
      markerMap = {};
      stops.forEach((stop, idx) => {
        const sequence = stop.sequence;
        const lat = stop.lat;
        const lon = stop.lon;

        const stationQuery = encodeURIComponent(
          `${stop.station_name}, ${stop.address}, ${stop.city}, ${stop.state}`
        );
        const gmapsStopUrl = `https://www.google.com/maps/search/?api=1&query=${stationQuery}`;

        const m = L.marker([lat, lon], {
          icon: L.divIcon({
            html: `<div class="custom-marker-fuel">${sequence}</div>`,
            className: '',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          })
        }).addTo(markersLayer).bindPopup(`
          <div style="color:#1e293b; font-family:sans-serif; min-width:200px; padding:4px 0">
            <h4 style="margin:0 0 4px 0; font-size:12px">${stop.station_name}</h4>
            <div style="font-size:10px; color:#64748b; margin-bottom:6px">${stop.city}, ${stop.state}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
              <div style="font-size:11px; line-height:1.5;">
                <b>Price:</b> $${parseFloat(stop.retail_price).toFixed(3)}/gal<br>
                <b>To Pump:</b> ${parseFloat(stop.gallons_purchased).toFixed(2)} gal<br>
                <b>Cost:</b> $${parseFloat(stop.cost_at_stop).toFixed(2)}
              </div>
              <a href="${gmapsStopUrl}" target="_blank" rel="noopener" style="display: flex; align-items: center; justify-content: center; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform='scale(1)'" title="Open in Google Maps">
                <img src="${googleMapsIconBase64}" width="44" height="44" alt="Google Maps" style="object-fit: contain; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.15));" />
              </a>
            </div>
          </div>
        `);
        markerMap[sequence] = m;
      });
    }

    // Render stop list and metrics in the sidebar
    function renderResults(meta, stops) {
      document.getElementById('metric-miles').innerText = parseFloat(meta.total_distance_miles).toFixed(1);
      document.getElementById('metric-cost').innerText = `$${parseFloat(meta.total_fuel_cost_usd).toFixed(2)}`;
      document.getElementById('metric-stops').innerText = stops.length;

      // Show savings badge if data present
      const badge = document.getElementById('savings-badge');
      if (meta.savings_usd && parseFloat(meta.savings_usd) > 0) {
        const saved = parseFloat(meta.savings_usd).toFixed(2);
        const pct   = parseFloat(meta.savings_pct  || 0).toFixed(1);
        const naive = parseFloat(meta.naive_cost_usd || 0).toFixed(2);
        document.getElementById('savings-amount').textContent = `$${saved} saved`;
        document.getElementById('savings-vs').textContent = `vs $${naive} avg-price routing (${pct}% cheaper)`;
        badge.style.display = 'block';
      } else {
        badge.style.display = 'none';
      }

      // Show Google Maps export button
      const gmapsBtn = document.getElementById('gmaps-btn');
      if (stops.length > 0) {
        gmapsBtn.href = buildGoogleMapsUrl(meta, stops);
        gmapsBtn.style.display = 'block';
      } else {
        gmapsBtn.style.display = 'none';
      }

      const stopsList = document.getElementById('stops-list');
      stopsList.innerHTML = '';

      if (stops.length === 0) {
        stopsList.innerHTML = '<div style="font-size:12px; color:var(--text-muted); text-align:center; padding:10px 0;">No stops required for this route (under 500 miles).</div>';
      } else {
        stops.forEach(stop => {
          const card = document.createElement('div');
          card.className = 'stop-card';
          card.style.cursor = 'pointer';
          card.style.transition = 'background 0.2s, box-shadow 0.2s';
          // Build Google Maps URL: prefer name+address search for exact station location
          const stationQuery = encodeURIComponent(
            `${stop.station_name}, ${stop.address}, ${stop.city}, ${stop.state}`
          );
          const gmapsStopUrl = `https://www.google.com/maps/search/?api=1&query=${stationQuery}`;
          card.innerHTML = `
            <div class="stop-index">${stop.sequence}</div>
            <div class="stop-content">
              <div class="stop-title">${stop.station_name}</div>
              <div class="stop-addr">${stop.city}, ${stop.state} · ${stop.address}</div>
              <div class="stop-metrics">
                <div class="stop-metric-item"><span>Price:</span> <b>$${parseFloat(stop.retail_price).toFixed(3)}</b></div>
                <div class="stop-metric-item"><span>Pump:</span> <b class="orange">${parseFloat(stop.gallons_purchased).toFixed(2)} gal</b></div>
                <div class="stop-metric-item"><span>Cost:</span> <b class="orange">$${parseFloat(stop.cost_at_stop).toFixed(2)}</b></div>
                <div class="stop-metric-item"><span>Arrival Fuel:</span> <b>${parseFloat(stop.miles_remaining_in_tank_on_arrival).toFixed(1)} mi</b></div>
              </div>
            </div>
            <a href="${gmapsStopUrl}" target="_blank" rel="noopener" class="gmaps-stop-icon" title="Open in Google Maps" onclick="event.stopPropagation()">
              <img src="${googleMapsIconBase64}" width="20" height="20" alt="Google Maps" style="object-fit: contain; transition: transform 0.2s;" />
            </a>
          `;
          // Card-to-map sync: hover highlights, click flies map to marker
          card.addEventListener('mouseenter', () => {
            card.style.background = 'rgba(255,165,60,0.12)';
            card.style.boxShadow  = '0 0 0 1px rgba(255,165,60,0.3)';
          });
          card.addEventListener('mouseleave', () => {
            card.style.background = '';
            card.style.boxShadow  = '';
          });
          card.addEventListener('click', () => {
            const m = markerMap[stop.sequence];
            if (m) {
              map.flyTo([stop.lat, stop.lon], 13, { animate: true, duration: 1.2 });
              setTimeout(() => m.openPopup(), 1300);
            }
          });
          stopsList.appendChild(card);
        });
      }
      document.getElementById('results-panel').style.display = 'block';
    }

    // ----------------------------------------------------------------
    // Build Google Maps multi-stop navigation URL
    // ----------------------------------------------------------------
    function buildGoogleMapsUrl(meta, stops) {
      const enc = s => encodeURIComponent(s);
      const origin      = enc(meta.start);
      const destination = enc(meta.destination);
      const waypoints   = stops.map(s => enc(`${s.station_name}, ${s.city}, ${s.state}`)).join('|');
      return `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${destination}&waypoints=${waypoints}&travelmode=driving`;
    }


    // ----------------------------------------------------------------
    // Toggle sidebar collapsed / expanded
    // ----------------------------------------------------------------
    function toggleSidebar() {
      document.getElementById('sidebar').classList.toggle('collapsed');
      setTimeout(() => map.invalidateSize(), 360);
    }

    // Show error in full-screen modal and clear old route from map
    function showError(message, code) {
      // Clear the stale map route so old data doesn't mislead the user
      if (routeLayer) {
        map.removeLayer(routeLayer);
        routeLayer = null;
      }
      markersLayer.clearLayers();
      document.getElementById('results-panel').style.display = 'none';

      // Choose icon + title based on error code
      const configs = {
        'INVALID_INPUT':        { icon: '🚫', title: 'Invalid Input',              color: '#f59e0b' },
        'LOCATION_NOT_FOUND':   { icon: '📍', title: 'Location Not Found',         color: '#ef4444' },
        'ROUTE_IMPOSSIBLE':     { icon: '🛣️', title: 'Route Impossible',           color: '#ef4444' },
        'ROUTING_API_DOWN':     { icon: '🔌', title: 'Routing Service Unavailable',color: '#8b5cf6' },
        'DATABASE_ERROR':       { icon: '💾', title: 'Database Error',             color: '#ef4444' },
      };
      const cfg = configs[code] || { icon: '⚠️', title: 'Error', color: '#ef4444' };

      document.getElementById('modal-icon').textContent   = cfg.icon;
      document.getElementById('modal-icon').style.borderColor    = cfg.color + '66';
      document.getElementById('modal-icon').style.background     = cfg.color + '1a';
      document.getElementById('modal-code').textContent   = code || 'ERROR';
      document.getElementById('modal-code').style.color   = cfg.color;
      document.getElementById('modal-code').style.background     = cfg.color + '1a';
      document.getElementById('modal-title').textContent  = cfg.title;
      document.getElementById('modal-message').textContent = message;

      const overlay = document.getElementById('error-modal');
      overlay.classList.add('show');

      // Auto-dismiss after 8 seconds
      if (window._errorTimer) clearTimeout(window._errorTimer);
      window._errorTimer = setTimeout(closeErrorModal, 8000);
    }

    function closeErrorModal() {
      document.getElementById('error-modal').classList.remove('show');
      if (window._errorTimer) clearTimeout(window._errorTimer);
    }

    // Call API view to compute fuel stops
    async function calculateRoute() {
      const start = document.getElementById('start').value.trim();
      const destination = document.getElementById('destination').value.trim();
      const tank_size_miles = parseFloat(document.getElementById('tank_size').value);
      const mpg = parseFloat(document.getElementById('mpg').value);
      const max_detour_miles = parseFloat(document.getElementById('detour').value);

      // UI Loading States
      document.getElementById('btn-label').style.display = 'none';
      document.getElementById('btn-spinner').style.display = 'block';
      document.getElementById('btn-submit').disabled = true;
      closeErrorModal();  // hide any previous error modal
      document.getElementById('results-panel').style.display = 'none';

      try {
        const response = await fetch('/api/v1/route/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            start,
            destination,
            tank_size_miles,
            mpg,
            max_detour_miles
          })
        });

        const data = await response.json();
        
        if (response.ok) {
          // Draw map route & render sidebar schedule
          drawMap(data.route.geojson.geometry.coordinates, data.stops, data.meta.start, data.meta.destination);
          renderResults(data.meta, data.stops);

          // Update URL query parameters silently
          if (data.route && data.route.map_url) {
            window.history.pushState({}, '', data.route.map_url);
          } else {
            const url = new URL(window.location);
            url.searchParams.set('start', data.meta.start);
            url.searchParams.set('end', data.meta.destination);
            window.history.pushState({}, '', url);
          }
        } else {
          // Parse specific API flat errors or default validations
          let errorMsg = 'An unexpected routing error occurred.';
          let errorCode = 'ERROR';
          if (data.error) {
            errorCode = data.error.code || 'ERROR';
            if (data.error.details && typeof data.error.details === 'object') {
              const keys = Object.keys(data.error.details);
              errorMsg = data.error.message + ' — ' + keys.map(k => `${k}: ${data.error.details[k].join(', ')}`).join('; ');
            } else {
              errorMsg = data.error.message || errorMsg;
            }
          }
          showError(errorMsg, errorCode);
        }
      } catch (err) {
        showError('Network request failed. Ensure the server is running and accessible.', 'NETWORK_ERROR');
      } finally {
        document.getElementById('btn-label').style.display = 'block';
        document.getElementById('btn-spinner').style.display = 'none';
        document.getElementById('btn-submit').disabled = false;
      }
    }

    // Check if initial parameters were loaded from backend
    if (initCoordinates && initCoordinates.length > 0) {
      document.getElementById('start').value = initStart;
      document.getElementById('destination').value = initEnd;
      drawMap(initCoordinates, initStops, initStart, initEnd);
      
      // Compute metadata object wrapper for rendering initial state
      const totalCost = initStops.reduce((sum, stop) => sum + parseFloat(stop.cost_at_stop || 0), 0);
      const fakeMeta = {
        start: initStart,
        destination: initEnd,
        total_distance_miles: initCoordinates.length > 1 ? (initCoordinates.length * 10).toFixed(1) : 0, // estimate
        total_fuel_cost_usd: totalCost
      };
      
      const metaToUse = (initMeta && Object.keys(initMeta).length > 0) ? initMeta : fakeMeta;
      if (!metaToUse.start) metaToUse.start = initStart;
      if (!metaToUse.destination) metaToUse.destination = initEnd;

      renderResults(metaToUse, initStops);
    } else {
      // Pre-fill fields for standard route demo
      document.getElementById('start').value = "Washington, DC";
      document.getElementById('destination').value = "Los Angeles, CA";
    }
  </script>
</body>
</html>"""

        meta_json = json.dumps(meta)
        html = html.replace("__COORDS_JSON__", coords_json)
        html = html.replace("__STOPS_JSON__", stops_json)
        html = html.replace("__START_LABEL__", json.dumps(start_label))
        html = html.replace("__END_LABEL__", json.dumps(end_label))
        html = html.replace("__META_JSON__", meta_json)
        html = html.replace("__GOOGLE_MAPS_ICON_BASE64__", GOOGLE_MAPS_ICON_BASE64)
        return html
