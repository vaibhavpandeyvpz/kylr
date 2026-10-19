class_name BioProjectileVisual
extends Node3D
## Dedicated animated bio gel; immutable meshes/material recipes stay shared.
const POISON_BLOB_BODY_SHADER := preload("res://shaders/combat/bio_blob_body.gdshader")
const POISON_BLOB_MEMBRANE_SHADER := preload("res://shaders/combat/bio_blob_membrane.gdshader")
var model_size: float = 0.48
var vfx_primary_color: Color = Color(0.42, 1, 0.045, 1)
var vfx_secondary_color: Color = Color(0.035, 0.7, 0.018, 1)
var vfx_tertiary_color: Color = Color(0.004, 0.055, 0.012, 1)
var vfx_emission: float = 2.8
var vfx_color_curve: float = 1.35
var vfx_noise_scale: Vector2 = Vector2(2.8, 2.2)
var vfx_noise_scroll: Vector2 = Vector2(0.22, -0.16)
var vfx_noise_curve: float = 1.18
var vfx_speed_scale: float = 1.15
var vfx_mesh_resolution: int = 32
var vfx_edge_hardness: float = 0.13
var vfx_edge_position: float = 0.48
var blob_core_scale: float = 0.58
var blob_shell_scale: float = 1.0
var blob_deformation: float = 0.16
var blob_shell_deformation: float = 0.36
var blob_pulse_amount: float = 0.055
var blob_lobe_frequency: float = 5.2
var blob_membrane_opacity: float = 0.34
var blob_shell_rotation_amount_deg: float = 88.0
var blob_shell_rotation_speed: float = 0.92
var blob_droplet_count: int = 5
var blob_droplet_size: float = 0.07
var blob_orbit_speed: float = 1.5
var blob_ray_count: int = 8
var blob_ray_length: float = 0.24
var blob_ray_speed: float = 1.05
var _age: float = 0.0
var _blob_rotation_phase: Vector3
var _blob_core_pivot: Node3D
var _blob_membrane_pivot: Node3D
var _blob_droplet_pivot: Node3D
var _blob_droplets: Array[MeshInstance3D] = []
var _blob_droplet_directions: Array[Vector3] = []

func _ready() -> void:
	_add_poison_blob()

func _process(delta: float) -> void:
	_age += delta
	_animate_poison_blob()

func _add_poison_blob() -> void:
	var assembly := Node3D.new()
	assembly.name = "PoisonBlobAssembly"
	add_child(assembly)

	_blob_rotation_phase = Vector3(randf_range(0.0, TAU), randf_range(0.0, TAU), randf_range(0.0, TAU))
	_blob_core_pivot = Node3D.new()
	_blob_core_pivot.name = "CorePivot"
	assembly.add_child(_blob_core_pivot)
	_blob_membrane_pivot = Node3D.new()
	_blob_membrane_pivot.name = "MembranePivot"
	assembly.add_child(_blob_membrane_pivot)
	_blob_droplet_pivot = Node3D.new()
	_blob_droplet_pivot.name = "SurfaceParticlePivot"
	assembly.add_child(_blob_droplet_pivot)

	# Reserve the rest of model_size for shader displacement and surface lobes,
	# so the complete animated silhouette stays inside its authored envelope.
	var outer_radius := model_size * 0.3
	var segments := maxi(vfx_mesh_resolution, 20)
	var body := MeshInstance3D.new()
	body.name = "GelBody"
	body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	body.mesh = _new_blob_sphere(outer_radius * blob_core_scale, segments)
	body.material_override = _new_poison_blob_material(
		POISON_BLOB_BODY_SHADER,
		0.0,
		blob_deformation,
		blob_pulse_amount,
		vfx_noise_scale,
		vfx_noise_scroll,
	)
	body.scale = Vector3(1.0, 0.94, 0.98)
	_blob_core_pivot.add_child(body)

	var membrane := MeshInstance3D.new()
	membrane.name = "BoilingMembrane"
	membrane.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	membrane.mesh = _new_blob_sphere(outer_radius * blob_shell_scale, segments)
	var membrane_material := _new_poison_blob_material(
		POISON_BLOB_MEMBRANE_SHADER,
		7.9,
		blob_shell_deformation,
		blob_pulse_amount * 1.35,
		Vector2(vfx_noise_scale.y * 1.37, vfx_noise_scale.x * 0.78),
		Vector2(-vfx_noise_scroll.y, -vfx_noise_scroll.x) * 1.3,
	)
	membrane.material_override = membrane_material
	membrane.scale = Vector3(1.03, 0.96, 1.0)
	_blob_membrane_pivot.add_child(membrane)
	_blob_core_pivot.add_child(_build_poison_core_rays())

	_blob_droplets.clear()
	_blob_droplet_directions.clear()
	for index in maxi(blob_droplet_count, 0):
		var fraction := (float(index) + 0.5) / maxf(float(blob_droplet_count), 1.0)
		var y := 1.0 - fraction * 2.0
		var radial := sqrt(maxf(1.0 - y * y, 0.0))
		var angle := float(index) * 2.399963 + 0.63
		var direction := Vector3(cos(angle) * radial, y, sin(angle) * radial).normalized()
		var droplet := MeshInstance3D.new()
		droplet.name = "BoilingDroplet%02d" % index
		droplet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var size_variation := lerpf(0.72, 1.18, fposmod(float(index) * 0.618, 1.0))
		var droplet_radius := model_size * blob_droplet_size * size_variation
		droplet.mesh = _new_blob_sphere(droplet_radius, maxi(segments / 2, 12))
		droplet.material_override = _new_poison_blob_material(
			POISON_BLOB_BODY_SHADER,
			float(index + 1) * 1.73,
			blob_deformation * 0.72,
			blob_pulse_amount * 0.72,
			vfx_noise_scale,
			vfx_noise_scroll,
		)
		_blob_droplet_pivot.add_child(droplet)
		_blob_droplets.append(droplet)
		_blob_droplet_directions.append(direction)
	_animate_poison_blob()



func _new_blob_sphere(blob_radius: float, segments: int) -> PrimitiveMesh:
	var sphere := ProjectileResources.primitive(&"SphereMesh", {"radius":blob_radius,"height":blob_radius * 2.0,"radial_segments":segments,"rings":maxi(segments * 2 / 3, 10)})
	return sphere



func _new_poison_blob_material(
	shader: Shader,
	phase: float,
	deformation: float,
	pulse_amount: float,
	noise_scale: Vector2,
	noise_scroll: Vector2,
) -> ShaderMaterial:
	return ProjectileResources.shader(shader, {
		"primary_color":vfx_primary_color,
		"secondary_color":vfx_secondary_color,
		"tertiary_color":vfx_tertiary_color,
		"emission_energy":vfx_emission,
		"color_curve":vfx_color_curve,
		"animation_speed":vfx_speed_scale,
		"noise_scale":noise_scale,
		"noise_scroll":noise_scroll,
		"noise_curve":vfx_noise_curve,
		"deformation":deformation,
		"pulse_amount":pulse_amount,
		"lobe_frequency":blob_lobe_frequency,
		"phase_offset":phase,
		"rim_power":lerpf(3.4, 0.9, vfx_edge_position),
		"vein_width":clampf(vfx_edge_hardness, 0.02, 0.42),
		"shell_opacity":blob_membrane_opacity,
	})



func _animate_poison_blob() -> void:
	var amount := deg_to_rad(blob_shell_rotation_amount_deg)
	var speed := blob_shell_rotation_speed
	if is_instance_valid(_blob_core_pivot):
		_blob_core_pivot.rotation = _random_blob_rotation(_age * speed * 0.73, amount * 0.48, _blob_rotation_phase)
	if is_instance_valid(_blob_membrane_pivot):
		_blob_membrane_pivot.rotation = _random_blob_rotation(
			-_age * speed,
			amount,
			_blob_rotation_phase + Vector3(2.1, 4.4, 1.3),
		)
	if is_instance_valid(_blob_droplet_pivot):
		_blob_droplet_pivot.rotation = _random_blob_rotation(
			_age * speed * 1.16,
			amount * 0.72,
			_blob_rotation_phase + Vector3(5.2, 0.8, 3.6),
		)
	if _blob_droplets.is_empty():
		return
	var body_radius := model_size * 0.3
	for index in _blob_droplets.size():
		var droplet := _blob_droplets[index]
		if not is_instance_valid(droplet):
			continue
		var base_direction := _blob_droplet_directions[index]
		var phase := float(index) * 1.73
		var orbit_angle := _age * blob_orbit_speed * (0.72 + fposmod(float(index), 3.0) * 0.13)
		var orbit_axis := Vector3.FORWARD
		var direction := Basis(orbit_axis, orbit_angle + phase * 0.18) * base_direction
		var boil := sin(_age * vfx_speed_scale * (3.1 + float(index) * 0.17) + phase)
		var separation := body_radius * (1.02 + blob_droplet_size * 1.7 + boil * 0.18)
		droplet.position = direction * separation
		var squash := 1.0 + boil * 0.16
		droplet.scale = Vector3(1.0 / squash, squash, 1.0 / squash)



func _random_blob_rotation(time: float, amount: float, phase: Vector3) -> Vector3:
	return Vector3(
		sin(time * 0.83 + phase.x) + sin(time * 0.31 + phase.z) * 0.35,
		sin(time * 0.67 + phase.y) + cos(time * 0.27 + phase.x) * 0.42,
		cos(time * 0.91 + phase.z) + sin(time * 0.39 + phase.y) * 0.3,
	) * amount



func _build_poison_core_rays() -> GPUParticles3D:
	var rays := GPUParticles3D.new()
	rays.name = "CoreRayBursts"
	rays.amount = maxi(blob_ray_count, 1)
	rays.lifetime = 0.24
	rays.preprocess = 0.18
	rays.randomness = 0.72
	rays.emitting = blob_ray_count > 0
	# Core rays share the core's random rotation, rather than becoming a wake.
	rays.local_coords = true
	rays.visibility_aabb = AABB(Vector3.ONE * -1.0, Vector3.ONE * 2.0)

	var ramp := ProjectileResources.gradient(PackedFloat32Array([0.0, 0.12, 0.64, 1.0]), PackedColorArray([
		Color(vfx_primary_color.r, vfx_primary_color.g, vfx_primary_color.b, 0.0),
		Color(vfx_primary_color.r, vfx_primary_color.g, vfx_primary_color.b, 0.95),
		Color(vfx_secondary_color.r, vfx_secondary_color.g, vfx_secondary_color.b, 0.6),
		Color(vfx_secondary_color.r, vfx_secondary_color.g, vfx_secondary_color.b, 0.0),
	]))
	# These recipes are immutable; the GPUParticles node owns simulation state.
	rays.process_material = ProjectileResources.particles({
		"particle_flag_align_y":true,"emission_shape":ParticleProcessMaterial.EMISSION_SHAPE_SPHERE,
		"emission_sphere_radius":model_size * blob_core_scale * 0.18,
		"direction":Vector3.UP,"spread":180.0,
		"initial_velocity_min":model_size * blob_ray_speed * 0.45,"initial_velocity_max":model_size * blob_ray_speed,
		"gravity":Vector3.ZERO,"damping_min":model_size * blob_ray_speed * 1.8,"damping_max":model_size * blob_ray_speed * 2.8,
		"scale_min":0.55,"scale_max":1.15,"color_ramp":ramp})

	var ray_mesh := ProjectileResources.primitive(&"CylinderMesh", {"top_radius":model_size * 0.006,"bottom_radius":model_size * 0.018,"height":model_size * blob_ray_length,"radial_segments":4})
	rays.material_override = ProjectileResources.standard({
		"shading_mode":BaseMaterial3D.SHADING_MODE_UNSHADED,"transparency":BaseMaterial3D.TRANSPARENCY_ALPHA,
		"albedo_color":vfx_primary_color,"emission_enabled":true,"emission":vfx_primary_color,
		"emission_energy_multiplier":vfx_emission * 1.35})
	rays.draw_pass_1 = ray_mesh
	return rays



