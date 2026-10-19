class_name WeaponContactBurst
extends Node3D
## Common sprite/particle mechanics only; each weapon owns its composition.
const SPRITE_SHADER := preload("res://shaders/combat/contact_sprite.gdshader")
const SHELL_SHADER := preload("res://shaders/combat/contact_shell.gdshader")
var size_m := 1.0
var duration := 0.5
var particle_count := 12
var primary_color := Color.WHITE
var secondary_color := Color.WHITE
var core_color := Color.WHITE
var tertiary_color := Color(0.09,0.075,0.07)
var emission_energy := 3.4
var opacity := 1.0
var edge_hardness := 0.6
var flash_pinch := 0.45
var turbulence := 0.35
var streak_length := 0.8
var remaining := 0.0
var _elapsed := 0.0
var _materials: Array[ShaderMaterial] = []
var _shell_materials: Array[ShaderMaterial] = []
var _particles: Array[GPUParticles3D] = []
var _layers: Array[Dictionary] = []

func _ready() -> void:
	_build_layers()
	_apply_colors()
	hide()
	set_process(false)

func _build_layers() -> void:
	pass

func fire(point: Vector3, normal: Vector3) -> void:
	var up := Vector3.FORWARD if absf(normal.dot(Vector3.UP)) > 0.96 else Vector3.UP
	global_transform = Transform3D(Basis.looking_at(-normal,up).scaled(Vector3.ONE*size_m),point)
	_elapsed = 0.0
	remaining = duration + 0.1
	_render_progress(0.0)
	for particle in _particles:
		particle.restart()
		particle.emitting = true
	show()
	set_process(true)

func _process(dt: float) -> void:
	_elapsed += dt
	remaining = maxf(0.0,remaining-dt)
	_render_progress(clampf(_elapsed/duration,0.0,1.0))
	if remaining <= 0.0:
		hide()
		set_process(false)

func _apply_colors() -> void:
	for material in _materials:
		material.set_shader_parameter("primary_color",primary_color)
		material.set_shader_parameter("secondary_color",secondary_color)
		material.set_shader_parameter("tertiary_color",tertiary_color)
		material.set_shader_parameter("core_color",primary_color if material in _shell_materials else core_color)
		material.set_shader_parameter("emission_energy",minf(emission_energy*0.1,0.5) if material in _shell_materials else emission_energy)
		material.set_shader_parameter("effect_opacity",opacity*0.72 if material in _shell_materials else opacity)

func _render_progress(progress: float) -> void:
	for entry in _layers:
		var local_progress := clampf((progress-entry.start)/maxf(entry.end-entry.start,0.001),0.0,1.0)
		entry.node.visible = progress >= entry.start and progress <= entry.end
		entry.material.set_shader_parameter("effect_progress",local_progress)

func _add_layer(
	layer_name: String,
	shape_mode: float,
	extent: float,
	start: float,
	end: float,
	seed: float,
	spin: float = 0.0,
) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = layer_name
	var quad := ProjectileResources.primitive(&"QuadMesh",{"size":Vector2.ONE * extent})
	var material := _new_sprite_material(shape_mode, seed, spin)
	mesh_instance.material_override = material
	mesh_instance.mesh = quad
	add_child(mesh_instance)
	_materials.append(material)
	_layers.append({"node": mesh_instance, "material": material, "start": start, "end": end})

func _add_shell(layer_name: String, extent: float, start: float, end: float, seed: float) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = layer_name
	var sphere := ProjectileResources.primitive(&"SphereMesh",{"radius":extent * 0.5,"height":extent,"radial_segments":32,"rings":16})
	var material := ShaderMaterial.new()
	material.shader = SHELL_SHADER
	material.set_shader_parameter("seed", seed)
	material.set_shader_parameter("edge_hardness", edge_hardness)
	material.set_shader_parameter("flash_pinch", flash_pinch)
	material.set_shader_parameter("emission_energy", emission_energy)
	mesh_instance.material_override = material
	mesh_instance.mesh = sphere
	add_child(mesh_instance)
	_materials.append(material)
	_shell_materials.append(material)
	_layers.append({"node": mesh_instance, "material": material, "start": start, "end": end})

func _add_particles(
	layer_name: String,
	shape_mode: float,
	extent: float,
	speed_factor: float,
	particle_scale: float,
	count_factor: float = 1.0,
) -> void:
	var particles := _base_particles(layer_name, count_factor)
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	process.emission_sphere_radius = 0.025
	process.direction = Vector3(0.0, 0.25, 1.0)
	process.spread = 78.0 + turbulence * 44.0
	# The whole renderer is scaled to the authored metre footprint. Compensate
	# here so fragments travel at a readable world speed instead of a 3 m preset
	# also tripling its velocity.
	process.initial_velocity_min = speed_factor * 4.0 / size_m
	process.initial_velocity_max = speed_factor * 8.0 / size_m
	process.gravity = Vector3(0.0, -0.42, 0.0)
	process.damping_min = 0.7
	process.damping_max = 1.8
	process.scale_min = 0.62
	process.scale_max = 1.28
	particles.process_material = process
	var quad := ProjectileResources.primitive(&"QuadMesh",{"size":Vector2(extent * particle_scale, particle_scale)})
	var material := _new_sprite_material(shape_mode, randf_range(0.0, TAU), 0.0)
	material.set_shader_parameter("effect_progress", 0.2)
	particles.material_override = material
	particles.draw_pass_1 = quad
	_materials.append(material)
	_particles.append(particles)

func _base_particles(layer_name: String, count_factor: float) -> GPUParticles3D:
	var particles := GPUParticles3D.new()
	particles.name = layer_name
	particles.emitting = false
	particles.one_shot = true
	particles.explosiveness = 1.0
	particles.local_coords = true
	particles.amount = maxi(1, roundi(float(particle_count) * count_factor))
	particles.lifetime = duration
	particles.randomness = 0.32
	var bounds := maxf(4.0, streak_length * 4.0 + 0.9 * 2.0)
	particles.visibility_aabb = AABB(Vector3.ONE * -bounds, Vector3.ONE * bounds * 2.0)
	add_child(particles)
	return particles

func _new_sprite_material(shape_mode: float, seed: float, spin: float) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = SPRITE_SHADER
	material.set_shader_parameter("shape_mode", shape_mode)
	material.set_shader_parameter("seed", seed)
	material.set_shader_parameter("spin", spin)
	material.set_shader_parameter("edge_hardness", edge_hardness)
	material.set_shader_parameter("flash_pinch", flash_pinch)
	material.set_shader_parameter("emission_energy", emission_energy)
	return material

