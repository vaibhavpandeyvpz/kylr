class_name JumbotronMotion
extends Node

var game
var motion: PropMotion
var started := false
var shutting_down := false

func install(root: Node3D, controller) -> void:
	game = controller
	root.add_child(self)
	motion = PropMotion.new()
	motion.install(root, true)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/environments/jumbotron/jumbotron_rig.json"))
	for spot in data.spots:
		var mount := Assets.socket(root, spot.gizmo)
		assert(mount != null, "Missing jumbotron beam gizmo: " + spot.gizmo)
		FixtureLighting.spot(mount,"jumbotron",spot)

func start() -> void:
	if started: return
	started = true
	motion.play("spin_up", false, "hover", true, "rotors")
	motion.play("lights_on", false, "flood", false, "spots")

func shutdown() -> float:
	if shutting_down: return 0.0
	shutting_down = true
	if not started: return 0.0
	var rotors: Dictionary = motion.channels.rotors
	var remaining: float = rotors.player.get_animation(rotors.clip).length - rotors.time if not rotors.done and not (rotors.loop and motion.reduced_motion) else 0.0
	motion.at_boundary("spin_down", "rotors")
	motion.play("lights_off", false, "", false, "spots")
	return remaining + motion.channels.rotors.player.get_animation("spin_down").length

func _process(_dt: float) -> void:
	if not started: return
	var reduced: bool = game.reduced_motion
	var distance := 0.0
	if game.camera: distance = game.camera.global_position.distance_to(motion.asset.global_position)
	motion.set_budget(reduced, distance)
	var spots: Dictionary = motion.channels.spots
	if not shutting_down and spots.clip != "lights_on":
		if spots.clip != "flood": motion.play("flood", false, "", false, "spots")
