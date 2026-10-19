"""Closed deck and independent guard/service-frame and canopy collision."""
import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('bridge_source',Path(__file__).with_name('model.py'))
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
BONE_OVERRIDE={'Root':lambda rig:[engine.box('Root',(-2.5,-5,-.8),(2.5,0,0))]}
TRI_MAX=500


def roof_piece(side):
    points=np.array([(x,y,z) for y in (-5,0) for x,z in source.roof_section(side)])
    vertices,triangles=engine.hull(points)
    return dict(bone='Root',V=vertices,T=triangles)


def profile_piece(x,profile,width):
    points=np.array([(x+dx,y,z) for dx in (-width/2,width/2) for y,z in profile])
    vertices,triangles=engine.hull(points)
    return dict(bone='Root',V=vertices,T=triangles)


def railing_pieces(sign):
    boxes=source.mechanics.rails_boxes(sign)
    return [engine.box('Root',*box) for box in boxes[2:5]+boxes[6:]]


def canopy_pieces():
    return [profile_piece(sign*2.32,source.support_profile(y),.08) for sign in (-1,1) for y in (-4.85,-.15)]+[
        roof_piece(-1),roof_piece(1)]+[
        shield_piece(matrix) for sign,y,matrix in source.mechanics.shield_frames()]+[
        engine.box('Root',(-.14,y-.36,2.935),(.14,y+.36,3.022)) for y in (-4.04,-2.5,-.96)]


def shield_piece(matrix):
    bm=source.mechanics.shield_panel()
    vertices,triangles=engine.hull(np.array([matrix@v.co for v in bm.verts]));bm.free()
    return dict(bone='Root',V=vertices,T=triangles)


def side_frame_pieces(sign):
    x=sign*2.32
    return [engine.box('Root',(x-.045,-5,0),(x+.045,0,.16))]+[
        engine.box('Root',(x-.04,y-.09,.16),(x+.04,y+.09,1.09)) for y in (-4.85,-.15)]


CUSTOM={source.FRAME_LEFT:lambda rig,mesh:side_frame_pieces(-1),
        source.FRAME_RIGHT:lambda rig,mesh:side_frame_pieces(1),source.LEFT:lambda rig,mesh:railing_pieces(-1),
        source.RIGHT:lambda rig,mesh:railing_pieces(1),
        source.COVER:lambda rig,mesh:canopy_pieces()}
