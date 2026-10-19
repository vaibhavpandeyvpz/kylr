"""Static one-metre beacon lantern. Headless Blender 5.2; front -Y, up +Z.

Lofted service shroud, sealed light engine, two welded guard baskets and a
gasketed opal annulus. All manufactured solids are audited before culling.
No animation, game integration, hidden wiring or fictitious hinge mechanisms.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
import bmesh
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common
kit, ROOT = common.kit, common.ROOT
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
NAME, TITLE = 'beacon_lantern', 'BeaconLantern'
HEIGHT, RADIUS, SEGMENTS, RIBS = 1.0, .390, 32, 16
emit, rod = common.emit, common.rod


def polar(r, a, z):
    return (r * math.cos(a), r * math.sin(a), z)


def drum(stations, n=SEGMENTS):
    return kit.loft_rings([[polar(r, -math.pi/2-math.pi/n+i*math.tau/n, z)
                            for i in range(n)] for z, r in stations])


def annulus(stations, n=SEGMENTS):
    """Closed hollow loft: stations are (z, outer radius, inner radius)."""
    bm = bmesh.new()
    rows = [[bm.verts.new(polar(r, -math.pi/2-math.pi/n+i*math.tau/n, z))
             for i in range(n)] for z, ro, ri in stations for r in (ro, ri)]
    for j in range(len(stations)-1):
        for side in (0, 1):
            a, b = rows[2*j+side], rows[2*j+2+side]
            for i in range(n):
                h = (i+1) % n
                bm.faces.new((a[i], a[h], b[h], b[i]))
    for j in (0, len(stations)-1):
        a, b = rows[2*j], rows[2*j+1]
        for i in range(n):
            h = (i+1) % n
            bm.faces.new((a[i], a[h], b[h], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def transform(bm, m):
    for v in bm.verts:
        v.co = m @ v.co
    return bm


def subtract(body, cutter):
    cutter.verts.index_update()
    part = SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
                           faces=[[v.index for v in f.verts] for f in cutter.faces])
    result = common.trim_seats(body, [part])
    cutter.free()
    return result


def socket(k, m, radius=.0065, depth=.003):
    with k.frame(m):
        bm = kit.machine(rod((0, 0, -depth), (0, 0, 0), radius-.00015, 6),
                         cuts=[((0, 0, -.0015), (0, 0, .005), radius*.45, 6)])
        emit(k, bm, JNT, 'flush captive socket screw')


def build_pedestal(k):
    emit(k, drum([(0, .215), (.004, .230), (.035, .230), (.048, .217)], 24),
         SEC, 'lofted ground mounting flange')
    # The grey collars and chassis carry the broad removable paint shroud.
    emit(k, drum([(.048, .160), (.060, .160), (.510, .160), (.530, .164)], 16),
         FRM, 'sealed driver chassis')
    for stations in ([ (.048, .184), (.062, .184), (.078, .177)],
                     [(.494, .177), (.510, .184), (.530, .165)]):
        emit(k, annulus([(z, r, .161 if z < .510 else .161+(z-.510)*.2)
                         for z, r in stations]), SEC, 'turned shroud end collar')
    # Three manufactured cassettes with narrow seams and a broad front door.
    for a0, a1 in ((-math.pi*.875, -math.pi*.125),
                   (-math.pi*.125, math.pi*.5),
                   (math.pi*.5, math.pi*1.125)):
        start, stop = a0+.003, a1-.003
        count = round((a1-a0)/math.tau*32)
        # Turned shoulders stiffen the broad cassette without ornamental rings.
        stations = [(.078, .177), (.103, .181), (.468, .181), (.494, .177)]
        shell = kit.loft_rings([[polar(r, start+(stop-start)*i/count, z)
                                 for i in range(count+1)] +
                                [polar(.163, start+(stop-start)*i/count, z)
                                 for i in range(count, -1, -1)]
                                for z, r in stations])
        frames = []
        for i in ((1, count-2) if a0 < -math.pi/2 < a1 else (count//2,)):
            angle = start+(stop-start)*(i+.5)/count
            flat = .181*math.cos((stop-start)/count/2)
            for z in ((.103, .468) if a0 < -math.pi/2 < a1 else (.285,)):
                m = common.frame(polar(flat, angle, z),
                                 (math.cos(angle), math.sin(angle), 0), (0, 0, 1))
                frames.append(m)
                shell = subtract(shell, transform(rod((0, 0, -.003), (0, 0, .008), .0065, 8), m))
        # Indicators sit on actual facets, with a shared pocket/insert outline.
        indicator_frames = []
        if a0 < -math.pi/2 < a1:
            for i, z in ((count//2, .405), (count//2-2, .155)):
                angle = start+(stop-start)*(i+.5)/count
                flat = .181*math.cos((stop-start)/count/2)
                m = common.frame(polar(flat, angle, z),
                                 (math.cos(angle), math.sin(angle), 0), (0, 0, 1))
                indicator_frames.append(m)
                shell = subtract(shell, transform(common.loft([(.028, .003, .0007, -.002),
                                                                (.028, .003, .0007, .008)]), m))
        emit(k, shell, PRI, 'lofted removable service cassette')
        for m in frames:
            socket(k, m)
        for m in indicator_frames:
            with k.frame(m):
                emit(k, common.loft([(.028, .003, .0007, -.002),
                                     (.028, .003, .0007, 0)]), EMI, 'flush driver status insert')


def rib(a, stations):
    """Swept flat strap, constant tangential width and radial wall thickness."""
    tangent = Vector((-math.sin(a), math.cos(a), 0))
    radial = Vector((math.cos(a), math.sin(a), 0))
    return kit.loft_rings([[Vector(polar(r, a, z))+tangent*t+radial*d
                            for t, d in ((-.0055, -.014), (.0055, -.014),
                                         (.0055, 0), (-.0055, 0))]
                           for z, r in stations])


def build_head(k):
    # Central sealed light engine supports the basket collars at both ends.
    emit(k, drum([(.530, .165), (.552, .165), (.590, .215),
                  (.678, .347), (.752, .347), (.867, .258), (.900, .258)]),
         SEC, 'sealed heat-spreading light engine')
    lower = annulus([(.530, .180, .165), (.552, .180, .165)])
    lower = kit.machine(lower, union=[
        annulus([(.678, .390, .365), (.690, .390, .365)]),
        *[rib(-math.pi/2+i*math.tau/RIBS,
              [(.542, .1791), (.614, .320),
               (.684, .3879)]) for i in range(RIBS)]])
    emit(k, lower, SEC, 'welded lower guard basket with seated strap ends')
    upper = annulus([(.880, .275, .258), (.900, .275, .258)])
    upper = kit.machine(upper, union=[
        annulus([(.740, .390, .365), (.752, .390, .365)]),
        *[rib(-math.pi/2+i*math.tau/RIBS,
              [(.746, .3879), (.822, .338),
               (.890, .2735)]) for i in range(RIBS)]])
    emit(k, upper, SEC, 'welded upper guard basket with seated strap ends')
    # Thin rubber seals occupy their own axial zones, all ends meeting exactly.
    for z0, z1 in ((.690, .692), (.738, .740)):
        emit(k, annulus([(z0, .390, .365), (z1, .390, .365)]),
             FRM, 'annular diffuser compression gasket')
    emit(k, annulus([(.692, .390, .365), (.738, .390, .365)]),
         EMI, 'sealed cyan opal beacon annulus')
    emit(k, drum([(.900, .258), (.903, .258)]), FRM, 'top cover seal')
    cap = drum([(.903, .258), (.915, .267), (.928, .267), (.928, .240),
                (.974, .204), (HEIGHT, .100)], 24)
    screws = []
    for a in (-math.pi/2, 0, math.pi/2, math.pi):
        m = common.frame(polar(.254, a, .928), (0, 0, 1), (0, 1, 0))
        screws.append(m)
        cap = subtract(cap, transform(rod((0, 0, -.003), (0, 0, .025), .0065, 8), m))
    emit(k, cap, PRI, 'lofted weather cap with recessed retaining screws')
    for m in screws:
        socket(k, m)


def main():
    kit.NAME, kit.TITLE = NAME, TITLE
    common.CORNER_STEPS = 1
    common.LABELS.clear()
    kit.MATERIALS[EMI] = ((.025, .55, .62), 0, .4, 1.5)
    kit.reset_scene()
    kit.build_materials()
    kit.JOINT_SPECS = [(ROOT, None, 'fixed', (0, 0, 0), (1, 0, 0), (0, 0, 1), None)]
    joints = kit.resolve_joints()
    rig = kit.build_rig(joints, [])
    k = kit.Kit()
    build_pedestal(k)
    build_head(k)
    pairs = common.exact_intersections(k)
    kit.check_connectivity(k, joints, [])
    body = k.to_object('SK_'+TITLE)
    kit.skin(body, rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body, rig, joints, [], [('fixed', {})], (-.001, -.001), (.001, .001))
    kit.check_coplanar(body)
    tris = kit.triangles(body)
    if '--draft' not in sys.argv:
        assert tris <= 5000, tris
    lo = [min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert abs(lo[2]) < 1e-6 and abs(hi[2]-HEIGHT) < 1e-6
    assert not bpy.data.actions
    if '--draft' not in sys.argv:
        common.prepare_export([rig, body], HERE, NAME)
        kit.select_only([rig, body])
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'), use_selection=True,
            object_types={'MESH', 'ARMATURE'}, global_scale=1, apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
            use_mesh_modifiers=False, mesh_smooth_type='OFF', add_leaf_bones=False,
            primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=True,
            bake_anim=False, path_mode='COPY', embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'), export_format='GLB',
            use_selection=True, export_yup=True, export_apply=False, export_skins=True,
            export_def_bones=True, export_animations=False, export_materials='EXPORT')
    rig['preview_poses'] = json.dumps({})
    report = dict(name=NAME, static=True, animations=[], units='metres', triangles=tris,
                  triangle_budget=5000, bounds_m=dict(lo=lo, hi=hi), tensor_height_m=1.753,
                  materials=list(kit.MATERIALS),
                  bones=[dict(name=ROOT, kind='fixed', parent=None)],
                  placement='floor centre z=0; service/front -Y; up +Z',
                  checks=dict(connected_parts=len(k.parts), exact_solid_pairs=pairs,
                              no_solid_intersections=True, coplanar=True, no_actions=True))
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report, indent=2))
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles, {len(k.parts)} connected parts; {lo} .. {hi}', flush=True)


if __name__ == '__main__':
    main()
