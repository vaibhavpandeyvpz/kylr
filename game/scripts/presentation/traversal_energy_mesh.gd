class_name TraversalEnergyMesh
extends RefCounted
## Closed render-only outlines, extruded along the fixture's local normal.
const DEPTH := 0.02

static func square_ring() -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var outer := PackedVector2Array([Vector2(-0.44,-0.44),Vector2(0.44,-0.44),Vector2(0.44,0.44),Vector2(-0.44,0.44)])
	var inner := PackedVector2Array([Vector2(-0.41,-0.41),Vector2(0.41,-0.41),Vector2(0.41,0.41),Vector2(-0.41,0.41)])
	for i in 4:
		var j := (i+1)%4
		quad(surface, point(outer[i],DEPTH/2),point(outer[j],DEPTH/2),point(inner[j],DEPTH/2),point(inner[i],DEPTH/2))
		quad(surface, point(inner[i],-DEPTH/2),point(inner[j],-DEPTH/2),point(outer[j],-DEPTH/2),point(outer[i],-DEPTH/2))
		quad(surface, point(outer[i],-DEPTH/2),point(outer[j],-DEPTH/2),point(outer[j],DEPTH/2),point(outer[i],DEPTH/2))
		quad(surface, point(inner[j],-DEPTH/2),point(inner[i],-DEPTH/2),point(inner[i],DEPTH/2),point(inner[j],DEPTH/2))
	return surface.commit()

static func chevron() -> ArrayMesh:
	# One continuous V with a +Z apex; no intersecting bars at the tip.
	var outline := PackedVector2Array([Vector2(-0.42,-0.15),Vector2(0,0.08),Vector2(0.42,-0.15),Vector2(0.42,-0.08),Vector2(0,0.15),Vector2(-0.42,-0.08)])
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var indices := Geometry2D.triangulate_polygon(outline)
	for i in range(0,indices.size(),3):
		var a := outline[indices[i]]
		var b := outline[indices[i+1]]
		var c := outline[indices[i+2]]
		triangle(surface,point(a,DEPTH/2),point(b,DEPTH/2),point(c,DEPTH/2))
		triangle(surface,point(c,-DEPTH/2),point(b,-DEPTH/2),point(a,-DEPTH/2))
	for i in outline.size():
		var j := (i+1)%outline.size()
		quad(surface,point(outline[i],-DEPTH/2),point(outline[j],-DEPTH/2),point(outline[j],DEPTH/2),point(outline[i],DEPTH/2))
	return surface.commit()

static func point(p: Vector2,height: float) -> Vector3:
	return Vector3(p.x,height,p.y)

static func triangle(surface: SurfaceTool,a: Vector3,b: Vector3,c: Vector3) -> void:
	var normal := (b-a).cross(c-a).normalized()
	for vertex in [a,b,c]:
		surface.set_normal(normal)
		surface.add_vertex(vertex)

static func quad(surface: SurfaceTool,a: Vector3,b: Vector3,c: Vector3,d: Vector3) -> void:
	triangle(surface,a,b,c)
	triangle(surface,a,c,d)
