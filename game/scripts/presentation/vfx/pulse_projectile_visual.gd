class_name PulseProjectileVisual
extends Node3D
## Focused white core and a separate cyan packet sheath; local -Z is flight.
const LENGTH_M := 0.10
const RADIUS_M := 0.05
const COLOR := Color(0.0, 0.8, 0.7882353)
static var _material: ShaderMaterial
func _ready() -> void:
	if _material == null:
		_material = ShaderMaterial.new()
		_material.shader = preload("res://shaders/original/pulse_packet.gdshader")
	for index in 2:
		var body := MeshInstance3D.new()
		body.name = "PulseCore" if index == 0 else "PulseSheath"
		body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		body.mesh = EffectMeshes.mesh("PacketShell")
		body.material_override = _material
		body.scale = Vector3(0.014,0.014,LENGTH_M*0.85) if index == 0 else Vector3(RADIUS_M*0.7,RADIUS_M*0.7,LENGTH_M)
		body.set_instance_shader_parameter("core_layer",1.0 if index == 0 else 0.0)
		add_child(body)
