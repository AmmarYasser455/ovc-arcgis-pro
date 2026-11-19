from checks.road_qc.engine import (
    find_dangles,
    find_disconnected,
    find_self_intersections,
)


def test_connected_endpoints_are_not_dangles():
    eps = {1: [(0, 0), (10, 0)], 2: [(10, 0.1), (20, 0)]}
    dangles = find_dangles(eps, tolerance=0.5)
    assert {(f, i) for f, _, _, i in dangles} == {(1, 0), (2, 1)}


def test_same_road_endpoints_do_not_connect():
    assert len(find_dangles({1: [(0, 0), (0.1, 0)]}, tolerance=0.5)) == 2


def test_closed_loop_road_is_not_dangling():
    # Start and end coincide (e.g. a roundabout): nothing dangles.
    loop = {1: [(500000.0, 4649776.0), (500000.0, 4649776.0)]}
    assert find_dangles(loop, tolerance=0.5) == []
    assert find_disconnected(loop, tolerance=0.5)[0] == []


def test_closed_loop_does_not_hide_other_dangle():
    eps = {1: [(0, 0), (0, 0)], 2: [(5, 5), (9, 9)]}
    assert {f for f, _, _, _ in find_dangles(eps, 0.5)} == {2}


def test_outside_tolerance_is_dangle():
    assert len(find_dangles({1: [(0, 0)], 2: [(1, 0)]}, tolerance=0.5)) == 2


def test_negative_coordinates_connect():
    eps = {1: [(-10.2, -5.1)], 2: [(-10.0, -5.0)]}
    assert find_dangles(eps, tolerance=0.5) == []


def test_find_disconnected():
    eps = {
        1: [(0, 0), (10, 0)],
        2: [(10, 0), (20, 0)],
        3: [(100, 100), (110, 100)],
    }
    disc, dangles = find_disconnected(eps, tolerance=0.5)
    assert disc == [3]
    assert {d[0] for d in dangles} == {1, 2, 3}


def test_find_disconnected_ignores_roads_without_endpoints():
    # A null/empty geometry yields no endpoints and must not be reported.
    eps = {1: [(0.0, 0.0), (10.0, 0.0)], 2: []}
    disc, dangles = find_disconnected(eps, tolerance=0.5)
    assert disc == [1]
    assert {d[0] for d in dangles} == {1}


def test_self_intersection_bowtie():
    verts = {1: [[(0, 0), (10, 10), (10, 0), (0, 10)]]}
    res = find_self_intersections(verts)
    assert len(res) == 1
    fid, x, y = res[0]
    assert fid == 1 and abs(x - 5) < 1e-9 and abs(y - 5) < 1e-9


def test_no_self_intersection_simple_line():
    assert find_self_intersections({1: [[(0, 0), (5, 0), (10, 5), (15, 5)]]}) == []


def test_short_part_ignored():
    assert find_self_intersections({1: [[(0, 0), (1, 1), (2, 0)]]}) == []


# Real-location fixture: a road near the Colosseum, Rome, in EPSG:32633
# (UTM 33N, metres; x = easting, y = northing).  The road runs east along
# one northing, continues, then doubles back over its own first stretch,
# so the only intersection is a collinear overlap (no crossing point).
_E0, _N0 = 291780.0, 4640640.0
_DOUBLING_BACK = [
    (_E0, _N0), (_E0 + 100.0, _N0), (_E0 + 120.0, _N0), (_E0 + 40.0, _N0),
]


def test_collinear_overlap_is_self_intersection():
    res = find_self_intersections({1: [_DOUBLING_BACK]})
    assert len(res) == 1
    fid, x, y = res[0]
    # Overlap is easting [E0+40, E0+100] along northing N0.
    assert fid == 1 and y == _N0 and _E0 + 40.0 <= x <= _E0 + 100.0


def test_collinear_overlap_reported_alongside_clean_road():
    clean = [(_E0, _N0 + 50), (_E0 + 10, _N0 + 60),
             (_E0 + 20, _N0 + 50), (_E0 + 30, _N0 + 60)]
    res = find_self_intersections({7: [_DOUBLING_BACK], 8: [clean]})
    assert [r[0] for r in res] == [7]


def test_closed_ring_is_not_self_intersecting():
    ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    assert find_self_intersections({1: [ring]}) == []


def test_duplicate_vertices_are_not_self_intersection():
    # Repeated vertex B (UTM 36N metres, Cairo area) must not be a crossing.
    a, b = (310000.0, 3320000.0), (310100.0, 3320000.0)
    c, d = (310100.0, 3320100.0), (310200.0, 3320100.0)
    assert find_self_intersections({1: [[a, b, b, c, d]]}) == []


def test_duplicate_vertices_do_not_hide_real_crossing():
    pts = [(0, 0), (4, 4), (4, 4), (4, 0), (0, 4)]
    res = find_self_intersections({7: [pts]})
    assert len(res) == 1 and res[0][0] == 7
