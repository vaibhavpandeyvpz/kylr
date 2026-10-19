"""Native fixture geometry probe for parametric platforms and bridge QA."""
import bpy
from pathlib import Path
HERE=Path(__file__).resolve().parent

def fixture_vertices():
    """Read actual authored sconce geometry without replacing the audited scene."""
    source=HERE.parents[2]/'environments/sconce_light/sconce_light.blend'
    with bpy.data.libraries.load(str(source),link=False) as (available,loaded):
        loaded.objects=[n for n in available.objects if n.startswith('SK_')]
    points=[obj.matrix_world@v.co for obj in loaded.objects if obj.type=='MESH' for v in obj.data.vertices]
    assert points,'missing actual sconce geometry'
    for obj in loaded.objects:bpy.data.objects.remove(obj,do_unlink=True)
    return points
