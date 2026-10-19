"""Convert the audited Figma hierarchy into metres-ready placement rows."""
import json,math
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/'models/maps/skyfall'
tree=json.loads((HERE/'figma_inspection.json').read_text())
previous=json.loads((HERE/'figma_layout.json').read_text())
# Preserve delivered gizmo/module names when an earlier Figma placement is deleted.
indices={row['figma_node']:row.get('placement_index',i) for i,row in enumerate(previous['placements'])}
next_index=max(indices.values(),default=-1)+1
nodes={n[0]:n for n in tree['rows']}
placements=[]
for ident,label,kind,parent,w,h,t in tree['rows']:
    if kind not in ('RECTANGLE','ELLIPSE') or label=='Bleed':continue
    path=[];p=parent
    while p in nodes:
        n=nodes[p];path.insert(0,n[1]);p=n[3]
    placements.append(dict(figma_node=ident,label=label,size_px=[w,h],center_px=[t[0][2]+t[0][0]*w/2+t[0][1]*h/2-tree['origin'][0][2],t[1][2]+t[1][0]*w/2+t[1][1]*h/2-tree['origin'][1][2]],angle=math.atan2(t[1][0],t[0][0]),path=path))
    if ident not in indices:
        indices[ident]=next_index;next_index+=1
    placements[-1]['placement_index']=indices[ident]
snapshot=dict(file_key='0pxQrXAGeHplJ0ANVYwD8e',node='69:3',canvas_px=tree['size'],metres_per_pixel=.01,inspected=tree.get('inspected','2026-10-13'),placements=placements)
(HERE/'figma_layout.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
print(len(placements),'placements; both zones inspected directly')
