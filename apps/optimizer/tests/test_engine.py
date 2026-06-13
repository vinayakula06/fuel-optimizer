import pytest
from apps.optimizer.engine import find_optimal_fuel_stops

def test_no_stop_trip():
    """
    Trip is shorter than the vehicle range (500 miles).
    Expect 0 stops and 0.0 total cost.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.0, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 200.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=400.0, tank_range=500.0, mpg=10.0)
    assert len(stops) == 0
    assert cost == 0.0


def test_single_stop_trip():
    """
    Trip is longer than vehicle range (600 miles), requires exactly 1 stop.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 400.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=600.0, tank_range=500.0, mpg=10.0)
    
    assert len(stops) == 1
    assert stops[0]['id'] == 1
    # Phase 2 (tank-aware): 400 miles driven from start, tank used 40 gal, 10 gal remain.
    # Space in tank = 50 - 10 = 40 gal. A sees no cheaper real station → fills full space.
    # Cost = 40 gal * $3.00 = $120.00
    assert cost == 120.00
    assert stops[0]['gallons_to_pump'] == 40.0
    assert stops[0]['estimated_cost'] == 120.0
    assert stops[0]['miles_remaining_in_tank_on_arrival'] == 100.0  # 500 - 400 = 100


def test_multi_stop_trip():
    """
    Long trip requiring multiple stops.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 400.0
        },
        {
            'id': 2, 'name': 'Station B', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.50, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 800.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=1200.0, tank_range=500.0, mpg=10.0)
    
    assert len(stops) == 2
    assert stops[0]['id'] == 1
    assert stops[1]['id'] == 2
    # Phase 2 (tank-aware):
    # A at mile 400: 400 mi driven, tank has 10 gal remain (100 mi range). Space = 40 gal.
    #   A ($3.00) sees B ($3.50) as only real station → A is cheapest → fills full space.
    #   Cost = 40 gal * $3.00 = $120.00. Tank now full (50 gal).
    # B at mile 800: 400 mi driven from A, tank has 10 gal remain. Space = 40 gal.
    #   B ($3.50) sees no real station ahead → fills full space.
    #   Cost = 40 gal * $3.50 = $140.00.
    # Total = $260.00
    assert cost == 260.00
    assert stops[0]['gallons_to_pump'] == 40.0
    assert stops[1]['gallons_to_pump'] == 40.0


def test_exact_range_boundary():
    """
    A station is exactly on the boundary of the range (500 miles).
    Succeeds because distance <= tank_range.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 500.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=600.0, tank_range=500.0, mpg=10.0)
    assert len(stops) == 1
    assert stops[0]['id'] == 1
    assert cost == 150.0  # Station at mile 500 fills full 50 gal @ $3.00 = $150.00


def test_unreachable_destination():
    """
    Gap between stations is greater than 500 miles, so destination is unreachable.
    Expect ValueError.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 3.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 600.0
        }
    ]
    with pytest.raises(ValueError):
        find_optimal_fuel_stops(stations, total_distance=800.0, tank_range=500.0, mpg=10.0)


def test_sub_optimal_local_minima():
    """
    DP bypasses immediate cheap station for better overall route.
    Route: Start (0) -> A (100) -> B (450) -> C (500) -> End (900)
    Prices:
      A: $4.00 (expensive, but very early)
      B: $3.00 (cheaper, but if we stop here we can only reach up to 950 miles, which is fine, but wait)
      C: $2.50 (very cheap, but at 500 miles from start. We can only reach C if we stopped at A!)
    Let's check if the DP chooses to stop at A ($4.00) so it can reach C ($2.50), rather than stopping at B ($3.00) which would make C unreachable because B to C is 50 miles, but wait:
    If we go Start -> B (450):
      We arrive at B with 50 range.
      We refill at B. We can reach up to 450 + 500 = 950 miles. So we can reach End (900) directly from B!
      If we stop at B, we buy fuel for B -> End (450 miles) at $3.00/gal.
      Cost: 45 * 3.0 = $135.00
    If we go Start -> A (100) -> C (500) -> End (900):
      We drive to A (100). We buy fuel for A -> C (400 miles) at $4.00/gal. Cost: 40 * 4 = $160.00
      We drive to C (500). We buy fuel for C -> End (400 miles) at $2.50/gal. Cost: 40 * 2.5 = $100.00
      Total Cost: 160 + 100 = $260.00. This is worse than stopping at B ($135.00).
    
    Let's change prices to make the A -> C path better:
      Let total_distance = 950 miles.
      If we go Start -> B (450) -> End (950):
        At B (450), we buy fuel for B -> End (500 miles) at $4.00/gal. Cost: 50 * 4.0 = $200.00.
      If we go Start -> A (100) -> C (550) -> End (950):
        A is at 100, C is at 550 (distance 450). But C is at 550, which is > 500, so we can't reach C from Start without stopping!
        We must stop at A (100) to reach C (550).
        At A, price is $1.00/gal. Fuel for A -> C (450 miles). Cost: 45 * 1.0 = $45.00.
        At C (550), price is $1.00/gal. Fuel for C -> End (400 miles). Cost: 40 * 1.0 = $40.00.
        Total Cost: 45 + 40 = $85.00.
      DP should choose to stop at A and C (cost $85.00) instead of B (cost $200.00), even though B is closer to the destination and avoids one stop.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 1.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 100.0
        },
        {
            'id': 2, 'name': 'Station B', 'address': '', 'city': '', 'state': '',
            'retail_price': 5.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 450.0
        },
        {
            'id': 3, 'name': 'Station C', 'address': '', 'city': '', 'state': '',
            'retail_price': 1.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 550.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=950.0, tank_range=500.0, mpg=10.0)
    
    # Phase 2 (tank-aware):
    # A at mile 100: 100 mi driven, tank has 40 gal remain. Space = 10 gal.
    #   A ($1.00) is tied cheapest with C ($1.00) → fills full space = 10 gal @ $1.00 = $10.00.
    #   Tank now full (50 gal). With 500 range, can reach C (550) which is exactly 450 mi away. OK.
    # C at mile 550: 450 mi driven from A, tank has 5 gal remain. Space = 45 gal.
    #   C ($1.00) sees no real stations → fills full space = 45 gal @ $1.00 = $45.00.
    # Total = $55.00
    assert len(stops) == 2
    assert stops[0]['id'] == 1
    assert stops[1]['id'] == 3
    assert cost == 55.00


def test_dp_optimal_selection():
    """
    DP Optimal Selection:
    Route: Start (0) -> S_1 (200) -> S_2 (400) -> S_3 (480) -> End (800)
    Prices:
      S_1: $4.00 (expensive)
      S_2: $2.00 (medium)
      S_3: $1.50 (cheapest)
    
    The DP algorithm finds the global cost-minimizing stop.
    It stops at Station C (ID 3, at 480) directly since it is reachable (480 <= 500).
    Cost:
      Start -> S_3: 0.0 (starts full)
      S_3 -> End: (800 - 480) / 10 * 1.50 = 32 * 1.50 = $48.00.
    """
    stations = [
        {
            'id': 1, 'name': 'Station A', 'address': '', 'city': '', 'state': '',
            'retail_price': 4.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 200.0
        },
        {
            'id': 2, 'name': 'Station B', 'address': '', 'city': '', 'state': '',
            'retail_price': 2.00, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 400.0
        },
        {
            'id': 3, 'name': 'Station C', 'address': '', 'city': '', 'state': '',
            'retail_price': 1.50, 'latitude': 0.0, 'longitude': 0.0, 'miles_from_start': 480.0
        }
    ]
    stops, cost, _naive = find_optimal_fuel_stops(stations, total_distance=800.0, tank_range=500.0, mpg=10.0)
    
    assert len(stops) == 1
    assert stops[0]['id'] == 3
    # S3 at mile 480: tank used 48 gal, 2 gal remain, space = 48 gal.
    # S3 ($1.50) sees no real stations → fills full space = 48 gal @ $1.50 = $72.00
    assert cost == 72.00


