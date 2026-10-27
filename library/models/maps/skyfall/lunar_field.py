"""Lunar impact basins and low regolith drifts, in Godot world metres."""
import math
import random
import numpy as np

IMPACTS = [
    (-7, 4, 19, 3.2, 1.2), (-29, 12, 6.5, 1.7, .65),
    (23, -16, 8, 2.1, .85), (10, 24, 4.5, 1.2, .5),
    (-5, -27, 3.7, .9, .4), (-91, -18, 25, 5, 2.3),
    (78, 55, 19, 4.2, 1.9), (-45, 97, 13, 3, 1.4),
    (32, -101, 14, 3.2, 1.5), (113, -66, 8, 2, .9),
    (-106, 83, 6, 1.6, .7),
]


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def landscape(x, z):
    radius = np.hypot(x, z)
    angle = np.arctan2(z, x)
    # A broad circular bowl and low continuous rim establish impact geology.
    q = (radius - .65*np.sin(angle*3) - .35*np.sin(angle*8)) / 68
    bowl = -7.5 * (1-smooth((q-.30)/.72))
    rim = 4.2*np.exp(-((q-1)/.10)**2)*(1+.12*np.sin(angle*5)+.04*np.sin(angle*13))
    ejecta = 1.1*np.exp(-((q-1.15)/.19)**2)
    height = bowl + rim + ejecta
    impacts = list(IMPACTS)
    rng = random.Random(70131)
    for _ in range(44):
        a = rng.random()*math.tau
        r = rng.uniform(115, 221)
        size = rng.uniform(2.8, 7)
        impacts.append((r*math.cos(a), r*math.sin(a), size, size*.22, size*.09))
    for index, (cx, cz, size, depth, rise) in enumerate(impacts):
        dx = x-cx; dz = z-cz
        a = np.arctan2(dz, dx)
        r = np.hypot(dx, dz)/size
        r *= 1+.018*np.sin(a*7+index)+.01*np.sin(a*11-index)
        depression = -depth*(1-smooth(r))
        lip = rise*np.exp(-((r-1.02)/.17)**2)
        apron = rise*.15*np.exp(-((r-1.3)/.4)**2)
        height += depression+lip+apron
    # Shallow ejecta deposits and regolith mounds retain a quiet bowl floor.
    deposits = smooth((radius-10)/10)*(1-smooth((radius-48)/14))
    ripples = (.5+.5*np.sin(x*.23+z*.10+.5*np.sin(z*.04)))**3
    height += deposits*(ripples*.24-.06)
    height += .13*np.sin(x*.40)*np.cos(z*.31)+.07*np.sin(x*1.3+z*.7)
    return height
