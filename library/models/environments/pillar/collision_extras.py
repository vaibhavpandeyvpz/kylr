"""Compact convex colliders for the pillar's three rigid slide bodies."""

import math
import numpy as np


def octagon(bone, radius, z0, z1):
    ring = np.array([(radius*math.cos(math.pi/8+i*math.pi/4),
                      radius*math.sin(math.pi/8+i*math.pi/4)) for i in range(8)])
    v,t = engine.prism(ring,z0,z1)
    return {"bone":bone,"V":v,"T":t}


def root(_rig):
    return [engine.box('Root',(-.45,-.45,0),(.45,.45,.08)),
            octagon('Root',.37,.065,.28),octagon('Root',.28,.28,1.42),
            octagon('Root',.37,.225,.275),octagon('Root',.35,1.335,1.385)]


def stage1(_rig):
    return [octagon('Stage1',.21,.45,1.42)]


def stage2(_rig):
    return [octagon('Stage2',.153,.55,1.45),
            engine.box('Stage2',(-.36,-.36,1.43),(.36,.36,1.5))]


BONE_OVERRIDE = {'Root':root,'Stage1':stage1,'Stage2':stage2}
TRI_MAX = 300
PIECE_MAX = 8
