"""Open-cavity Root proxy and independent rigid Door proxy, same exported clips."""
import importlib.util
from pathlib import Path
import numpy as np
from mathutils import Vector
spec=importlib.util.spec_from_file_location('stasis_collision_source',Path(__file__).with_name('model.py'))
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
from material_classes import classified_name
engine=None

def hull(points,bone='Root'):
 v,t=engine.hull(np.array(points));return {'bone':bone,'V':v,'T':t}

def assembly():
 # The saved render mesh has delivery classifiers; reconstructing source
 # geometry still uses the generator's original material slot names.
 original={classified_name(name,source.MATERIAL_CLASSIFIERS):name for name in source.MATERIAL_CLASSIFIERS}
 source.kit.SLOTS=[original.get(m.name,m.name) for m in engine.bpy.data.objects['SK_StasisChamber'].data.materials]
 source.common.CORNER_STEPS=1;source.common.LABELS.clear();k=source.kit.Kit()
 for fn in (source.base,source.enclosure,source.crown,source.service_sides):fn(k)
 with k.frame(source.Matrix.Translation((0,.239999,0))):source.internals(k)
 return k,list(zip(k.parts,source.common.LABELS))

def envelope(parts,labels,bone='Root'):
 points=np.array([v for p,tag in parts if tag in labels and p.bone==bone for v in p.verts])
 assert len(points),labels
 return engine.box(bone,points.min(0),points.max(0))

def root(rig):
 k,parts=assembly();out=[]
 for label in ('foundation flange','lofted condenser crown'):
  p=next(p for p,tag in parts if tag==label)
  if label=='foundation flange':
   floor=np.array([v for v in p.verts if abs(v.z)<1e-6]);reduced=[]
   for corner in range(4):
    pair=floor[corner*2:corner*2+2]
    if corner in (0,2):reduced.append(np.sign(pair.mean(0))*(np.max(np.abs(floor),axis=0)-np.array((.012,.012,0))))
    else:reduced.extend(pair)
   floor=np.array(reduced);top=floor.copy();top[:,2]=p.hi.z
   out.append(hull(np.concatenate((floor,top))))
  else:out.append(hull(p.verts))
 out.append(hull([v for p,tag in parts if tag in ('lofted pump and power cabinet','load bearing chamber sill') for v in p.verts]))
 for piece in out[1:]:
  piece['V'],piece['T']=engine.fit(piece['V'],piece['T'],.020)
 # Eight annular wall sectors leave the occupant opening empty. A uniform
 # middle shoulder stays within 20 mm of all authored loft stations.
 outer=source.common.outline(1.04,1.90,.12,0)
 inner=source.common.outline(.82,1.80,.085,0)
 for i in range(8):
  j=(i+1)%8
  out.append(hull([source.FRONT@Vector((p[0],p[1],d)) for d in (0,-1.14) for p in (outer[i],outer[j],inner[i],inner[j])]))
 out.append(hull([source.FRONT@Vector(p) for d in (-1.14,-1.22) for p in source.common.outline(1.04,1.90,.12,d)]))
 for label in ('rear thermal exchange plate','coolant distribution manifold','interior lighting channel','backplane instrumentation rail'):
  for p,tag in parts:
   if tag==label:
    if label=='backplane instrumentation rail':
     side=1 if p.lo.x+p.hi.x>0 else -1
     labels=('backplane instrumentation rail','rail mounted sensor module','sensor status lens')
     chosen=[(q,t) for q,t in parts if t in labels and (q.lo.x+q.hi.x)*side>0]
     out.append(envelope(chosen,labels))
    else:out.append(engine.box('Root',np.array(p.verts).min(0),np.array(p.verts).max(0)))
 for side in (-1,1):
  chosen=[(p,t) for p,t in parts if t in ('rear coolant return tube','bored tube saddle clamp') and (p.lo.x+p.hi.x)*side>0]
  out.append(envelope(chosen,('rear coolant return tube','bored tube saddle clamp')))
  for labels in (('side service loop','side loop retaining saddle'),('roof condenser bridge pipe','roof coolant gland')):
   chosen=[(p,t) for p,t in parts if t in labels and (p.lo.x+p.hi.x)*side>0]
   out.append(envelope(chosen,labels))
 for z in (.80,2.06):
  chosen=[(p,t) for p,t in parts if p.bone=='Root' and t in ('hinge bearing foot','retained hinge pin','hinge pin retaining head') and abs((p.lo.z+p.hi.z)/2-z)<.1]
  out.append(envelope(chosen,('hinge bearing foot','retained hinge pin','hinge pin retaining head')))
 k.bm.free();return out

def door(rig):
 k,parts=assembly();out=[]

 for p,tag in parts:
  if p.bone!='Door':continue
  if tag=='door pull handle':
   vertices=np.array(p.verts)
   out.append(engine.box('Door',vertices.min(0),vertices.max(0)))
  if tag=='door hinge barrel and welded leaf':out.append(engine.box('Door',np.array(p.verts).min(0),np.array(p.verts).max(0)))
 k.bm.free();return out
def panel(rig,mesh):
 k,parts=assembly()
 out=[hull([source.FRONT@Vector(p) for d in (-.008,.028) for p in source.common.outline(1.0,1.9,.1,d)],'Door')]
 for z in (.80,2.06):
  chosen=[(p,t) for p,t in parts if t in ('door compression latch','seated latch lever') and abs((p.lo.z+p.hi.z)/2-z)<.1]
  out.append(envelope(chosen,('door compression latch','seated latch lever'),'Door'))
 k.bm.free();return 'SK_StasisChamberDoorCol',out

CUSTOM={'SK_StasisChamberGlass':panel}
BONE_OVERRIDE={'Root':root,'Door':door}
TRI_MAX=500
