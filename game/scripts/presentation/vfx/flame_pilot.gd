class_name FlamePilot
extends Node3D

var plume: NozzleExhaust

func _ready():
	plume = NozzleExhaust.new()
	plume.radius_m = 0.009
	plume.emission = 0.35
	add_child(plume)
	# The pilot is a bounded continuous thermal mesh, without travelling sparks.

func update_target(target: Node3D):
	var direction := target.global_position - global_position
	if direction.length_squared() < 0.0001:
		plume.hide()
		return
	plume.show()
	plume.length_m = direction.length() * 0.9
	plume.global_basis = Basis.looking_at(direction.normalized(), Vector3.RIGHT if absf(direction.normalized().y) > 0.99 else Vector3.UP)
	plume._process(0)
