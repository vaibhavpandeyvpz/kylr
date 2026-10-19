class_name PackBurst
extends Node3D

var scene: PackedScene
var effect: Node3D
var remaining := 0.0
var anchor: WeakRef
var anchor_offset := Transform3D.IDENTITY
var emp := false
var refraction: MeshInstance3D

func _ready() -> void:
	effect = PackVfx.instantiate(scene)
	add_child(effect)
	PackVfx.apply_palette(effect)
	if effect.has_method("apply_runtime_preset"): effect.apply_runtime_preset()
	if emp:
		for material in PackVfx.materials(effect):
			material.set_shader_parameter("primary_color", Color(0.38, 0.38, 0.38, 0.35))
			material.set_shader_parameter("secondary_color", Color(0.38, 0.38, 0.38, 0.35))
			material.set_shader_parameter("tertiary_color", Color(0.38, 0.38, 0.38, 0.35))
			material.set_shader_parameter("effect_opacity", 0.18)
			material.set_shader_parameter("effect_emission", 0.08)
		var smoke := effect.get_node_or_null("Smoke")
		if smoke: smoke.hide()
		refraction = MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius = 1.2
		sphere.height = 2.4
		sphere.radial_segments = 32
		sphere.rings = 16
		refraction.mesh = sphere
		var material := ShaderMaterial.new()
		material.shader = preload("res://shaders/combat/emp_impact_volume.gdshader")
		for key in ["primary_color", "secondary_color", "core_color", "tertiary_color"]:
			material.set_shader_parameter(key, Color(0.45, 0.45, 0.45))
		material.set_shader_parameter("effect_opacity", 0.65)
		material.set_shader_parameter("emission_energy", 0.0)
		refraction.material_override = material
		refraction.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(refraction)
	hide()
	set_process(false)

func fire(point: Vector3, outward: Vector3, size := 1.0) -> void:
	global_transform = Transform3D(Basis(Quaternion(Vector3.UP, outward.normalized())) * Basis.from_scale(Vector3.ONE * size), point)
	remaining = PackVfx.play_once(effect)
	show()
	set_process(true)
	if refraction:
		remaining = maxf(remaining, 1.2)
		refraction.set_instance_shader_parameter("effect_progress", 0.0)

func _process(dt: float) -> void:
	remaining = maxf(0.0, remaining - dt)
	if anchor:
		var socket := anchor.get_ref() as Node3D
		if not is_instance_valid(socket): remaining = 0.0
		else: global_transform = socket.global_transform * anchor_offset
	if refraction:
		var progress := clampf(1.0 - remaining / 1.2, 0.0, 1.0)
		refraction.scale = Vector3.ONE * lerpf(0.1, 2.0, smoothstep(0.0, 0.5, progress))
		refraction.set_instance_shader_parameter("effect_progress", progress)
	if remaining <= 0:
		hide()
		set_process(false)
