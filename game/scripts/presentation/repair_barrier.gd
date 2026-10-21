class_name RepairBarrier
extends RefCounted
## Projected station field on the native animated barrier, separate from armor FX.
const SHADER=preload("res://shaders/combat/repair_barrier.gdshader")
const TINT=Color("60ef98")

static func material() -> ShaderMaterial:
	var result:=ShaderMaterial.new()
	result.shader=SHADER
	result.set_shader_parameter("tint",TINT)
	return result

static func set_reduced_motion(material: ShaderMaterial,reduced: bool) -> void:
	var enabled:=not reduced
	if material.get_shader_parameter("motion_enabled")!=enabled:
		material.set_shader_parameter("motion_enabled",enabled)
