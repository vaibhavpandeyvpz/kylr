"""Original-material UV atlases shared by the scripted model generators.

Each source material gets its own unique 0..1 layout across the body and all
head alternatives. Geometry, normals, weights, material assignments and PBR
settings are preserved; only seams and UV coordinates change.
"""
import heapq
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

PREFIX = "model"
class LayoutError(RuntimeError):
    def __init__(self, message, faces):
        super().__init__(message)
        self.faces = faces

SIZE = 2048
_preserve_uvs = False
MARGIN = 0.004


def mark_seams(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    for edge in bm.edges:
        edge.seam = (obj.get('uv_face_charts',False) or obj.name.startswith("SK_TensorShield") or not edge.is_manifold or
                     edge.link_faces[0].material_index != edge.link_faces[1].material_index or
                     edge.calc_face_angle(0.0) > math.radians(30) or
                     (edge.calc_face_angle(0.0) > math.radians(1) and
                      any(len(face.verts) > 4 for face in edge.link_faces)))
    # Smooth curved patches (rod walls, conduits) need a longitudinal opening
    # as well as the construction seams around their caps. Cut a shortest path
    # between the patch's most distant vertices; leave planar panels intact.
    unseen = set(bm.faces)
    while unseen:
        seed = min(unseen, key=lambda face: face.index)
        unseen.remove(seed)
        patch, pending = {seed}, [seed]
        while pending:
            face = pending.pop()
            for edge in face.edges:
                if edge.seam:
                    continue
                for neighbour in edge.link_faces:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        patch.add(neighbour)
                        pending.append(neighbour)
        if all(face.normal.dot(seed.normal) > 0.999 for face in patch):
            continue
        edges = {edge for face in patch for edge in face.edges if not edge.seam}
        vertices = {v for edge in edges for v in edge.verts}
        if not vertices:
            continue
        start = min(vertices, key=lambda v: v.index)
        start = max(vertices, key=lambda v: ((v.co - start.co).length_squared, -v.index))
        end = max(vertices, key=lambda v: ((v.co - start.co).length_squared, -v.index))
        distances, previous = {start: 0.0}, {}
        queue = [(0.0, start.index, start)]
        while queue:
            distance, _, vertex = heapq.heappop(queue)
            if vertex == end:
                break
            if distance > distances[vertex]:
                continue
            for edge in vertex.link_edges:
                if edge not in edges:
                    continue
                other = edge.other_vert(vertex)
                candidate = distance + edge.calc_length()
                if candidate < distances.get(other, float('inf')):
                    distances[other] = candidate
                    previous[other] = (vertex, edge)
                    heapq.heappush(queue, (candidate, other.index, other))
        while end in previous:
            end, edge = previous[end]
            edge.seam = True
    # Only write seam flags; rebuilding the mesh would reorder its polygons.
    for edge in bm.edges:
        obj.data.edges[edge.index].use_seam = edge.seam
    bm.free()


def degenerate_layout_faces(objects):
    """Batch the exact degenerate-chart failures used by validate_layouts.

    Machined castings can expose hundreds of thin faces at once; repairing one
    per atlas repack exhausted the iteration cap without a geometry problem.
    """
    faces=set()
    for obj in objects:
        mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data
        for tri in mesh.loop_triangles:
            va,vb,vc=[mesh.vertices[i].co for i in tri.vertices]
            if (vb-va).cross(vc-va).length*.5<1e-9:continue
            a,b,c=[uv[i].uv*SIZE for i in tri.loops]
            determinant=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
            if abs(determinant)<1e-8:faces.add((obj.name,tri.polygon_index))
    return faces

def validate_layouts(objects, groups, folder):
    """Check all material layouts and write 2048px authoring guides."""
    atlases = {group: np.full((SIZE, SIZE), -1, dtype=np.int16) for group in groups}
    interiors = {group: np.full((SIZE, SIZE), -1, dtype=np.int32) for group in groups}
    triangle_names = []
    coverage = dict.fromkeys(groups, 0.0)
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv = mesh.uv_layers.active.data
        for tri in mesh.loop_triangles:
            va, vb, vc = [mesh.vertices[i].co for i in tri.vertices]
            if (vb-va).cross(vc-va).length * 0.5 < 1e-9:
                continue
            group = mesh.materials[mesh.polygons[tri.polygon_index].material_index].name
            source = groups.index(group)
            labels = atlases[group]
            points = np.array([uv[i].uv[:] for i in tri.loops]) * SIZE
            a, b, c = points
            determinant = float((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]))
            if abs(determinant) < 1e-8:
                va, vb, vc = [mesh.vertices[i].co for i in tri.vertices]
                if (vb-va).cross(vc-va).length * 0.5 < 1e-9:
                    # Collinear boolean leftovers are retained in the source
                    # topology and have no rendered area to texture.
                    continue
                raise LayoutError(f'Degenerate UV triangle: {obj.name}/{tri.polygon_index}', [(obj.name, tri.polygon_index)])
            coverage[group] += abs(determinant) / (2 * SIZE * SIZE)
            lo = np.maximum(np.floor(points.min(axis=0)).astype(int), 0)
            hi = np.minimum(np.ceil(points.max(axis=0)).astype(int), SIZE - 1)
            yy, xx = np.mgrid[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
            dx, dy = xx + 0.5 - a[0], yy + 0.5 - a[1]
            u = (dx * (c[1]-a[1]) - dy * (c[0]-a[0])) / determinant
            v = ((b[0]-a[0]) * dy - (b[1]-a[1]) * dx) / determinant
            inside = (u >= 0) & (v >= 0) & (u+v <= 1)
            interior = (u > 1e-5) & (v > 1e-5) & (u+v < 1-1e-5)
            region = labels[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
            occupied = interiors[group][lo[1]:hi[1]+1, lo[0]:hi[0]+1]
            overlap = interior & (occupied >= 0)
            if np.any(overlap):
                previous = triangle_names[int(occupied[overlap][0])]
                raise LayoutError(f'Overlapping {group} UV islands: {obj.name}/{tri.polygon_index} and {previous}', [(obj.name, tri.polygon_index), previous])
            occupied[interior] = len(triangle_names)
            triangle_names.append((obj.name, tri.polygon_index))
            region[inside] = source
    for group in groups:
        labels = atlases[group]
        pixels = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
        mask = labels >= 0
        pixels[mask] = (0.7, 0.8, 0.9, 1)
        outline = mask & (~np.roll(mask, 1, 0) | ~np.roll(mask, -1, 0) |
                          ~np.roll(mask, 1, 1) | ~np.roll(mask, -1, 1))
        pixels[outline] = (0.1, 0.2, 0.3, 1)
        image = bpy.data.images.new(f'{PREFIX}_uv_{group[2:].lower()}', width=SIZE, height=SIZE, alpha=True)
        image.pixels.foreach_set(pixels.ravel())
        image.filepath_raw = str(folder / f'{image.name}.png')
        image.file_format = 'PNG'
        image.save()
        bpy.data.images.remove(image)
        print(f'[{PREFIX}] {group}: {coverage[group]:.1%} UV coverage; no overlapping triangle interiors')


def write_wireframe(objects, material, folder):
    """Render the actual polygon UV edges on a 2048px checker canvas."""
    yy, xx = np.indices((SIZE, SIZE))
    checker = ((xx // 64 + yy // 64) % 2).astype(np.float32) * 0.035 + 0.15
    edge_pixels = np.zeros((SIZE, SIZE), dtype=np.float32)
    unique_edges = set()
    for obj in objects:
        mesh = obj.data
        uvs = mesh.uv_layers.active.data
        for face in mesh.polygons:
            if mesh.materials[face.material_index].name != material:
                continue
            loops = list(face.loop_indices)
            for i, loop in enumerate(loops):
                a = tuple(uvs[loop].uv)
                b = tuple(uvs[loops[(i + 1) % len(loops)]].uv)
                key = tuple(sorted(tuple(round(v, 7) for v in point) for point in (a, b)))
                if key in unique_edges:
                    continue
                unique_edges.add(key)
                a, b = np.array(a) * (SIZE - 1), np.array(b) * (SIZE - 1)
                steps = max(2, int(np.ceil(np.max(np.abs(b - a)) * 3)) + 1)
                points = np.linspace(a, b, steps)
                x, y = np.floor(points[:, 0]).astype(int), np.floor(points[:, 1]).astype(int)
                fx, fy = points[:, 0] - x, points[:, 1] - y
                for ox, oy, weights in ((0, 0, (1-fx)*(1-fy)), (1, 0, fx*(1-fy)),
                                        (0, 1, (1-fx)*fy), (1, 1, fx*fy)):
                    px, py = np.clip(x + ox, 0, SIZE - 1), np.clip(y + oy, 0, SIZE - 1)
                    np.maximum.at(edge_pixels, (py, px), weights)
    pixels = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    pixels[:, :, :3] = (checker * (1-edge_pixels) + 0.98 * edge_pixels)[:, :, None]
    name = f'{PREFIX}_uv_{material[2:].lower()}_wireframe'
    image = bpy.data.images.new(name, width=SIZE, height=SIZE, alpha=False)
    image.pixels.foreach_set(pixels.ravel())
    image.file_format = 'PNG'
    image.filepath_raw = str(folder / f'{name}.png')
    image.save()
    bpy.data.images.remove(image)
    print(f'[{PREFIX}] {material}: wrote {SIZE}px UV wireframe ({len(unique_edges)} edges)')


def flatten_panels(objects):
    """Project planar machined charts exactly; unwrap the remaining curves.

    Large boolean n-gons can otherwise fold their narrow cut-out bridges in
    the unwrap solver. Projection preserves the panel's holes and proportions.
    """
    chart = 0
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        uv = bm.loops.layers.uv.active
        unseen = {face for face in bm.faces if face.select}
        while unseen:
            seed = min(unseen, key=lambda face: face.index)
            unseen.remove(seed)
            patch, pending = {seed}, [seed]
            while pending:
                face = pending.pop()
                for edge in face.edges:
                    if edge.seam:
                        continue
                    for neighbour in edge.link_faces:
                        if neighbour in unseen:
                            unseen.remove(neighbour)
                            patch.add(neighbour)
                            pending.append(neighbour)
            normal = seed.normal.normalized()
            origin = seed.verts[0].co
            offset = Vector((chart * 0.001, chart * 0.002))
            if (all(face.normal.dot(normal) > 0.99999 for face in patch) and
                    all(abs((v.co-origin).dot(normal)) < 1e-5 for face in patch for v in face.verts)):
                axis = min((Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
                           key=lambda axis: abs(axis.dot(normal)))
                tangent = normal.cross(axis).normalized()
                bitangent = normal.cross(tangent)
                for face in patch:
                    for loop in face.loops:
                        p = loop.vert.co-origin
                        loop[uv].uv = Vector((p.dot(tangent), p.dot(bitangent))) + offset
            else:
                # Straight rods and hydraulic barrels: their side normals
                # share a null axis. Analytic cylindrical UVs avoid a solver
                # fold on very long, narrow mechanical strips.
                normals = np.array([face.normal[:] for face in patch])
                eigenvalues, axes = np.linalg.eigh(normals.T @ normals / len(patch))
                if eigenvalues[0] < 1e-6 and eigenvalues[1] > 0.01:
                    axis = Vector(axes[:, 0])
                    verts = {v for face in patch for v in face.verts}
                    center = sum((v.co for v in verts), Vector()) / len(verts)
                    radial = (seed.verts[0].co-center)
                    tangent = (radial-axis*radial.dot(axis)).normalized()
                    bitangent = axis.cross(tangent)
                    radii = [(v.co-center-axis*(v.co-center).dot(axis)).length for v in verts]
                    radius = sum(radii) / len(radii)
                    if max(radii)-min(radii) > radius * 0.03:
                        chart += 1
                        continue  # a tapered/carved shell, not a cylindrical rod
                    for face in patch:
                        angles = [math.atan2((loop.vert.co-center).dot(bitangent),
                                             (loop.vert.co-center).dot(tangent)) for loop in face.loops]
                        if max(angles)-min(angles) > math.pi:
                            angles = [angle+math.tau if angle < 0 else angle for angle in angles]
                        for loop, angle in zip(face.loops, angles):
                            loop[uv].uv = Vector((angle*radius, (loop.vert.co-center).dot(axis))) + offset
            chart += 1
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def repair_folded_faces(objects):
    """Open a face boundary if the curved-chart solver folds its triangles.

    A small number of curved conduit quads need their own planar chart. This
    changes UV seams only; the source polygon and its shading remain intact.
    """
    chart = 0
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        uv = bm.loops.layers.uv.active
        # Use Mesh tessellation: the exporter uses this diagonal, which can
        # differ from BMesh's temporary edit-mode tessellation on thin quads.
        bm.faces.ensure_lookup_table()
        signs = {}
        degenerate = set()
        for tri in obj.data.loop_triangles:
            face = bm.faces[tri.polygon_index]
            if not face.select:
                continue
            by_vertex = {loop.vert.index: loop for loop in face.loops}
            loops = [by_vertex[i] for i in tri.vertices]
            va, vb, vc = [loop.vert.co for loop in loops]
            if (vb-va).cross(vc-va).length * 0.5 < 1e-9:
                continue
            a, b, c = [loop[uv].uv for loop in loops]
            area = (b.x-a.x)*(c.y-a.y) - (b.y-a.y)*(c.x-a.x)
            if abs(area) > 1e-12:
                signs.setdefault(face, set()).add(area > 0)
            else:
                degenerate.add(face)
        folded = sorted(degenerate | {face for face, winding in signs.items() if len(winding) > 1},
                        key=lambda face: face.index)
        for face in folded:
            # A folded source polygon has no faithful planar projection.
            # An isolated convex chart keeps its native rendered triangles
            # disjoint, with the same total world-area texel density.
            n = len(face.loops)
            radius = math.sqrt(max(face.calc_area(), 1e-12) /
                               (n * math.sin(math.tau/n) / 2))
            offset = Vector((-0.01 - chart * 0.001, -0.02 - chart * 0.002))
            for i, loop in enumerate(face.loops):
                angle = math.tau * i / n
                loop[uv].uv = Vector((math.cos(angle)*radius,
                                     math.sin(angle)*radius)) + offset
            for edge in face.edges:
                edge.seam = True
            chart += 1
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    if chart:
        print(f'[{PREFIX}] opened {chart} folded conduit/boolean faces at their boundaries', flush=True)


def pack_material(objects, group):
    """Pack UV charts with rigid transforms; retain native n-gon diagonals.

    Blender's triangle-based packer can distort a repaired boolean n-gon.
    These chart rectangles use one uniform transform per connected UV island.
    """
    charts = []
    for obj in objects:
        mesh = obj.data
        uv = mesh.uv_layers.active.data
        faces = {f.index: f for f in mesh.polygons if mesh.materials[f.material_index].name == group}
        parent = {i:i for i in faces}
        def root(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]];i=parent[i]
            return i
        edges = {}
        for face in faces.values():
            loops = list(face.loop_indices)
            for a,b in zip(loops,loops[1:]+loops[:1]):
                va,vb = mesh.loops[a].vertex_index,mesh.loops[b].vertex_index
                edge = tuple(sorted((va,vb)))
                points = (uv[a].uv[:],uv[b].uv[:]) if va<vb else (uv[b].uv[:],uv[a].uv[:])
                for old_face,old_points in edges.get(edge,[]):
                    if all(abs(c-d)<1e-7 for p,q in zip(points,old_points) for c,d in zip(p,q)):
                        parent[root(face.index)]=root(old_face)
                edges.setdefault(edge,[]).append((face.index,points))
        islands = {}
        for face in faces.values():islands.setdefault(root(face.index),[]).append(face)
        mesh.calc_loop_triangles()
        areas = {}
        for tri in mesh.loop_triangles:
            if tri.polygon_index not in faces:continue
            key=root(tri.polygon_index)
            a,b,c=[mesh.vertices[i].co for i in tri.vertices]
            world=(b-a).cross(c-a).length/2
            a,b,c=[uv[i].uv for i in tri.loops]
            texture=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))/2
            totals=areas.setdefault(key,[0.,0.]);totals[0]+=world;totals[1]+=texture
        for key,parts in islands.items():
            loops=[i for f in parts for i in f.loop_indices]
            points=np.array([uv[i].uv[:] for i in loops],dtype=np.float64)
            world,texture=areas.get(key,(0,0))
            factor=math.sqrt(world/texture) if texture>1e-20 and world>0 else 1.
            points=(points-points.min(axis=0))*factor
            w,h=points.max(axis=0)
            charts.append((obj,loops,points,max(w,1e-9),max(h,1e-9)))
    charts.sort(key=lambda c:max(c[3],c[4]),reverse=True)
    pad=MARGIN/2
    def layout(scale):
        free=[(0.,0.,1.,1.)];placements=[]
        for _,_,_,w,h in charts:
            best=None
            for i,(x,y,fw,fh) in enumerate(free):
                for rotated,(rw,rh) in enumerate(((w*scale+2*pad,h*scale+2*pad),
                                                (h*scale+2*pad,w*scale+2*pad))):
                    if rw<=fw and rh<=fh:
                        score=(min(fw-rw,fh-rh),max(fw-rw,fh-rh),i,rotated)
                        if best is None or score<best[0]:best=(score,rw,rh,x,y,fw,fh)
            if best is None:return None
            score,rw,rh,x,y,fw,fh=best
            free.pop(score[2]);placements.append((x+pad,y+pad,bool(score[3])))
            if fw-rw>fh-rh:
                free.extend(((x+rw,y,fw-rw,fh),(x,y+rh,rw,fh-rh)))
            else:
                free.extend(((x,y+rh,fw,fh-rh),(x+rw,y,fw-rw,rh)))
            free=[r for r in free if r[2]>2*pad and r[3]>2*pad]
        return placements
    lo,hi=0.,1./max(max(c[3],c[4]) for c in charts)
    for _ in range(25):
        mid=(lo+hi)/2
        if layout(mid) is not None:lo=mid
        else:hi=mid
    result=layout(lo)
    if result is None:raise RuntimeError(f'{group}: too many charts for the requested gutter')
    for (obj,loops,points,w,h),(x,y,rotated) in zip(charts,result):
        if rotated:points=np.column_stack((h-points[:,1],points[:,0]))
        points=points*lo+np.array((x,y))
        for i,point in zip(loops,points):obj.data.uv_layers.active.data[i].uv=point


def build_atlases(objects, slots, folder, prefix=None):
    global PREFIX
    PREFIX = prefix or folder.name
    for obj in objects:
        obj.data.calc_loop_triangles()
        mark_seams(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.context.scene.tool_settings.mesh_select_mode = (False, False, True)
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    for group in slots:
        for obj in objects:
            for vertex in obj.data.vertices:
                vertex.select = False
            for edge in obj.data.edges:
                edge.select = False
            for face in obj.data.polygons:
                face.select = obj.data.materials[face.material_index].name == group
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=MARGIN)
        flatten_panels(objects)
        repair_folded_faces(objects)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, rotate_method='CARDINAL', margin=MARGIN,
                               margin_method='FRACTION', shape_method='AABB')
        bpy.ops.object.mode_set(mode='OBJECT')
        for obj in objects:
            for face in obj.data.polygons:
                if face.select:
                    for loop in face.loop_indices:
                        coords = obj.data.uv_layers.active.data[loop].uv
                        if any(not math.isfinite(c) or c < -1e-5 or c > 1.00001 for c in coords):
                            raise RuntimeError(f'UV outside 0..1: {group}/{obj.name}/{face.index}: {coords[:]}')
        print(f'[{PREFIX}] packed unique {group} UV atlas', flush=True)
    repaired = set()
    for attempt in range(80):
        try:
            validate_layouts(objects, slots, folder)
            break
        except LayoutError as error:
            new_faces = (set(error.faces) | degenerate_layout_faces(objects)) - repaired
            if not new_faces:
                raise
            repaired.update(new_faces)
            affected = set()
            for obj in objects:
                for vertex in obj.data.vertices: vertex.select = False
                for edge in obj.data.edges: edge.select = False
                for face in obj.data.polygons:
                    face.select = (obj.name, face.index) in new_faces
                    if face.select:
                        affected.add(obj.data.materials[face.material_index].name)
            bpy.ops.object.mode_set(mode='EDIT')
            for obj in objects:
                bm = bmesh.from_edit_mesh(obj.data)
                uv = bm.loops.layers.uv.active
                for face in bm.faces:
                    if not face.select: continue
                    n = len(face.loops)
                    radius = math.sqrt(max(face.calc_area(), 1e-12) /
                                       (n*math.sin(math.tau/n)/2))
                    # Isolate the chart from its neighbours in UV space.
                    offset = Vector((-2-radius, -2-radius))
                    for i, loop in enumerate(face.loops):
                        angle = math.tau*i/n
                        loop[uv].uv = Vector((math.cos(angle)*radius,math.sin(angle)*radius))+offset
                    for edge in face.edges: edge.seam=True
                bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            for group in sorted(affected):
                pack_material(objects, group)
            print(f'[{PREFIX}] isolated {len(new_faces)} exceptional UV faces: {error}',flush=True)
    else:
        raise RuntimeError(f'{PREFIX}: UV validation did not converge')
    for group in slots:
        write_wireframe(objects, group, folder)
    for obj in objects:
        for face in obj.data.polygons:
            face.select = True


# Runtime effects consume the original analytic UV0. Their unique authoring
# layout goes in UV1, preserving screen orientation and shader coordinates.
EFFECT_MATERIALS = {"M_Portal", "M_Exhaust", "M_Screen", "M_Marquee",
                    "M_Ribbon", "M_Flag", "M_Shield", "M_CoreOuter", "M_CoreInner"}


def effect_material(material):
    if material is None:
        return False
    name = material.name
    for classifier in ('Metallic', 'Glass', 'Emissive', 'Diffuse'):
        name = name.removesuffix('_' + classifier)
    return name in EFFECT_MATERIALS


def prepare_export(objects, folder, stem):
    """Pack all rendered parts together per native material before export."""
    from pathlib import Path
    folder = Path(folder)
    meshes = [o for o in objects if o.type == 'MESH']
    if not meshes:
        return
    if folder.parent.name == 'weapons':
        from weapon_materials import restore
        restore(objects, folder)
    if _preserve_uvs:
        from material_classes import apply
        apply(objects, folder)
        return
    if all(o.get('material_uv_atlas') == stem for o in meshes):
        from material_classes import apply
        apply(objects, folder)
        return
    saved = {}
    visibility = {o.name:(o.hide_get(),o.hide_viewport,o.hide_select) for o in meshes}
    for obj in meshes:
        obj.hide_set(False);obj.hide_viewport=False;obj.hide_select=False
        effects = any(effect_material(m) for m in obj.data.materials)
        if effects and obj.data.uv_layers.active:
            original = obj.data.uv_layers.active
            atlas = obj.data.uv_layers.get('MaterialAtlas') or obj.data.uv_layers.new(name='MaterialAtlas')
            obj.data.uv_layers.active = atlas
            saved[obj.name] = original.name
        elif not obj.data.uv_layers.active:
            obj.data.uv_layers.new(name='UVMap')
    slots = sorted({obj.data.materials[f.material_index].name
                    for obj in meshes for f in obj.data.polygons})
    build_atlases(meshes, slots, folder, stem)
    for obj in meshes:
        obj['material_uv_atlas'] = stem
        if obj.name in saved:
            obj.data.uv_layers.active = obj.data.uv_layers[saved[obj.name]]
            obj.data.uv_layers.active.active_render = True
        hidden, viewport, locked = visibility[obj.name]
        obj.hide_set(hidden);obj.hide_viewport=viewport;obj.hide_select=locked
    print(f'[{stem}] verified {len(slots)} native material atlases at {SIZE}px', flush=True)
    from material_classes import apply
    apply(objects, folder)


def refresh_asset(folder, classify_only=False, materials_only=False):
    """UV-only regeneration of an existing validated procedural build.

    Runs the same native exporter after proving geometry, skinning, materials,
    analytic effect UV0 and rig contents were not changed by UV preparation.
    Full source builds use prepare_export too; no cache is needed to rebuild.
    """
    import hashlib, json, runpy, struct, tempfile
    from pathlib import Path
    folder = Path(folder)
    name = folder.name
    scratch = Path(tempfile.gettempdir()) / ('kylr-weapon-finishes' if materials_only else 'kylr-material-classes' if classify_only else 'kylr-material-uv') / name
    scratch.mkdir(parents=True, exist_ok=True)
    files = [(name,folder / (name + '.blend'))]
    files += [(p.stem,p) for suffix in ('ammo', 'rocket', 'grenade', 'shield')
              if (p := folder / f'{name}_{suffix}.blend').exists()]
    embedded_rocket = folder / (name + '_rocket.glb')
    if embedded_rocket.exists() and not (folder/(name+'_rocket.blend')).exists():
        files.append((name+'_rocket',folder/(name+'.blend')))
    if classify_only:
        files = []
        for delivery in sorted(folder.glob('*.glb')):
            if '_col' in delivery.stem:
                continue
            blend = delivery.with_suffix('.blend')
            if not blend.exists():
                blend = folder / (name + '.blend')
            if blend.exists():
                files.append((delivery.stem, blend))
    report = []
    global _preserve_uvs
    _preserve_uvs = materials_only
    source = None
    if not classify_only and name not in {'skyfall', 'energy_core', 'shield_core'}:
        source = runpy.run_path(str(folder / 'model.py'), run_name='_uv_source')
    def gltf(path):
        with path.open('rb') as stream:
            stream.read(12)
            length, kind = struct.unpack('<II', stream.read(8))
            return json.loads(stream.read(length))
    def contract(data):
        return {
            'triangles': sum(data['accessors'][p.get('indices', p['attributes']['POSITION'])]['count']//3
                             for mesh in data.get('meshes', []) for p in mesh['primitives']),
            'meshes': sorted(m['name'] for m in data.get('meshes', [])),
            'materials': sorted(m['name'] for m in data.get('materials', [])),
            'animations': sorted(a['name'] for a in data.get('animations', [])),
            'joints': sorted(data['nodes'][i]['name'] for skin in data.get('skins', []) for i in skin['joints']),
        }
    def geometry(objects):
        return {o.name: {
            'vertices': [v.co[:] for v in o.data.vertices],
            'faces': [(p.vertices[:], p.material_index, p.use_smooth) for p in o.data.polygons],
            'weights': [[(o.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in o.data.vertices],
            'normals': [n.vector[:] for n in o.data.corner_normals],
            **({'uvs': {uv.name: [d.uv[:] for d in uv.data] for uv in o.data.uv_layers}} if materials_only else {}),
        } for o in objects if o.type == 'MESH'}
    for stem, blend in files:
        embedded = stem != blend.stem
        path = folder / (stem + '.glb')
        original = scratch / (stem + '.glb')
        if classify_only or not original.exists(): original.write_bytes(path.read_bytes())
        previous = gltf(original)
        baseline = contract(previous)
        if materials_only:
            from weapon_materials import delivery_name
            baseline['materials'] = sorted(delivery_name(value, folder) for value in baseline['materials'])
        if classify_only:
            from material_classes import classified_name, policy
            choices = policy(folder)
            baseline['materials'] = sorted(classified_name(value, choices) for value in baseline['materials'])
        if stem.endswith(('_ammo', '_rocket', '_grenade')) and not embedded:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            with bpy.data.libraries.load(str(blend), link=False) as (library, loaded):
                loaded.objects = library.objects
            for obj in loaded.objects:
                if obj: bpy.context.scene.collection.objects.link(obj)
        else:
            bpy.ops.wm.open_mainfile(filepath=str(blend))
        names = {n.get('name') for n in previous['nodes']}
        objects = [o for o in bpy.context.scene.objects if o.name in names]
        # Exporter armature nodes can be elided; include the mesh's actual rig.
        for mesh in list(objects):
            if mesh.type == 'MESH':
                for mod in mesh.modifiers:
                    if mod.type == 'ARMATURE' and mod.object not in objects:
                        objects.insert(0, mod.object)
        meshes = [o for o in objects if o.type == 'MESH']
        if not meshes:
            if classify_only and baseline['triangles'] == 0:
                print(f'[{stem}] placement-only delivery: no materials to rename', flush=True)
                continue
            if classify_only and all(value.endswith(('_Metallic','_Glass','_Emissive','_Diffuse')) for value in baseline['materials']):
                print(f'[{stem}] native standalone export already classified; validate with its source map validator', flush=True)
                continue
            raise RuntimeError(f'No export meshes found for {stem}')
        before = geometry(meshes)
        effects = {o.name: [d.uv[:] for d in o.data.uv_layers.active.data]
                   for o in meshes if o.data.uv_layers.active and
                   any(effect_material(m) for m in o.data.materials)}
        if materials_only:
            from weapon_materials import restore
            restore(objects, folder)
        elif classify_only:
            from material_classes import apply
            apply(objects, folder)
        else:
            for o in meshes:
                if 'material_uv_atlas' in o: del o['material_uv_atlas']
            prepare_export(objects, folder, stem)
        assert before == geometry(meshes), f'{stem}: geometry, normals or skin weights changed'
        for obj_name, coords in effects.items():
            assert coords == [d.uv[:] for d in bpy.data.objects[obj_name].data.uv_layers.active.data]
        bpy.context.preferences.filepaths.save_version = 0
        # Save the inspectable rig before its exporter temporarily removes limits.
        if stem.endswith(('_ammo', '_rocket', '_grenade')) and not embedded:
            staged = blend.with_name(stem + '_uv_staged.blend')
            bpy.data.libraries.write(str(staged), set(objects), fake_user=True, compress=True)
            staged.replace(blend)
        else:
            bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
        for obj in objects:
            obj.hide_set(False);obj.hide_viewport=False;obj.hide_select=False
        if embedded:
            for rig in objects:
                if rig.type=='ARMATURE':rig.location=(0,0,0)
            for action in list(bpy.data.actions):
                if action.name not in baseline['animations']:
                    bpy.data.actions.remove(action,do_unlink=True)
        if classify_only:
            allowed = set(baseline['animations'])
            for action in list(bpy.data.actions):
                if action.name not in allowed:
                    bpy.data.actions.remove(action, do_unlink=True)
        if source and stem == name and name != 'pillar':
            exporter = source.get('export') or getattr(source.get('k'), 'export', None)
            assert exporter is not None, (name, 'Missing native exporter')
            exporter(objects, stem)
        elif source and name == 'pillar':
            source['export'](next(o for o in objects if o.type=='ARMATURE'), meshes[0])
        else:
            for o in objects:
                if o.type == 'ARMATURE':
                    for bone in o.pose.bones:
                        for c in list(bone.constraints): bone.constraints.remove(c)
                    for driver in list(o.animation_data.drivers if o.animation_data else []):
                        o.animation_data.drivers.remove(driver)
            bpy.ops.object.select_all(action='DESELECT')
            for o in objects: o.select_set(True)
            bpy.context.view_layer.objects.active = next((o for o in objects if o.type=='ARMATURE'),meshes[0])
            static = not any(o.type=='ARMATURE' for o in objects)
            bpy.ops.export_scene.fbx(filepath=str(folder/(stem+'.fbx')),use_selection=True,
                global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',
                axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,mesh_smooth_type='OFF',
                add_leaf_bones=False,use_armature_deform_only=True,bake_anim=not static,
                bake_anim_use_all_actions=True,bake_anim_force_startend_keying=True,
                bake_anim_simplify_factor=0,
                path_mode='COPY',embed_textures=True)
            settings = dict(filepath=str(path),export_format='GLB',use_selection=True,
                            export_animations=not static, export_materials='EXPORT')
            if name in {'skyfall'}:
                settings.update(export_extras=True,export_apply=True)
            else:
                settings.update(export_apply=False,export_skins=not static,export_def_bones=True,
                                export_animation_mode='ACTIONS',export_anim_single_armature=True,
                                export_reset_pose_bones=True,export_force_sampling=True)
            bpy.ops.export_scene.gltf(**settings)
        current = contract(gltf(path))
        assert baseline == current, (stem, 'Export contract changed', baseline, current)
        expected = sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if ext == 'glb': bpy.ops.import_scene.gltf(filepath=str(path))
            else: bpy.ops.import_scene.fbx(filepath=str(folder/(stem+'.fbx')))
            imported = [o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in before]
            count = 0
            for o in imported:
                o.data.calc_loop_triangles(); count += len(o.data.loop_triangles)
                assert o.data.uv_layers, (stem, ext, o.name, 'missing UVs')
                for uv in o.data.uv_layers:
                    assert all(math.isfinite(c) for d in uv.data for c in d.uv)
            target = baseline['triangles'] if ext == 'glb' else expected
            assert count == target, (stem, ext, count, target)
            print(f'[{stem}] {ext.upper()} round-trip passed: {count} triangles', flush=True)
        report.append(dict(stem=stem,**current,verified_geometry=True,verified_effect_uv0=True,
                           roundtrips=['glb','fbx'],resolution=SIZE))
    (scratch/'report.json').write_text(json.dumps(report,indent=2))
    _preserve_uvs = False
    print(f'[{name}] UV refresh and all delivery checks passed', flush=True)
