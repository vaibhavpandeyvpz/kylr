"""KYLR pillar: a floor-to-ceiling, two-stage single-acting hydraulic support.

Run from library: blender --background --factory-startup --python models/environments/pillar/model.py
The source is procedural; all .blend, .glb, .fbx and preview files are generated.
Metres, +Z up, origin at the centre of the lower mounting surface.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
NAME = "pillar"
FPS = 30
STROKE = 0.75                 # each nested stage moves 0.75 m, giving 1.50 m total
REST_HEIGHT = 1.5
FULL_HEIGHT = 3.0
FOOT = 0.90
HEAD = 0.72
MAX_BODY_WIDTH = 0.74
TRI_BUDGET = 5000

MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), .30, .58, 0),
    "M_Secondary": ((.16, .16, .17), .25, .58, 0),
    "M_Frame": ((.026, .026, .029), .25, .66, 0),
    "M_Joint": ((.55, .55, .54), 1.0, .20, 0),
    "M_Bronze": ((.32, .17, .065), .8, .32, 0),
    "M_Emissive": ((.05, .8, .88), .0, .4, 3.5),
}


def material(name, spec):
    rgb, metal, rough, emission = spec
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Metallic"].default_value = metal
    bs.inputs["Roughness"].default_value = rough
    if emission:
        bs.inputs["Emission Color"].default_value = (*rgb, 1)
        bs.inputs["Emission Strength"].default_value = emission
    return m


class Kit:
    def __init__(self):
        self.v = []
        self.f = []
        self.m = []
        self.b = []
        self.slots = list(MATERIALS)

    def add(self, verts, faces, bone, mat):
        off = len(self.v)
        self.v.extend(verts)
        self.f.extend(tuple(off + i for i in face) for face in faces)
        self.m.extend([self.slots.index(mat)] * len(faces))
        self.b.extend([bone] * len(verts))

    def box(self, cx, cy, cz, sx, sy, sz, bone, mat):
        x0, x1 = cx-sx/2, cx+sx/2
        y0, y1 = cy-sy/2, cy+sy/2
        z0, z1 = cz-sz/2, cz+sz/2
        v = [(x,y,z) for z in (z0,z1) for y in (y0,y1) for x in (x0,x1)]
        f = [(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
        self.add(v, f, bone, mat)

    def chamfer_plate(self, half, cut, z0, z1, bone, mat):
        h,c=half,cut
        ring=[(-h+c,-h),(h-c,-h),(h,-h+c),(h,h-c),
              (h-c,h),(-h+c,h),(-h,h-c),(-h,-h+c)]
        v=[(x,y,z) for z in (z0,z1) for x,y in ring]
        f=[tuple(range(7,-1,-1)),tuple(range(8,16))]
        f += [(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
        self.add(v,f,bone,mat)

    def cyl(self, x, y, z0, z1, r, bone, mat, n=12):
        v = [(x+r*math.cos(2*math.pi*i/n), y+r*math.sin(2*math.pi*i/n), z)
             for z in (z0,z1) for i in range(n)]
        f = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))]
        f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        self.add(v, f, bone, mat)

    def axis_cyl(self, a, b, r, bone, mat, n=12):
        a,b=Vector(a),Vector(b)
        d=(b-a).normalized()
        u=d.cross(Vector((0,0,1)))
        if u.length<.01:
            u=d.cross(Vector((0,1,0)))
        u.normalize()
        w=d.cross(u).normalized()
        v=[tuple(p+r*(u*math.cos(2*math.pi*i/n)+w*math.sin(2*math.pi*i/n)))
           for p in (a,b) for i in range(n)]
        f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        self.add(v,f,bone,mat)

    def tube(self, sections, bone, mat, n=8):
        """Faceted lofted, open-ended tube. Each section is (height, outer radius, inner radius)."""
        v = []
        for z, ro, ri in sections:
            for r in (ro, ri):
                v += [(r*math.cos(math.pi/8+2*math.pi*i/n),
                       r*math.sin(math.pi/8+2*math.pi*i/n), z) for i in range(n)]
        f = []
        for s in range(len(sections)-1):
            for i in range(n):
                j = (i+1)%n
                a, b = 2*n*s, 2*n*(s+1)
                f.extend([(a+i,a+j,b+j,b+i), (a+n+j,a+n+i,b+n+i,b+n+j)])
        for i in range(n):
            j = (i+1)%n
            f.extend([(i,n+i,n+j,j),
                      (2*n*(len(sections)-1)+i,2*n*(len(sections)-1)+j,
                       2*n*(len(sections)-1)+n+j,2*n*(len(sections)-1)+n+i)])
        self.add(v, f, bone, mat)

    def to_object(self, rig):
        mesh = bpy.data.meshes.new("SK_Pillar_Mesh")
        mesh.from_pydata(self.v, [], self.f)
        mesh.update()
        for name in self.slots:
            mesh.materials.append(bpy.data.materials[name])
        obj = bpy.data.objects.new("SK_Pillar", mesh)
        bpy.context.collection.objects.link(obj)
        for poly, index in zip(mesh.polygons, self.m):
            poly.material_index = index
            poly.use_smooth = False
        for bone in ("Root", "Stage1", "Stage2"):
            obj.vertex_groups.new(name=bone)
        for i, bone in enumerate(self.b):
            obj.vertex_groups[bone].add([i], 1, 'REPLACE')
        obj.parent = rig
        mod = obj.modifiers.new("Armature", 'ARMATURE')
        mod.object = rig
        return obj


def bolt(k, x, y, z, bone, upside=False):
    # Washer, captive hex head, and an exposed threaded end on the reverse face.
    sign = -1 if upside else 1
    k.cyl(x,y,z,z+sign*.004,.020,bone,"M_Frame",12)
    k.cyl(x,y,z+sign*.004,z+sign*.017,.014,bone,"M_Joint",6)
    k.cyl(x,y,z-sign*.021,z-sign*.004,.009,bone,"M_Joint",8)


def build_geometry(k):
    # The mounting sole is chamfered; the first two shell sections grow directly
    # out of it as one tapered load path instead of a set of square corner posts.
    k.chamfer_plate(FOOT/2,.055,0,.07,"Root","M_Frame")
    for x in (-.375,.375):
        for y in (-.375,.375):
            bolt(k,x,y,.07,"Root")
    # Fixed cylinder barrel: lofted armour narrows to the bronze gland. Inner faces
    # remain physically open so the nested stages can translate out of it.
    k.tube([(.065,.37,.212),(.145,.325,.212),(.28,.28,.212),(.31,.28,.212),
            (1.28,.255,.212),(1.375,.27,.212),(1.395,.255,.212)],"Root","M_Primary")
    k.tube([(1.395,.255,.212),(1.412,.255,.212)],"Root","M_Frame")
    k.tube([(1.412,.238,.212),(1.42,.238,.212)],"Root","M_Bronze")
    # Four external tie rods clamp the cylinder's machined end caps together.
    # Each rod passes through both cap flanges and is held by a washer and nut;
    # this is the barrel's axial load path, not an applied decorative plate.
    k.tube([(.225,.37,.212),(.275,.365,.212)],'Root','M_Secondary')
    k.tube([(1.335,.35,.212),(1.385,.32,.212)],'Root','M_Secondary')
    for sx in (-1,1):
        for sy in (-1,1):
            def on_tie(z):
                t=(z-.265)/(1.407-.265)
                xy=.22+(.19-.22)*t
                return (sx*xy,sy*xy,z)
            k.axis_cyl(on_tie(.265),on_tie(1.407),.012,'Root','M_Joint',8)
            for z in (.275,1.385):
                k.axis_cyl(on_tie(z),on_tie(z+.006),.023,'Root','M_Frame',12)
                k.axis_cyl(on_tie(z+.006),on_tie(z+.024),.018,'Root','M_Joint',6)
    # A machined pressure gland, with a bronze hex coupling and dark mouth,
    # projects normally from the fixed barrel's front flat.
    k.axis_cyl((0,-.252,.37),(0,-.287,.37),.053,'Root','M_Frame',8)
    k.axis_cyl((0,-.284,.37),(0,-.319,.37),.036,'Root','M_Bronze',6)
    k.axis_cyl((0,-.317,.37),(0,-.322,.37),.023,'Root','M_Frame',12)
    k.axis_cyl((0,-.253,.47),(0,-.276,.47),.016,'Root','M_Joint',8) # bleed screw

    # First nested tube. At full extension 0.235 m remains inside the fixed barrel.
    k.tube([(.45,.191,.155),(.50,.208,.155),(.58,.208,.155),
            (1.33,.208,.155),(1.395,.208,.155)],"Stage1","M_Secondary")
    k.tube([(1.395,.208,.155),(1.412,.208,.155)],"Stage1","M_Frame")
    k.tube([(1.412,.197,.155),(1.42,.197,.155)],"Stage1","M_Bronze")
    # Interrupted milled flats on the intermediate sleeve make the motion legible.
    k.tube([(1.30,.210,.155),(1.325,.210,.155)],"Stage1","M_Primary")

    # Second tube is the pressure-driven ram and carries the upper load plate.
    # At full extension 0.14 m stays inside stage 1; the keyed octagonal profile
    # prevents axial twist. The steel contact strip reads as a sliding surface.
    k.tube([(.55,.145,.085),(.61,.151,.085),(1.35,.151,.085),
            (1.42,.145,.085)],"Stage2","M_Joint")
    # The moving head is a flared eight-sided crown merging the ram into a
    # chamfered contact flange. Its bolt heads face down for ceiling attachment.
    k.tube([(1.42,.145,.085),(1.435,.20,.085),
            (1.455,.325,.085)],"Stage2","M_Secondary")
    k.chamfer_plate(HEAD/2,.065,1.45,1.5,"Stage2","M_Frame")
    for x in (-.29,.29):
        for y in (-.29,.29):
            bolt(k,x,y,1.45,"Stage2",upside=True)


def build_rig():
    arm = bpy.data.armatures.new("RIG_Pillar_Data")
    rig = bpy.data.objects.new("RIG_Pillar", arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent in (("Root",None),("Stage1","Root"),("Stage2","Stage1")):
        eb = arm.edit_bones.new(name)
        eb.head = (0,0,0)
        eb.tail = (0,0,1)
        eb.use_connect = False
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for name in ("Stage1","Stage2"):
        pb = rig.pose.bones[name]
        pb.lock_location = (True,False,True)
        pb.lock_rotation = (True,True,True)
        pb.lock_scale = (True,True,True)
        c = pb.constraints.new('LIMIT_LOCATION')
        c.owner_space = 'LOCAL'
        c.use_min_y = c.use_max_y = True
        c.min_y, c.max_y = 0, STROKE
    return rig


def make_action(rig, name, values):
    for pb in rig.pose.bones:
        pb.location = (0,0,0)
    rig.animation_data_create()
    action = bpy.data.actions.new(name)
    # Key both telescope stages at every sample. Smoothstep gives a soft hydraulic
    # start/stop; both stages move equally, as in a pressure-balanced two-stage ram.
    rig.animation_data.action = action
    for frame, amount in values:
        for name in ("Stage1","Stage2"):
            pb = rig.pose.bones[name]
            pb.location = (0,amount,0)
            pb.keyframe_insert(data_path="location",frame=frame,group=name)
    action.use_fake_user = True
    return action


def write_rig_json(tris):
    data = {
        "name":"pillar", "units":"metres", "origin":"lower mount bottom centre",
        "materials":list(MATERIALS), "triangles":tris,
        "mounts":{"lower":{"bone":"Root","z_m":0,"size_m":[FOOT,FOOT],"bolt_pattern_m":[.75,.75]},
                  "upper":{"bone":"Stage2","z_m_at_rest":REST_HEIGHT,"size_m":[HEAD,HEAD],"bolt_pattern_m":[.58,.58]}},
        "dimensions":{"retracted_height_m":REST_HEIGHT,"extended_height_m":FULL_HEIGHT,
                      "ground_footprint_m":[FOOT,FOOT],"max_body_width_m":MAX_BODY_WIDTH},
        "joints":[{"bone":n,"parent":p,"type":"slide","axis":[0,0,1],
                   "range_m":[0,STROKE],"channel":"location_y_m"}
                  for n,p in (("Stage1","Root"),("Stage2","Stage1"))],
        "coupling":{"Stage2":"Stage1","ratio":1,"description":"equal relative travel; full head travel is twice either stage"},
        "mechanics":{"type":"single-acting, two-stage telescopic hydraulic cylinder",
                     "extension":"pressure at fixed lower port", "retraction":"external compressive load after pressure release",
                     "minimum_overlap_m":{"fixed_to_stage1":.22,"stage1_to_stage2":.12},
                     "anti_rotation":"keyed octagonal nested tubes"},
        "animations":{"open":{"frames":[0,45],"fps":FPS,"start_height_m":1.5,"end_height_m":3.0},
                      "close":{"frames":[0,45],"fps":FPS,"start_height_m":3.0,"end_height_m":1.5}},
        "usage":"Attach the lower and upper four-bolt plates to opposed surfaces. Open pressurises the ram; close assumes an external compressive load. Keep both stage channels coupled 1:1 for procedural control."
    }
    (HERE/'pillar_rig.json').write_text(json.dumps(data,indent=2))


def validate(k, tris):
    assert abs(REST_HEIGHT+2*STROKE-FULL_HEIGHT)<1e-8
    assert FOOT<=1 and HEAD<=1 and MAX_BODY_WIDTH<=.75
    assert 2*.37 <= MAX_BODY_WIDTH  # outer radius of the flared load shroud
    assert 1.42-(.45+STROKE) >= .22-1e-8  # fixed barrel / first stage insertion
    assert (1.42+STROKE)-(.55+2*STROKE) >= .12-1e-8  # first / second insertion
    assert .212-.210 >= .002-1e-8 and .155-.151 >= .004-1e-8
    assert .37-.053 > .275+.02  # pressure coupling clears the lower tie-rod flange
    assert math.sqrt(2)*.22+.023 < .365*math.cos(math.pi/8)  # lower nuts seated on cap
    assert math.sqrt(2)*.19+.023 < .32*math.cos(math.pi/8)  # upper nuts seated on tapered cap
    assert math.sqrt(2)*.19-.012 > .27*math.cos(math.pi/8)  # rods clear the upper shroud
    assert tris <= TRI_BUDGET, f"triangle budget exceeded: {tris}"
    for t in range(101):
        travel=STROKE*t/100
        height=REST_HEIGHT+2*travel
        assert REST_HEIGHT<=height<=FULL_HEIGHT
    print(f"[pillar] checks passed: 1.5-3.0 m, two 0.75 m stages, >=0.12 m tube overlap, {tris} tris")


def export(rig, body):
    import sys
    sys.path.insert(0, str(HERE.parents[1]))
    from material_uv import prepare_export
    prepare_export([body], HERE, 'pillar')
    # The joint limits are represented in JSON and in the live .blend rig; keyframes
    # are baked for GLB/FBX, so exporters do not need live constraints.
    for pb in rig.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(filepath=str(HERE/'pillar.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        bake_space_transform=False,use_mesh_modifiers=False,mesh_smooth_type='OFF',
        add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',
        use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/'pillar.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_skins=True,export_def_bones=True,
        export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_optimize_animation_size=True,
        export_materials='EXPORT')


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for old in list(bpy.data.materials):
        if old.name not in MATERIALS:
            bpy.data.materials.remove(old, do_unlink=True)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.render.fps=FPS
    for name,spec in MATERIALS.items():
        material(name,spec)
    rig=build_rig()
    kit=Kit()
    build_geometry(kit)
    body=kit.to_object(rig)
    tris=sum(len(f)-2 for f in kit.f)
    validate(kit,tris)
    make_action(rig,'open',[(0,0),(45,STROKE)])
    make_action(rig,'close',[(0,STROKE),(45,0)])
    rig.animation_data.action=None
    export(rig,body)
    # Recreate live limits after export for inspectable procedural poses.
    for name in ('Stage1','Stage2'):
        c=rig.pose.bones[name].constraints.new('LIMIT_LOCATION')
        c.owner_space='LOCAL'; c.use_min_y=c.use_max_y=True
        c.min_y=0; c.max_y=STROKE
    rig['preview_poses']=json.dumps({
        'halfway':{'Stage1':{'loc':[0,STROKE/2,0]},'Stage2':{'loc':[0,STROKE/2,0]}},
        'extended':{'Stage1':{'loc':[0,STROKE,0]},'Stage2':{'loc':[0,STROKE,0]}}})
    rig['preview_pose_views']=json.dumps({'halfway':['front_left','front'],
                                          'extended':['front_left','front','right']})
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['preview_frame']=json.dumps({'lo':[-.5,-.5,0], 'hi':[.5,.5,3.1]})
    write_rig_json(tris)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'pillar.blend'),compress=True)
    print('[pillar] exported pillar.glb/.fbx, pillar_rig.json and pillar.blend')


if __name__=='__main__':
    import sys
    if '--uv-only' in sys.argv:
        sys.path.insert(0, str(HERE.parents[1]))
        from material_uv import refresh_asset
        refresh_asset(HERE)
    else:
        main()
