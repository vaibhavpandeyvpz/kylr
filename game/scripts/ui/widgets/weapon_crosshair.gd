class_name WeaponCrosshair
extends Control

var profile: Dictionary = {}
var target_valid := false
var confirmed_hit := false
var contraction := 0.0
var lock_progress := -1.0

func _ready():
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func configure(weapon: String, secondary: bool):
	var data: Dictionary = Arsenal.WEAPONS[weapon]
	profile = data.get("scope_crosshair", data.get("secondary_crosshair",data.crosshair)) if secondary else data.crosshair

func _process(dt: float):
	contraction = lerpf(contraction, 1.0 if target_valid else 0.0, 1.0 - exp(-18.0 * dt))
	queue_redraw()

func stroke(points: PackedVector2Array, width: float):
	var centered := PackedVector2Array()
	for point in points: centered.append(size * 0.5 + point * lerpf(1.0, 0.7, contraction))
	draw_polyline(centered, Color(0, 0, 0, 0.7), width + 1.5, true)
	draw_polyline(centered, Color.WHITE, width, true)

func ring(radius: float, start: float, end: float, width: float):
	var points := PackedVector2Array()
	for i in 33: points.append(Vector2.from_angle(lerpf(start, end, i / 32.0)) * radius)
	stroke(points, width)

func _draw():
	if profile.is_empty(): return
	var style: String = profile.style
	var radius: float = profile.get("radius", 14.0)
	var width: float = profile.get("width", 2.0)
	match style:
		"circle":
			ring(radius,0,TAU,width)
		"flak":
			for i in 4:
				ring(radius,i*PI/2+0.12,(i+1)*PI/2-0.12,width)
				var direction:=Vector2.from_angle(PI/4+i*PI/2)
				stroke(PackedVector2Array([direction*radius*0.6,direction*radius*0.8]),width)
		"bio":
			for i in 3: ring(radius,i*TAU/3+0.22,(i+1)*TAU/3-0.22,width)
		"grenade":
			ring(radius,PI,TAU,width)
			stroke(PackedVector2Array([Vector2(-radius,0),Vector2(-radius*.55,0)]),width)
			stroke(PackedVector2Array([Vector2(radius*.55,0),Vector2(radius,0)]),width)
			for step in [0.5,1.0]:
				stroke(PackedVector2Array([Vector2(-radius*.22,radius*step),Vector2(radius*.22,radius*step)]),width)
		"orb":
			ring(radius*0.7,0,TAU,width)
			for direction in [Vector2.LEFT,Vector2.RIGHT]:
				stroke(PackedVector2Array([direction*radius, direction*radius*1.2]),width)
		"cross", "diagonal":
			for i in 4:
				var direction := Vector2.from_angle(i * PI / 2 + (PI / 4 if style == "diagonal" else 0.0))
				stroke(PackedVector2Array([direction * radius * 0.56, direction * radius]), width)
		"brackets":
			for x in [-1, 1]:
				for y in [-1, 1]:
					stroke(PackedVector2Array([Vector2(x * radius, y * radius * 0.6), Vector2(x * radius, y * radius), Vector2(x * radius * 0.6, y * radius)]), width)
		"scope":
			ring(radius, 0, TAU, width)
			for i in 4:
				var direction := Vector2.from_angle(i * PI / 2)
				stroke(PackedVector2Array([direction * radius * 0.68, direction * radius * 1.32]), width)
		"broken_ring":
			for i in 4: ring(radius, i * PI / 2 + 0.3, (i + 1) * PI / 2 - 0.3, width)
		"octagon":
			var points := PackedVector2Array()
			for point in [Vector2(-0.12,-1), Vector2(0.12,-1), Vector2(1,-0.12), Vector2(1,0.12), Vector2(0.12,1), Vector2(-0.12,1), Vector2(-1,0.12), Vector2(-1,-0.12), Vector2(-0.12,-1)]:
				points.append(point * radius * 0.62)
			stroke(points, width)
			for i in 4:
				var direction := Vector2.from_angle(i * PI / 2)
				stroke(PackedVector2Array([direction * radius * 0.85, direction * radius * 1.25]), width)
		"chevrons":
			for i in 4:
				var angle := i * PI / 2
				stroke(PackedVector2Array([Vector2(radius * 0.72, -radius * 0.27).rotated(angle), Vector2(radius, 0).rotated(angle), Vector2(radius * 0.72, radius * 0.27).rotated(angle)]), width)
	if style in ["scope", "broken_ring", "octagon", "bio", "grenade", "orb"]:
		draw_circle(size * 0.5, 2.1, Color(0, 0, 0, 0.7))
		draw_circle(size * 0.5, 1.4, Color.WHITE)
	if confirmed_hit:
		for i in 4:
			var direction := Vector2.from_angle(PI / 4 + i * PI / 2)
			var from := size * 0.5 + direction * 8
			var to := size * 0.5 + direction * 16
			draw_line(from, to, Color(0.015, 0.06, 0.08, 0.95), 6, true)
			draw_line(from, to, Color("a5ffff"), 3, true)
	if lock_progress >= 0.0:
		var lock_color := Color("8fffc1") if lock_progress >= 1.0 else Color("ffd17a")
		draw_arc(size * 0.5, 27.0, -PI / 2, -PI / 2 + TAU * maxf(0.005, lock_progress), 48, lock_color, 2.0, true)
		var text := "LOCKED" if lock_progress >= 1.0 else "ACQUIRING" if lock_progress > 0.0 else "SEEK"
		var font := ThemeDB.fallback_font
		draw_string(font, size * 0.5 + Vector2(-font.get_string_size(text,HORIZONTAL_ALIGNMENT_LEFT,-1,12).x/2,45), text,HORIZONTAL_ALIGNMENT_LEFT,-1,12,lock_color)
