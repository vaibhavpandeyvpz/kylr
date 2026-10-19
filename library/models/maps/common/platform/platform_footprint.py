"""Rectilinear union planning for one casting, independent of Blender."""
import math

def contains(rects,x,y,margin=0):
    return any(a-margin<=x<=c+margin and b-margin<=y<=d+margin for a,b,c,d in rects)

def outline(rects):
    xs=sorted(set(round(r[i],6) for r in rects for i in (0,2)))
    ys=sorted(set(round(r[i],6) for r in rects for i in (1,3)))
    occupied={(i,j) for i in range(len(xs)-1) for j in range(len(ys)-1)
              if contains(rects,(xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2)}
    edges=[]
    for i,j in occupied:
        a,b,c,d=xs[i],ys[j],xs[i+1],ys[j+1]
        for neighbor,p,q in (((i,j-1),(a,b),(c,b)),((i+1,j),(c,b),(c,d)),
                             ((i,j+1),(c,d),(a,d)),((i-1,j),(a,d),(a,b))):
            if neighbor not in occupied:edges.append((p,q))
    links=dict(edges);assert len(links)==len(edges),'Extensions must share a complete edge, not just a corner'
    start=min(links);points=[];p=start
    while p not in points:
        points.append(p);p=links[p]
    assert p==start and len(points)==len(edges),'Footprint must be one connected shell without internal islands'
    simplified=[]
    for i,p in enumerate(points):
        before=points[i-1];after=points[(i+1)%len(points)]
        if abs((p[0]-before[0])*(after[1]-p[1])-(p[1]-before[1])*(after[0]-p[0]))>1e-8:simplified.append(p)
    return simplified

def border_plan(boundary,omit=(),width=.16):
    """Split actual perimeter at omitted spans, then inset every remaining land."""
    segments=[]
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);tx,ty=dx/length,dy/length
        cuts={0.,length};spans=[]
        for p,q in omit:
            if abs((p[0]-a[0])*ty-(p[1]-a[1])*tx)>.001 or abs((q[0]-a[0])*ty-(q[1]-a[1])*tx)>.001:continue
            lo,hi=sorted(((p[0]-a[0])*tx+(p[1]-a[1])*ty,(q[0]-a[0])*tx+(q[1]-a[1])*ty))
            lo=max(0,lo);hi=min(length,hi)
            if hi-lo>1e-5:cuts.update((lo,hi));spans.append((lo,hi))
        cuts=sorted(cuts)
        for lo,hi in zip(cuts,cuts[1:]):
            excluded=any(s<=((lo+hi)/2)<=e for s,e in spans)
            segments.append(dict(a=(a[0]+tx*lo,a[1]+ty*lo),b=(a[0]+tx*hi,a[1]+ty*hi),
                                 tangent=(tx,ty),normal=(ty,-tx),length=hi-lo,border_width=0 if excluded else width))
    inner=[]
    for index,current in enumerate(segments):
        previous=segments[index-1];p=current['a']
        u=previous['tangent'];v=current['tangent'];cross=u[0]*v[1]-u[1]*v[0]
        na=previous['normal'];nb=current['normal']
        a=(p[0]-na[0]*previous['border_width'],p[1]-na[1]*previous['border_width'])
        b=(p[0]-nb[0]*current['border_width'],p[1]-nb[1]*current['border_width'])
        if abs(cross)<1e-8:
            inner.append(a)
            if math.dist(a,b)>1e-8:inner.append(b)
        else:
            offset=((b[0]-a[0])*v[1]-(b[1]-a[1])*v[0])/cross
            inner.append((a[0]+offset*u[0],a[1]+offset*u[1]))
    return segments,inner

def docking_specs(segments):
    """Native bridge placement axes on complete exposed five-metre lands."""
    out=[]
    for index,edge in enumerate(segments):
        if edge['length']<5-.001:continue
        nx,ny=edge['normal'];at=((edge['a'][0]+edge['b'][0])/2,(edge['a'][1]+edge['b'][1])/2,0)
        label='Front' if ny<-.9 and abs(at[0])<.001 else 'Rear' if ny>.9 and abs(at[0])<.001 else 'Right' if nx>.9 and abs(at[1])<.001 else 'Left' if nx<-.9 and abs(at[1])<.001 else str(index+1)
        out.append(('BridgePlug'+label,at,math.atan2(nx,-ny)))
    return out
