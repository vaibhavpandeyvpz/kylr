"""Authoritative native platform socket positions, in metres."""

def thruster_positions(w,d):
    """User-selected loadouts, inset within the tapered belly's flat footprint."""
    import math
    span=max(w,d)
    if span<5:return []
    if span<15:return [(0,0)]
    # Identical disc-to-edge clearance on every side of the planar belly.
    gap=.5
    x=max(0,w*.35-2.5-gap);y=max(0,d*.35-2.5-gap)
    if span<25:
        while math.hypot(2*x,2*y)<5 and gap>0:
            gap=max(0,gap-.01);x=max(0,w*.35-2.5-gap);y=max(0,d*.35-2.5-gap)
        assert math.hypot(2*x,2*y)>=5,'Two native 5 m discs cannot fit this chassis'
        return [(-x,-y),(x,y)]
    assert min(2*x,2*y)>=5,'Four native 5 m discs cannot fit this chassis'
    return [(-x,-y),(x,-y),(-x,y),(x,y)]
