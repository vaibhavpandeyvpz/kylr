"""Refresh source placement empties after a socket-only helper change."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from platform_footprint import docking_specs
from platform_common import export
for path in (HERE.parents[1]/'skyfall').glob('skyfall_module_platform_*_rig.json'):
    report=json.loads(path.read_text())
    if report.get('source_helper')!='platform':continue
    stem=path.name.removesuffix('_rig.json');folder=path.parent
    bpy.ops.wm.open_mainfile(filepath=str(folder/(stem+'.blend')))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    report['gizmos']=[g for g in report['gizmos'] if g.get('attachment_kind')!='bridge_plug']
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith('BridgePlug'):bpy.data.objects.remove(obj,do_unlink=True)
    for tag,at,angle in docking_specs(report['perimeter']):
        matrix=Matrix.Rotation(angle,4,'Z');matrix.translation=at
        obj=bpy.data.objects.new(tag,None);bpy.context.collection.objects.link(obj);obj.parent=rig;obj.matrix_world=matrix
        obj.empty_display_type='ARROWS';obj.empty_display_size=.4;obj['attachment_kind']='bridge_plug'
        report['gizmos'].append(dict(name=tag,bone='Root',attachment_kind='bridge_plug',origin=list(at),
            matrix_world=[list(row) for row in matrix],compatible_assets=['bridge'],omit_fixture_mounts=[]))
    export([rig,*[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in report['meshes']],
        *[o for o in bpy.context.scene.objects if o.type=='EMPTY']],folder/stem)
    path.write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(stem+'.blend')),compress=True)
    print('PLATFORM_MOUNTS_REFRESH',stem,flush=True)
