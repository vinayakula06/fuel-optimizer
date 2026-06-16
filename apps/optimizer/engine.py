import math
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

def optimize_fuel_stops(
    stations: List[Dict[str, Any]],
    total_distance: float,
    tank_range: float = 500.0,
    mpg: float = 10.0
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Two-phase optimal fuel stop engine.

    Phase 1 — DP path selection:
        dp[i] = minimum cost to reach node i.
        Uses "buy just enough + buffer" for path cost estimation so the DP
        correctly compares paths on an apples-to-apples basis.

    Phase 2 — Quantity optimisation (forward simulation with tank state):
        Given the chosen stop sequence, simulate forward.  At each stop decide:
        - If this stop is the cheapest (or tied) among all reachable real stations
          from here, fill to the physical tank capacity (tank_range - current_range).
        - Otherwise buy only enough to reach the next stop plus a safety buffer.
        This correctly accounts for remaining fuel in the tank on arrival.
    """

    # ------------------------------------------------------------------
    # 1. Build route array: [origin] + valid_stations + [destination]
    # ------------------------------------------------------------------
    origin = {
        'id': 'start', 'name': 'Starting Point',
        'address': '', 'city': '', 'state': '',
        'retail_price': 0.0, 'latitude': 0.0, 'longitude': 0.0,
        'miles_from_start': 0.0
    }
    destination = {
        'id': 'end', 'name': 'Destination',
        'address': '', 'city': '', 'state': '',
        'retail_price': 0.0, 'latitude': 0.0, 'longitude': 0.0,
        'miles_from_start': total_distance
    }

    valid_stations = [s for s in stations if 0 < s['miles_from_start'] < total_distance]
    valid_stations.sort(key=lambda s: s['miles_from_start'])

    route = [origin] + valid_stations + [destination]
    n = len(route)

    # ------------------------------------------------------------------
    # 2. DP — choose which stops to visit (cost estimation only)
    #    OPTIMISATION: search predecessors backwards and break early.
    #    Stations are sorted by miles_from_start, so once dist > tank_range
    #    going further back can only make dist larger — safe to stop.
    #    Reduces O(N²) → O(N·K) where K = avg stations per tank window.
    # ------------------------------------------------------------------
    dp = [math.inf] * n
    dp[0] = 0.0
    parent = [-1] * n

    for i in range(1, n):
        miles_i = route[i]['miles_from_start']
        for j in range(i - 1, -1, -1):   # iterate BACKWARDS
            dist = miles_i - route[j]['miles_from_start']
            if dist > tank_range:
                break  # all further j's are even farther away — stop early

            if j == 0:
                # Start full, no purchase cost
                cost = 0.0
            else:
                price_j = float(route[j]['retail_price'])
                # Estimate cost: buy just enough to reach i plus a 30-mile buffer
                # Add a $10.00 stop penalty to avoid routes with too many micro-stops
                gallons_est = min(tank_range, dist + 30.0) / mpg
                cost = (gallons_est * price_j) + 10.0

            total = dp[j] + cost
            if total < dp[i]:
                dp[i] = total
                parent[i] = j

    # ------------------------------------------------------------------
    # 3. Check feasibility
    # ------------------------------------------------------------------
    if dp[-1] == math.inf:
        raise ValueError(
            "Route impossible: gap greater than tank range with no stations available."
        )

    # ------------------------------------------------------------------
    # 4. Backtrack → ordered stop indices (excluding origin/destination)
    # ------------------------------------------------------------------
    stop_indices = []
    cur = n - 1
    while parent[cur] != -1:
        prev = parent[cur]
        if prev != 0:          # skip origin; it's not a refuel stop
            stop_indices.append(prev)
        cur = prev
    stop_indices.reverse()   # chronological order

    # ------------------------------------------------------------------
    # 5. Phase 2: forward simulation — compute optimal fill quantities
    #    with real tank state at each stop.
    # ------------------------------------------------------------------
    # Build the list of chosen route-node indices in order:
    # [0=origin, ...stop_indices..., n-1=destination]
    chosen = [0] + stop_indices + [n - 1]

    current_range = tank_range    # tank starts full
    prev_miles = 0.0
    optimal_stops = []

    for pos, idx in enumerate(chosen):
        if idx == 0:
            # Origin: tank is full, just record starting position
            prev_miles = 0.0
            continue

        node = route[idx]
        miles = float(node['miles_from_start'])

        # Fuel consumed driving here
        dist_driven = miles - prev_miles
        range_on_arrival = current_range - dist_driven

        if idx == n - 1:
            # Destination — no refuel, just update state and exit
            current_range = range_on_arrival
            break

        # --- Decide how much to buy ---
        price_here = float(node['retail_price'])

        # Next real stop (not destination)
        next_idx = chosen[pos + 1]
        next_is_destination = (next_idx == n - 1)
        dist_to_next = route[next_idx]['miles_from_start'] - miles

        # Find cheapest REAL station among the CHOSEN stops that are
        # reachable from here with a full tank (excludes destination).
        # We only care about stops we'll actually visit, not all DB stations.
        min_price_ahead = min(
            (float(route[future_idx]['retail_price'])
             for future_idx in chosen[pos + 1:]     # stops after current, in order
             if future_idx != n - 1                  # exclude destination
             and route[future_idx]['miles_from_start'] - miles <= tank_range),
            default=math.inf
        )

        # Physical tank capacity available
        tank_capacity_gal = tank_range / mpg
        space_in_tank_gal = tank_capacity_gal - (range_on_arrival / mpg)

        if price_here <= min_price_ahead:
            # Cheapest (or tied) reachable ahead — fill to physical tank limit
            gallons = space_in_tank_gal
            if next_is_destination:
                gallons_needed = (dist_to_next + 30.0) / mpg - (range_on_arrival / mpg)
                gallons = min(gallons, max(gallons_needed, 0.0))
        elif next_is_destination:
            # Buy only what is needed to reach the destination + 30-mile safety buffer
            gallons_needed = (dist_to_next + 30.0) / mpg - (range_on_arrival / mpg)
            gallons = min(max(gallons_needed, 0.0), space_in_tank_gal)
        elif dist_to_next > tank_range - 30.0:
            # Must fill fully to safely reach next stop
            gallons = space_in_tank_gal
        else:
            gallons_needed = (dist_to_next + 30.0) / mpg - (range_on_arrival / mpg)
            gallons = min(max(gallons_needed, 0.0), space_in_tank_gal)

        gallons = round(gallons, 2)
        cost = round(gallons * price_here, 2)

        # Update tank state
        current_range = min(tank_range, range_on_arrival + gallons * mpg)

        stop_record = {
            'id': node.get('id'),
            'sequence': len(optimal_stops) + 1,
            'station_name': node.get('name', ''),
            'name': node.get('name', ''),
            'address': node.get('address', ''),
            'city': node.get('city', ''),
            'state': node.get('state', ''),
            'retail_price': round(price_here, 3),
            'lat': node.get('latitude', 0.0),
            'lon': node.get('longitude', 0.0),
            'latitude': node.get('latitude', 0.0),
            'longitude': node.get('longitude', 0.0),
            'miles_from_start': round(miles, 2),
            'gallons_purchased': gallons,
            'gallons_to_pump': gallons,
            'cost_at_stop': cost,
            'estimated_cost': cost,
            'range_on_arrival': round(range_on_arrival, 2),
            'miles_remaining_in_tank_on_arrival': round(range_on_arrival, 2),
        }
        optimal_stops.append(stop_record)
        prev_miles = miles

    # ------------------------------------------------------------------
    # 6. Prune micro-stops (< 2 gal) where predecessor is cheaper/equal
    # ------------------------------------------------------------------
    pruned = []
    for stop in optimal_stops:
        if stop['gallons_purchased'] < 2.0 and pruned:
            prev = pruned[-1]
            if prev['retail_price'] <= stop['retail_price']:
                # Absorb into predecessor (already cheaper)
                prev['gallons_purchased'] = round(
                    prev['gallons_purchased'] + stop['gallons_purchased'], 2
                )
                prev['gallons_to_pump'] = prev['gallons_purchased']
                prev['cost_at_stop'] = round(
                    prev['gallons_purchased'] * prev['retail_price'], 2
                )
                prev['estimated_cost'] = prev['cost_at_stop']
                logger.debug(
                    f"Pruned micro-stop '{stop['station_name']}' "
                    f"({stop['gallons_purchased']} gal) into predecessor"
                )
                continue
        pruned.append(stop)

    # ------------------------------------------------------------------
    # 7. Re-sequence
    # ------------------------------------------------------------------
    for idx, stop in enumerate(pruned):
        stop['sequence'] = idx + 1

    # ------------------------------------------------------------------
    # 8. Final forward simulation to recompute exact range_on_arrival
    #    (needed after pruning may have changed quantities)
    # ------------------------------------------------------------------
    current_range = tank_range
    prev_miles = 0.0
    for stop in pruned:
        dist_driven = stop['miles_from_start'] - prev_miles
        range_on_arrival = current_range - dist_driven
        stop['range_on_arrival'] = round(range_on_arrival, 2)
        stop['miles_remaining_in_tank_on_arrival'] = round(range_on_arrival, 2)
        current_range = min(tank_range, range_on_arrival + stop['gallons_purchased'] * mpg)
        prev_miles = stop['miles_from_start']

    total_money_spent = round(sum(s['cost_at_stop'] for s in pruned), 2)

    # ------------------------------------------------------------------
    # 9. Compute naive baseline cost
    #    A naive driver fills up at every station proportionally using
    #    the corridor's average price — no smart buy-more-cheap logic.
    #    savings = naive_cost - optimal_cost  (always >= 0)
    # ------------------------------------------------------------------
    station_prices = [
        float(r['retail_price'])
        for r in route[1:-1]   # exclude synthetic origin/destination nodes
        if float(r.get('retail_price', 0)) > 0
    ]
    if station_prices:
        avg_price = sum(station_prices) / len(station_prices)
    elif pruned:
        avg_price = sum(float(s['retail_price']) for s in pruned) / len(pruned)
    else:
        avg_price = 0.0   # zero-stop trip: no fuel purchased at all

    total_gallons_needed = total_distance / mpg
    naive_cost = round(avg_price * total_gallons_needed, 2)

    logger.info(
        f"Optimization complete: {len(pruned)} stops, "
        f"optimal ${total_money_spent}, naive ${naive_cost}, "
        f"saved ${round(naive_cost - total_money_spent, 2)}"
    )

    return pruned, total_money_spent, naive_cost


def find_optimal_fuel_stops(
    stations: List[Dict[str, Any]],
    total_distance: float,
    tank_range: float = 500.0,
    mpg: float = 10.0
) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    Wrapper mapping back to optimize_fuel_stops for backward compatibility.
    Returns (stops, optimal_cost, naive_cost).
    """
    return optimize_fuel_stops(stations, total_distance, tank_range, mpg)
