"""Measure the native door's complete hinge sweep for safe spawn closure."""
import math
from mathutils import Vector,Matrix

def swept_bounds(objects,pivot=(.55,-.65,1.43),bone='Door'):
    pivot=Vector(pivot);points=[]
    for ob in objects:
        index=ob.vertex_groups.find(bone)
        for vertex in ob.data.vertices:
            point=ob.matrix_world@vertex.co
            moving=any(group.group==index and group.weight>.5 for group in vertex.groups)
            if moving:
                points.extend(pivot+Matrix.Rotation(math.radians(angle),3,'Z')@(point-pivot) for angle in range(121))
            else:points.append(point)
    # One millimetre covers the sub-degree extrema between samples.
    return dict(lo=[min(point[i] for point in points)-.001 for i in range(3)],hi=[max(point[i] for point in points)+.001 for i in range(3)])

if __name__=='__main__':
    import bpy,json
    from pathlib import Path
    here=Path(__file__).resolve().parent
    bpy.ops.wm.open_mainfile(filepath=str(here/'stasis_chamber.blend'))
    path=here/'stasis_chamber_rig.json';report=json.loads(path.read_text())
    report['door_swept_bounds_m']=swept_bounds([ob for ob in bpy.context.scene.objects if ob.type=='MESH' and ob.name.startswith('SK_Stasis')])
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('STASIS_DOOR_SWEEP',report['door_swept_bounds_m'])
