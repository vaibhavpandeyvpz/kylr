class_name RepairWelding
extends Node
## Presentation only: the match's seven-second repair remains authoritative.
var game
var fixture: Dictionary
var tip: Node3D
var glow: MeshInstance3D
var light: OmniLight3D
var windows: Array = []
var fps := 30.0
var pulse_remaining := 0.0
var welding := false

func install(controller, station: Dictionary) -> void:
	game = controller
	fixture = station
	station.node.add_child(self)
	tip = Assets.socket(station.node,"TorchTip")
	assert(tip != null,"Repair welding requires the exported TorchTip")
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/gameplay/repair_station/repair_station_rig.json"))
	windows = data.effects.TorchTip.welding_frames
	fps = data.animations.repair.fps
	glow = MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.018
	sphere.height = 0.036
	sphere.radial_segments = 8
	sphere.rings = 4
	glow.mesh = sphere
	glow.material_override = Assets.material(Color("bdefff"),8.0)
	glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	tip.add_child(glow)
	glow.hide()
	light = OmniLight3D.new()
	light.light_color = Color("9bdfff")
	light.omni_range = 0.55
	light.shadow_enabled = false
	tip.add_child(light)
	light.hide()

func is_welding() -> bool:
	if game.phase != "Active" or game.map.shutting_down or not is_instance_valid(fixture.occupant) or not fixture.occupant.alive: return false
	if fixture.elapsed < 1.0 or fixture.elapsed >= 6.0: return false
	var frame: float = (fixture.elapsed-1.0)*fps
	for window in windows:
		if frame >= window[0] and frame <= window[1]: return true
	return false

func stop() -> void:
	welding = false
	pulse_remaining = 0.0
	glow.hide()
	light.hide()

func _process(dt: float) -> void:
	welding = is_welding()
	var distance := tip.global_position.distance_to(game.camera.global_position) if game.camera != null else 0.0
	glow.visible = welding
	light.visible = welding and distance < 15.0
	if not welding:
		pulse_remaining = 0.0
		return
	var reduced: bool = game.reduced_motion
	var flicker := 1.0 if reduced else 0.8 + 0.2*sin(fixture.elapsed*TAU*13.0)
	glow.scale = Vector3.ONE*flicker
	light.light_energy = 0.5*flicker
	if reduced or distance >= 60.0: return
	pulse_remaining -= dt
	if pulse_remaining > 0.0: return
	pulse_remaining = 0.16 if distance < 25.0 else 0.5
	var flash := game.effects.sprite(tip.global_position,Color("bdefff"),0.085,0.12,4.0) as CombatTransient
	if flash:
		flash.anchor = weakref(tip)
		flash.anchor_offset = Transform3D(Basis.from_scale(Vector3.ONE*0.085),Vector3.ZERO)
	# Back away from the metal toward the torch, using the exported tool frame.
	game.effects.sparks(tip.global_position,tip.global_basis.z.normalized())
