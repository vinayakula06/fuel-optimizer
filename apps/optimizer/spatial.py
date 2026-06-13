import math
import numpy as np
from scipy.spatial import cKDTree
from django.conf import settings

def project_stations_to_route(stations, route_coords):
    """
    Fast station projection using cKDTree to avoid O(N*M) broadcasting.
    Projects all N stations onto the closest M segments in milliseconds.
    """
    if not stations or len(route_coords) < 2:
        return []

    coords = np.array(route_coords)          # (M, 2)  [lon, lat]
    seg_a  = coords[:-1]                     # (M-1, 2) segment starts
    seg_b  = coords[1:]                      # (M-1, 2) segment ends
    
    # Precompute cumulative distance
    cum_dist = _cumulative_haversine(coords)  # (M,)
    
    sta_arr = np.array([[s["longitude"], s["latitude"]] for s in stations])  # (N, 2)

    # 1. KDTree to find the nearest 3 vertices for each station
    # We check the segments connected to these vertices.
    tree = cKDTree(coords)
    _, nearest_idx = tree.query(sta_arr, k=3)  # (N, 3)

    MAX_OFF_ROUTE = settings.FUEL_SEARCH_RADIUS_MILES
    result = []

    for i, station in enumerate(stations):
        # Gather candidate segment indices (i-1 and i for each vertex i)
        cand_idx = set()
        for idx in nearest_idx[i]:
            if idx > 0:
                cand_idx.add(idx - 1)
            if idx < len(seg_a):
                cand_idx.add(idx)
        
        cand_idx = list(cand_idx)
        if not cand_idx:
            continue
            
        # Extract candidate segments
        a = seg_a[cand_idx]  # (K, 2)
        b = seg_b[cand_idx]  # (K, 2)
        ab = b - a           # (K, 2)
        
        # Scaling factor for longitude to approximate flat Earth near this station
        avg_lat = np.radians((a[:, 1] + b[:, 1]) / 2.0)
        cos_lat = np.cos(avg_lat)
        
        # Scale X (longitude)
        ab_scaled = ab.copy()
        ab_scaled[:, 0] *= cos_lat
        
        ap = sta_arr[i] - a  # (K, 2)
        ap_scaled = ap.copy()
        ap_scaled[:, 0] *= cos_lat
        
        seg_len_sq = np.sum(ab_scaled ** 2, axis=1)
        seg_len_sq = np.where(seg_len_sq == 0, 1e-10, seg_len_sq)
        
        t = np.sum(ap_scaled * ab_scaled, axis=1) / seg_len_sq
        t = np.clip(t, 0.0, 1.0)
        
        # Closest point D
        closest = a + t[:, np.newaxis] * ab
        
        # Haversine from station to D
        # Vectorized over K candidates
        lon1 = np.radians(sta_arr[i, 0])
        lat1 = np.radians(sta_arr[i, 1])
        lon2 = np.radians(closest[:, 0])
        lat2 = np.radians(closest[:, 1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a_hav = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
        off_dist = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a_hav, 0, 1)))
        
        best_k = np.argmin(off_dist)
        if off_dist[best_k] > MAX_OFF_ROUTE:
            continue
            
        best_seg = cand_idx[best_k]
        best_t = t[best_k]
        seg_len_mi = _haversine(seg_a[best_seg], seg_b[best_seg])
        along_route_mi = cum_dist[best_seg] + best_t * seg_len_mi
        
        s = station.copy()
        s["miles_from_start"] = float(along_route_mi)
        result.append(s)

    result.sort(key=lambda s: s["miles_from_start"])
    return result


def _haversine(p1, p2):
    """Haversine distance in miles between two [lon, lat] points."""
    lon1, lat1 = np.radians(p1)
    lon2, lat2 = np.radians(p2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def _cumulative_haversine(coords):
    """
    Cumulative haversine distances along polyline.
    Returns array of shape (M,) where result[0] = 0.
    """
    coords_rad = np.radians(coords)             # (M, 2)
    lat = coords_rad[:, 1]
    lon = coords_rad[:, 0]

    dlat = np.diff(lat)                         # (M-1,)
    dlon = np.diff(lon)                         # (M-1,)

    a = (
        np.sin(dlat/2)**2
        + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon/2)**2
    )
    seg_dist = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    cum = np.zeros(len(coords))
    cum[1:] = np.cumsum(seg_dist)
    return cum
