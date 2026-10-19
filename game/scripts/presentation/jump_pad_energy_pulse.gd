class_name JumpPadEnergyPulse
extends Node3D

var materials: Array[ShaderMaterial] = []
var motion_state := -1

func set_reduced_motion(reduced: bool) -> void:
	if motion_state == int(reduced): return
	motion_state = int(reduced)
	for material in materials:
		material.set_shader_parameter("motion_speed", 0.0 if reduced else 1.0)

## Render-only square field, attached in the jump pad's authored local axes.
## Three staggered outlines rise from the 1 m pad and fade before restarting.
func _ready() -> void:
	if DisplayServer.get_name() == "headless": return
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(0.92, 0.92)
	for index in 3:
		var material := ShaderMaterial.new()
		material.shader = preload("res://shaders/jump_pad_energy_pulse.gdshader")
		material.set_shader_parameter("phase_offset", float(index) / 3.0)
		materials.append(material)
		var ring := MeshInstance3D.new()
		ring.name = "LaunchSquare%d" % (index + 1)
		ring.mesh = mesh
		ring.material_override = material
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.extra_cull_margin = 0.8
		add_child(ring)
