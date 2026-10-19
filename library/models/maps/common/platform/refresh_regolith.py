"""Regenerate separate platform dressing from authoritative footprints/cutouts.

The casting and collider exports stay unchanged. Source deposits are unioned
before the same footprint intersection and 1 mm / 0.5 m placement machining.
"""
import bpy,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
from platform_common import residue,kit,common,split_large,export
from map_shells import boolean,cutter,recess_size

def refresh(path):
    meta=json.loads(path.read_text());stem=path.name.removesuffix('_rig.json');folder=path.parent
    bpy.ops.wm.open_mainfile(filepath=str(folder/(stem+'.blend')))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    w,d=meta['size_m'];rects=[[-w/2,-d/2,w/2,d/2],*meta['extension_rects_m']]
    kit.NAME=stem
    # Saved sources use classified material names. The shared generator owns
    # the base role and installs its canonical PBR before export classification.
    if 'M_Regolith' not in bpy.data.materials:bpy.data.materials.new('M_Regolith')
    drift=residue(rig,rects,d,meta['cutouts'])
    clip=kit.prism_bm([(x,y,.25) for x,y in meta['footprint']],1,(0,0,1))
    mesh=bpy.data.meshes.new('TEMP_regolith_footprint');clip.to_mesh(mesh);clip.free()
    tool=bpy.data.objects.new('TEMP_regolith_footprint',mesh);bpy.context.collection.objects.link(tool)
    boolean(drift,tool,'INTERSECT')
    for hole in meta['cutouts']:
        x,y,_=hole['center'];cutter(drift,[x,y,0],recess_size(hole['size']),hole['depth'],hole['yaw'])
    drift['cutout_clearance_m']=.20
    meshes=split_large(drift,rig,'ArchitectureRegolith')
    common.prepare_export([rig,*meshes],folder,stem+'_regolith')
    export([rig,*meshes],folder/(stem+'_regolith'))
    counts={o.name:kit.triangles(o) for o in meshes}
    assert max(counts.values())<=5000,counts
    report=dict(name=stem+'_regolith',triangles=sum(counts.values()),meshes=counts,budget_excluded=True,gizmos=[],
                surface_construction='Boolean-unioned closed deposits, clipped and machined before separate export')
    (folder/(stem+'_regolith_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('REGOLITH_REFRESH',stem,report['triangles'],flush=True)

if __name__=='__main__':
    for path in sorted((HERE.parents[1]/'skyfall').glob('skyfall_module_platform_*_rig.json')):
        if json.loads(path.read_text()).get('source_helper')=='platform':refresh(path)
