"""Consolidate a map's proposed floor rectangles into native platform configs."""
import math
from platform_footprint import outline

def consolidate(markers):
    groups={}
    for m in markers:
        if m['role']=='platform' and m['helper_family']!='bridge':groups.setdefault(m['deck'],[]).append(m)
    replacements={};removed=set()
    bridges=[m for m in markers if m['role']=='platform' and m['helper_family']=='bridge']
    for deck,parts in groups.items():
        bases=[m for m in parts if not m['helper_family'].startswith('platform_lip')]
        assert len(bases)==1,(deck,'one base with proposed extensions required')
        base=dict(bases[0]);px,py,pz=base['position_blender'];angle=base['rotation_blender'][2]
        def local(x,y):return (math.cos(angle)*(x-px)+math.sin(angle)*(y-py),-math.sin(angle)*(x-px)+math.cos(angle)*(y-py))
        rects=[]
        for part in parts:
            a,b,c,d=part['module_rect'];corners=[local(x,y) for x in (a,c) for y in (b,d)]
            rects.append([round(min(p[0] for p in corners),6),round(min(p[1] for p in corners),6),round(max(p[0] for p in corners),6),round(max(p[1] for p in corners),6)])
        i=parts.index(bases[0]);main=rects[i];extensions=[r for j,r in enumerate(rects) if j!=i]
        w,d=main[2]-main[0],main[3]-main[1]
        boundary=outline(rects);omitted=[]
        def world(p):return (px+math.cos(angle)*p[0]-math.sin(angle)*p[1],py+math.sin(angle)*p[0]+math.cos(angle)*p[1])
        for p,q in zip(boundary,boundary[1:]+boundary[:1]):
            a,b=world(p),world(q)
            for bridge in bridges:
                if abs(bridge['position_blender'][2]-pz)>.001:continue
                x0,y0,x1,y1=bridge['module_rect']
                if abs(a[0]-b[0])<.001 and min(abs(a[0]-x0),abs(a[0]-x1))<.001:
                    lo=max(min(a[1],b[1]),y0);hi=min(max(a[1],b[1]),y1)
                    if hi>lo+.001:omitted.append([local(a[0],lo),local(a[0],hi)])
                if abs(a[1]-b[1])<.001 and min(abs(a[1]-y0),abs(a[1]-y1))<.001:
                    lo=max(min(a[0],b[0]),x0);hi=min(max(a[0],b[0]),x1)
                    if hi>lo+.001:omitted.append([local(lo,a[1]),local(hi,a[1])])
        base.update(helper_family='platform',size_m=[w,d],extension_rects_m=extensions,omit_border_segments_m=omitted,
                    module_rect=[min(m['module_rect'][0] for m in parts),min(m['module_rect'][1] for m in parts),max(m['module_rect'][2] for m in parts),max(m['module_rect'][3] for m in parts)],
                    asset_suffix='_module_platform_'+deck,union_figma_nodes=[m['figma_node'] for m in parts])
        replacements[bases[0]['name']]=base;removed.update(m['name'] for m in parts if m!=bases[0])
    return [replacements.get(m['name'],m) for m in markers if m['name'] not in removed]
