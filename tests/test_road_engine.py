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
