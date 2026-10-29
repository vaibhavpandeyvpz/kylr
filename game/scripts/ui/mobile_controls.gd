extends Control

# Touches are tracked independently so movement, aiming and firing can overlap.
var fingers := {}
var movement := Vector2.ZERO
var aim := Vector2.ZERO
var icons: Dictionary = {}
var profile_elapsed := 0.0
var app
const BUTTONS := [
	["PAUSE", "pause", Vector2(-60, 52)],
	["VIEW", "view", Vector2(-148, 52)],
	["JUMP", "jump", Vector2(-300, 465)],
	["CHARGE", "charged_jump", Vector2(-400, 465)],
	["FIRE", "fire", Vector2(-85, 300)],
	["ALT", "secondary", Vector2(-205, 300)],
	["CROUCH", "crouch", Vector2(280, 465)],
]

func button_center(button: Array) -> Vector2:
	var point: Vector2 = button[2]
	var unit := size.y / 720.0
	if button[1] in ["pistol", "pickup"]:
		return Vector2(size.x * 0.5 + point.x * unit, size.y + point.y * unit)
	return Vector2(size.x + point.x * unit if point.x < 0 else point.x * unit, point.y * unit)

func button_radius(action: String) -> float:
	return size.y / 720.0 * (40.0 if action == "fire" else 29.0)

func stick_center() -> Vector2:
	return Vector2(size.y * 0.18, size.y * 0.65)

func aim_center() -> Vector2:
	return Vector2(size.x - size.y * 0.18, size.y * 0.65)

static func stick_value(point: Vector2, center: Vector2, radius: float) -> Vector2:
	var value := ((point - center) / maxf(1.0, radius)).limit_length()
	return Vector2.ZERO if value.length() < 0.12 else value

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	process_mode = Node.PROCESS_MODE_ALWAYS
	for button in BUTTONS:
		icons[button[1]] = load("res://assets/ui/icons/touch/%s.svg" % button[1])

func _process(delta: float) -> void:
	queue_redraw()
	if not app or not app.ui or app.ui.screen != "match" or not is_visible_in_tree():
		if not fingers.is_empty(): release_all()
		return
	if app.match_node and app.match_node.local_robot and not app.match_node.local_robot.spawn_look_locked():
		var robot = app.match_node.local_robot
		var rate: float = app.prefs.values.sensitivity / 0.0022 * 2.4
		robot.yaw -= aim.x * rate * delta
		robot.pitch = clampf(robot.pitch - aim.y * rate * delta * (-1 if app.prefs.values.invert else 1), -PI / 4, PI / 4)
	if OS.has_feature("debug"):
		profile_elapsed += delta
		if profile_elapsed >= 5.0:
			profile_elapsed = 0.0
			print("MOBILE_PROFILE fps=", Engine.get_frames_per_second(), " process_ms=", Performance.get_monitor(Performance.TIME_PROCESS)*1000.0, " physics_ms=", Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0, " draws=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))

func _input(event: InputEvent) -> void:
	if not app or not app.ui or app.ui.screen != "match" or not is_visible_in_tree(): return
	if event is InputEventScreenTouch:
		if event.pressed:
			var pos: Vector2 = get_global_transform().affine_inverse() * event.position
			if weapon_touch(event.position): return
			var action := button_at(pos)
			if Rect2(Vector2(size.x * 0.38, 0), Vector2(size.x * 0.24, size.y * 0.14)).has_point(pos): action = "scoreboard"
			if action == "pause":
				app.ui.pause_menu()
			elif not action.is_empty():
				fingers[event.index] = {"kind":"button", "action":action}
				set_action(action, true)
			elif pos.distance_to(aim_center()) <= size.y * 0.13 and not has_kind("aim"):
				fingers[event.index] = {"kind":"aim"}
				aim = stick_value(pos, aim_center(), size.y * 0.10)
			elif pos.x < size.x * 0.38 and pos.y > size.y * 0.4 and not has_kind("move"):
				fingers[event.index] = {"kind":"move", "origin":stick_center()}
			elif not has_kind("look"):
				fingers[event.index] = {"kind":"look"}
		else:
			release_finger(event.index)
		queue_redraw()
	elif event is InputEventScreenDrag and fingers.has(event.index):
		var finger: Dictionary = fingers[event.index]
		if finger.kind == "aim":
			var pos: Vector2 = get_global_transform().affine_inverse() * event.position
			aim = stick_value(pos, aim_center(), size.y * 0.10)
		elif finger.kind == "move":
			var pos: Vector2 = get_global_transform().affine_inverse() * event.position
			movement = ((pos - finger.origin) / maxf(1.0, size.y * 0.10)).limit_length()
			set_action("walk", movement.length() > 0.12 and movement.length() < 0.45)
			set_action("sprint", movement.length() >= 0.95)
			if movement.length() < 0.12: movement = Vector2.ZERO
			queue_redraw()
		elif (finger.kind == "look" or (finger.kind == "button" and finger.action in ["fire", "secondary"])) and app.match_node and app.match_node.local_robot:
			var robot = app.match_node.local_robot
			if not robot.spawn_look_locked():
				robot.yaw -= event.relative.x * app.prefs.values.sensitivity
				robot.pitch = clampf(robot.pitch - event.relative.y * app.prefs.values.sensitivity * (-1 if app.prefs.values.invert else 1), -PI / 4, PI / 4)

func has_kind(kind: String) -> bool:
	for finger in fingers.values():
		if finger.kind == kind: return true
	return false

func button_at(pos: Vector2) -> String:
	for button in BUTTONS:
		if pos.distance_to(button_center(button)) <= button_radius(button[1]) * 1.15: return button[1]
	return ""

func weapon_touch(viewport_pos: Vector2) -> bool:
	var tray = app.ui.weapon
	if not is_instance_valid(tray) or not is_instance_valid(tray.robot): return false
	var point: Vector2 = tray.get_global_transform().affine_inverse() * viewport_pos
	var rects: Array[Rect2] = WeaponReadout.slot_rects(tray.robot.owned_weapons.size(), tray.size, tray.screen_width)
	for index in rects.size():
		if not rects[index].has_point(point): continue
		if index == tray.robot.owned_weapons.find(tray.robot.equipped):
			set_action("reload", true)
			set_action("reload", false)
		else:
			var event := InputEventAction.new()
			event.action = "mobile_slot:%d" % index
			event.pressed = true
			Input.parse_input_event(event)
		return true
	return false

func set_action(action: String, pressed: bool) -> void:
	if not InputMap.has_action(action): return
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	event.strength = 1.0 if pressed else 0.0
	Input.parse_input_event(event)

func release_finger(index: int) -> void:
	if not fingers.has(index): return
	var finger: Dictionary = fingers[index]
	fingers.erase(index)
	if finger.kind == "aim": aim = Vector2.ZERO
	if finger.kind == "move":
		movement = Vector2.ZERO
		set_action("walk", false)
		set_action("sprint", false)
	if finger.kind == "button":
		for other in fingers.values():
			if other.kind == "button" and other.action == finger.action: return
		set_action(finger.action, false)

func release_all() -> void:
	for index in fingers.keys(): release_finger(index)
	queue_redraw()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT: release_all()

func _draw() -> void:
	for pair in [[stick_center(), movement], [aim_center(), aim]]:
		var stick: Vector2 = pair[0]
		var value: Vector2 = pair[1]
		draw_circle(stick, size.y * 0.10, Color(1, 1, 1, 0.10))
		draw_arc(stick, size.y * 0.10, 0, TAU, 48, Color(1, 1, 1, 0.25), 1.5)
		draw_circle(stick + value * size.y * 0.065, size.y * 0.035, Color(1, 1, 1, 0.10))
		draw_arc(stick + value * size.y * 0.065, size.y * 0.035, 0, TAU, 32, Color(1, 1, 1, 0.25), 1.5)
	for button in BUTTONS:
		var center := button_center(button)
		var radius := button_radius(button[1])
		var pressed := Input.is_action_pressed(button[1]) if InputMap.has_action(button[1]) else false
		draw_circle(center, radius, Color(1, 1, 1, 0.20 if pressed else 0.10))
		draw_arc(center, radius, 0, TAU, 32, Color(1, 1, 1, 0.5 if pressed else 0.25), 1.5)
		if icons.has(button[1]) and icons[button[1]]:
			draw_texture_rect(icons[button[1]], Rect2(center - Vector2.ONE * radius * 0.55, Vector2.ONE * radius * 1.1), false, Color(1, 1, 1, 0.5))
