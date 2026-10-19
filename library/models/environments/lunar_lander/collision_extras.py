"""Static pressure shell and independent landing-gear envelopes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from static_vehicle_collision import shells
TRI_MAX=1500 # Compounds export as separate meshes, each capped at 500 triangles.
import bpy
def proxy(rig,mesh):return shells(engine,rig,mesh)
def body(rig):return proxy(rig,bpy.data.objects['SK_LunarLanderBody'])
BONE_OVERRIDE={'Root':body}
CUSTOM={'SK_LunarLanderGear':proxy}
