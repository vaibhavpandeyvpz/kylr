class_name DamageIndicator
extends Control

const LIFE := 1.3
const HOLD := 0.55
const EDGE_INSET := 10.0
const MERGE_ANGLE := 0.35
const MAX_HITS := 6
const DANGER := Color("ff7275")

var viewer: Node3D
var camera: Camera3D
var hits: Array[Dictionary] = []
var reduced_motion := false

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_process(false)

func mark(source: Vector3, damage: float) -> void:
	if viewer == null or damage <= 0.0: return
	var direction := source - viewer.global_position
	direction.y = 0.0
	if direction.length_squared() < 0.0001: return
	direction = direction.normalized()
	for hit in hits:
		if hit.direction.angle_to(direction) < MERGE_ANGLE:
			hit.direction = direction
			hit.strength = maxf(hit.strength, minf(damage / 45.0, 1.0))
			hit.age = 0.0
			set_process(true)
			queue_redraw()
			return
	if hits.size() == MAX_HITS: hits.pop_front()
	hits.append({"direction":direction,"strength":minf(damage / 45.0, 1.0),"age":0.0})
	set_process(true)
	queue_redraw()

func clear() -> void:
	hits.clear()
	set_process(false)
	queue_redraw()

func _process(dt: float) -> void:
	for index in range(hits.size() - 1, -1, -1):
		hits[index].age += dt
		if hits[index].age >= LIFE: hits.remove_at(index)
	if hits.is_empty(): set_process(false)
	queue_redraw()

func _draw() -> void:
	if camera == null or hits.is_empty(): return
	var width := size.x - EDGE_INSET * 2.0
	var height := size.y - EDGE_INSET * 2.0
	if width <= 0.0 or height <= 0.0: return
	var pulse := 0.0
	for hit in hits:
		pulse = maxf(pulse, clampf(1.0 - hit.age / 0.38, 0.0, 1.0) * lerpf(0.25, 0.48, hit.strength))
	if pulse > 0.0:
		var depth := minf(size.y * 0.16, 110.0)
		var edge_color := Color(DANGER.r, DANGER.g * 0.3, DANGER.b * 0.3, pulse * (0.5 if reduced_motion else 1.0))
		var clear_color := Color(edge_color.r, edge_color.g, edge_color.b, 0.0)
		for band in [
			PackedVector2Array([Vector2.ZERO, Vector2(size.x,0), Vector2(size.x,depth), Vector2(0,depth)]),
			PackedVector2Array([Vector2(0,size.y), size, Vector2(size.x,size.y-depth), Vector2(0,size.y-depth)]),
			PackedVector2Array([Vector2.ZERO, Vector2(0,size.y), Vector2(depth,size.y), Vector2(depth,0)]),
			PackedVector2Array([Vector2(size.x,0), size, Vector2(size.x-depth,size.y), Vector2(size.x-depth,0)])]:
			draw_polygon(band, PackedColorArray([edge_color,edge_color,clear_color,clear_color]))
	for hit in hits:
		var direction: Vector3 = hit.direction
		var angle := relative_angle(direction)
		var length := lerpf(128.0, 260.0, hit.strength)
		var center := _border_distance(angle, width, height)
		var path := _edge_path(center - length * 0.5, length, width, height)
		var alpha: float = 1.0 if hit.age <= HOLD else pow((LIFE - hit.age) / (LIFE - HOLD), 2.0)
		draw_polyline(path, Color(DANGER.r,DANGER.g,DANGER.b,alpha * 0.22), 28.0, true)
		draw_polyline(path, Color(0.0,0.0,0.0,alpha * 0.75), 11.0, true)
		draw_polyline(path, Color(DANGER.r,DANGER.g,DANGER.b,alpha), 7.0, true)
		# Repeat the bearing near the sightline, where the player is looking.
		var start := angle - PI * 0.5 - 0.30
		draw_arc(size * 0.5, 54.0, start, start + 0.60, 16, Color(0,0,0,alpha * 0.8), 8.0, true)
		draw_arc(size * 0.5, 54.0, start, start + 0.60, 16, Color(DANGER.r,DANGER.g,DANGER.b,alpha), 4.0, true)

func relative_angle(direction: Vector3) -> float:
	var forward := camera.global_basis * Vector3.FORWARD
	forward.y = 0.0
	if forward.length_squared() < 0.0001: return 0.0
	forward = forward.normalized()
	return wrapf(atan2(direction.x, -direction.z) - atan2(forward.x, -forward.z), -PI, PI)

func _border_distance(angle: float, width: float, height: float) -> float:
	var ray := Vector2(sin(angle), -cos(angle))
	var reach_x := INF if absf(ray.x) < 0.00001 else width * 0.5 / absf(ray.x)
	var reach_y := INF if absf(ray.y) < 0.00001 else height * 0.5 / absf(ray.y)
	if reach_y <= reach_x:
		var x := width * 0.5 + ray.x * reach_y
		return x if ray.y < 0.0 else width * 2.0 + height - x
	var y := height * 0.5 + ray.y * reach_x
	return width + y if ray.x > 0.0 else width * 2.0 + height * 2.0 - y

func _edge_point(distance: float, width: float, height: float) -> Vector2:
	var phase := fposmod(distance, (width + height) * 2.0)
	if phase < width: return Vector2(EDGE_INSET + phase,EDGE_INSET)
	phase -= width
	if phase < height: return Vector2(EDGE_INSET + width,EDGE_INSET + phase)
	phase -= height
	if phase < width: return Vector2(EDGE_INSET + width - phase,EDGE_INSET + height)
	return Vector2(EDGE_INSET,EDGE_INSET + height - (phase - width))

func _edge_path(start: float, length: float, width: float, height: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	var steps := maxi(2,ceili(length / 6.0))
	for step in steps + 1:
		points.append(_edge_point(start + length * float(step) / float(steps),width,height))
	return points
