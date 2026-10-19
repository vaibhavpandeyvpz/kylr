class_name SpeedRampEnergyArrows
extends Node3D
## Procedural chevrons travel along the delivered belt's slope, without collision.
var materials: Array[ShaderMaterial]=[]
var reduced_motion := false

func configure(metadata: Dictionary,reduced: bool) -> void:
	reduced_motion=reduced
	var axis: Array=metadata.authoring_belt.axis
	var forward:=Vector3(axis[0],axis[2],-axis[1]).normalized()
	var normal:=forward.cross(Vector3.RIGHT).normalized()
	basis=Basis(Vector3.RIGHT,normal,forward)
	var entry: Array=metadata.belt.entry
	position=Vector3(entry[0],entry[2],-entry[1])+normal*(float(metadata.belt.surface_offset_m)+0.08)

func set_reduced_motion(reduced: bool) -> void:
	reduced_motion=reduced
	for material in materials:material.set_shader_parameter("motion_speed",0.0 if reduced else 1.0)

func _ready() -> void:
	if DisplayServer.get_name()=="headless":return
	var plane:=PlaneMesh.new();plane.size=Vector2(0.84,0.30)
	for index in 4:
		var material:=ShaderMaterial.new()
		material.shader=preload("res://shaders/speed_ramp_energy_arrows.gdshader")
		material.set_shader_parameter("phase_offset",float(index)/4.0)
		material.set_shader_parameter("motion_speed",0.0 if reduced_motion else 1.0)
		materials.append(material)
		var arrow:=MeshInstance3D.new()
		arrow.name="DirectionalChevron%d"%(index+1);arrow.mesh=plane;arrow.material_override=material
		arrow.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		arrow.extra_cull_margin=2.0;add_child(arrow)
