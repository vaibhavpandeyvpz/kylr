"""User-authored resting render envelopes, L(Y) x W(X) x H(Z), metres.

Below-floor machinery counts. Preview floors, payload stand-ins, triggers,
colliders and optional shield/effect meshes do not. Motion heights can exceed
the resting height; the owning generator audits mechanical travel separately.
"""
TARGET_LWH = {
    'weapon_holder': (1, 1, 2),
    'repair_station': (2, 2, 2),
    'pulse_gun': (1, 1, .6),
    'pressure_plate': (1, 2, .2),
    'jump_pad': (1, 1, .25),
    'item_table': (1, 1, 2),
    'item_cradle': (1, 1, .5),
    'barricade': (2, 4, 1.5),
    'speed_ramp': (1, 1.5, .75),
    'energy_core': (.26, .26, .26),
    'energy_core_pickup': (.25, .25, .25),
    'shield_core': (.26, .26, .26),
    'stasis_chamber': (1.5, 1.25, 2.679),
}


def assert_authored_bounds(name, meshes, tolerance=2e-5):
    points = [obj.matrix_world @ v.co for obj in meshes for v in obj.data.vertices]
    assert points, name
    lo = [min(v[i] for v in points) for i in range(3)]
    hi = [max(v[i] for v in points) for i in range(3)]
    actual = tuple(hi[i] - lo[i] for i in (1, 0, 2))
    expected = TARGET_LWH[name]
    assert all(abs(a-b) <= tolerance for a,b in zip(actual,expected)), (name, actual, expected)
    if name == 'speed_ramp':
        assert abs(lo[2]) <= tolerance and abs(hi[2]-.75) <= tolerance, (name, 'above-ground envelope', lo, hi)
    if name == 'pressure_plate':
        assert abs(hi[2]) <= tolerance and abs(lo[2]+.2) <= tolerance, (name, 'flush unpressed envelope', lo, hi)
    print(f'[{name}] authored L x W x H {actual} m PASS', flush=True)
    return {'lo':lo, 'hi':hi, 'lwh_m':list(actual)}
