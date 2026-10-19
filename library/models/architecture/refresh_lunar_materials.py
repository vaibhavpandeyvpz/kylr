"""Refresh lunar materials in existing native sources without changing geometry.

Run in headless Blender from library. Map scenery and platform deposits are
rebuilt by their own generators; this handles native architecture and variants.
"""
from pathlib import Path
import hashlib,json,sys
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'maps/common'))
from lunar_material import install,NAMES
from map_shells import export

def geometry():
    digest=hashlib.sha256()
    for ob in sorted(bpy.context.scene.objects,key=lambda o:o.name):
        digest.update(ob.name.encode())
        digest.update(str(tuple(tuple(row) for row in ob.matrix_world)).encode())
        if ob.type=='MESH':
            digest.update(str([tuple(v.co) for v in ob.data.vertices]).encode())
            digest.update(str([tuple(p.vertices) for p in ob.data.polygons]).encode())
            digest.update(str([[(g.group,g.weight) for g in v.groups] for v in ob.data.vertices]).encode())
    return digest.hexdigest()

sources=[HERE/name/(name+'.blend') for name in ('bastion','bunker','cistern','hangar','hub','laboratory','lodge','shelter')]
sources+=sorted((HERE.parent/'maps/faceoff').glob('faceoff_architecture_*.blend'))
for path in sources:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    before=geometry()
    updated=[]
    for material in bpy.data.materials:
        if material.name.split('.')[0].removesuffix('_Diffuse') in NAMES:
            install(material);updated.append(material.name)
    assert updated,(path,'No lunar material found')
    assert before==geometry(),(path,'Material refresh changed geometry')
    objects=[o for o in bpy.context.scene.objects if o.type in {'MESH','ARMATURE','EMPTY'}]
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    export(objects,path.parent,path.stem,animated=True)
    print('LUNAR_MATERIAL_REFRESH',path.stem,updated,'geometry unchanged',flush=True)
