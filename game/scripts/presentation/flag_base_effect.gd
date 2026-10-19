class_name FlagBaseEffect
extends Node3D

var materials: Array[ShaderMaterial] = []
var effect: Node3D
var last_color := Color(-1,-1,-1)
var last_reduced := false

func configure(color: Color, reduced: bool) -> void:
	if color == last_color and reduced == last_reduced: return
	last_color = color
	last_reduced = reduced
	for material in materials:
		material.set_shader_parameter("primary_color",color.lightened(0.25))
		material.set_shader_parameter("secondary_color",color)
		material.set_shader_parameter("speed_scale",0.0 if reduced else 1.0)

func _ready() -> void:
	effect = Node3D.new()
	add_child(effect)
	var plate := MeshInstance3D.new()
	plate.mesh = EffectMeshes.mesh("AxialCard")
	plate.scale = Vector3(2,1,2)
	plate.position.z = -1.0
	plate.position.y = 0.012
	plate.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/original/field.gdshader")
	material.set_shader_parameter("turbulence_texture",preload("res://assets/models/effects/combat_effects/turbulence_rgba.png"))
	material.set_shader_parameter("circular",true)
	plate.material_override = material
	effect.add_child(plate)
	materials.append(material)
	var color := last_color
	last_color = Color(-1,-1,-1)
	configure(color if color.r >= 0 else Color.WHITE,last_reduced)
