class_name EmpCharge
extends Node3D

# A compact conductive capsule inside a separate, animated induction envelope.
# Physics continues to use the existing independently authored swept volume.
const SHELL = preload("res://shaders/combat/emp_charge_shell.gdshader")
const LENGTH := 0.3
const INITIAL_RADIUS := 0.06
const VISUAL_SCALE := 0.5
const PRIMARY := Color(0.42, 0.44, 0.46)
const SECONDARY := Color(0.70, 0.72, 0.74)
const TERTIARY := Color(0.10, 0.11, 0.12)
const EMISSION := 1.5
var core: MeshInstance3D
var shell: MeshInstance3D
var core_material: StandardMaterial3D
var shell_material: ShaderMaterial
var _last_opacity := -1.0

func _ready() -> void:
	core_material = StandardMaterial3D.new()
	core_material.metallic = 0.65
	core_material.roughness = 0.38
	core_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	core_material.albedo_color = PRIMARY
	core_material.emission_enabled = true
	core_material.emission = PRIMARY
	core_material.emission_energy_multiplier = 0.35
	core = add_envelope("ChargeCore", LENGTH * 0.13, LENGTH * 0.82, core_material)
	shell_material = ShaderMaterial.new()
	shell_material.shader = SHELL
	shell_material.set_shader_parameter("primary_color", PRIMARY)
	shell_material.set_shader_parameter("secondary_color", SECONDARY)
	shell_material.set_shader_parameter("tertiary_color", TERTIARY)
	shell_material.set_shader_parameter("emission_energy", EMISSION)
	shell = add_envelope("DistortedShell", INITIAL_RADIUS, LENGTH, shell_material)
	var cage := MeshInstance3D.new()
	cage.name = "InductionFilaments"
	cage.mesh = EffectMeshes.mesh("InductionCage")
	cage.material_override = shell_material
	cage.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cage.custom_aabb = AABB(Vector3.ONE*-0.7,Vector3.ONE*1.4)
	shell.add_child(cage)
	update_travel(0.0)

func add_envelope(id: String, radius: float, length: float, material: Material) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.name = id
	instance.mesh = EffectMeshes.mesh("PacketShell")
	instance.scale = Vector3(radius*2.0,length,radius*2.0)
	instance.material_override = material
	instance.rotation.x = PI / 2.0
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	instance.extra_cull_margin = 0.05
	instance.custom_aabb = AABB(Vector3.ONE*-0.6,Vector3.ONE*1.2)
	add_child(instance)
	return instance

func update_travel(travelled: float) -> void:
	if scale != Vector3.ONE*VISUAL_SCALE: scale = Vector3.ONE*VISUAL_SCALE
	var opacity := Arsenal.emp_opacity(travelled)
	visible = opacity > 0.0
	if opacity != _last_opacity:
		core_material.albedo_color.a = opacity
		shell_material.set_shader_parameter("opacity", opacity)
		_last_opacity = opacity
