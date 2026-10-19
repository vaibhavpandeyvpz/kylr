class_name LightningOrb
extends Node3D

const CORE = preload("res://shaders/combat/lightning_orb_core.gdshader")
const SHELL = preload("res://shaders/combat/lightning_orb_shell.gdshader")
const WAKE = preload("res://shaders/combat/lightning_orb_wake.gdshader")
const WAKE_PARTICLES := 24
const ORB_SCALE := Arsenal.ORB_DIAMETER / 0.39
const LIGHTNING_SHADER = preload("res://shaders/original/electrical_ribbon.gdshader")
static var LIGHTNING_MESHES: Array[Mesh] = [EffectMeshes.mesh("ElectricalRibbon0"),EffectMeshes.mesh("ElectricalRibbon1")]
const LIGHTNING_PARTICLES := 10
static var lightning_material: ShaderMaterial
static var emission_points: ImageTexture
static var emission_normals: ImageTexture

func _ready():
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var phase := rng.randf() * TAU
	# Scale the source geometry and deformation together to a 10 cm outer shell.
	for index in 2:
		var radius := 0.18 if index == 0 else 0.195
		var sphere := ProjectileResources.primitive(&"SphereMesh", {"radius":radius,"height":radius*2.0,"radial_segments":24,"rings":16})
		var material := ProjectileResources.shader(CORE if index == 0 else SHELL)
		var mesh := MeshInstance3D.new()
		mesh.name = "Core" if index == 0 else "Shell"
		mesh.mesh = sphere
		mesh.scale = Vector3.ONE * ORB_SCALE
		mesh.material_override = material
		mesh.set_instance_shader_parameter("phase",phase)
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mesh.extra_cull_margin = 0.03
		add_child(mesh)

	var wake := GPUParticles3D.new()
	wake.name = "Wake"
	wake.amount = WAKE_PARTICLES
	wake.lifetime = 0.32 * ORB_SCALE
	wake.local_coords = false
	wake.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	wake.visibility_aabb = AABB(Vector3(-2, -2, -2), Vector3(4, 4, 4))
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	process.emission_sphere_radius = 0.06 * ORB_SCALE
	process.gravity = Vector3.ZERO
	process.initial_velocity_min = 0.0
	process.initial_velocity_max = 0.0
	process.scale_min = 0.18 * ORB_SCALE
	process.scale_max = 0.3 * ORB_SCALE
	# The source wake shader reads COLOR.r as normalized age, COLOR.a as fade.
	var gradient := Gradient.new()
	gradient.set_color(0, Color(0, 0, 0, 1))
	gradient.set_color(1, Color(1, 1, 1, 0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = gradient
	process.color_ramp = ramp
	wake.process_material = process
	var card := ProjectileResources.primitive(&"QuadMesh", {})
	wake.material_override = ProjectileResources.shader(WAKE)
	wake.set_instance_shader_parameter("seed",phase)
	wake.draw_pass_1 = card
	add_child(wake)
	add_lightning()

static func prepare_lightning():
	if lightning_material != null: return
	lightning_material = ShaderMaterial.new()
	lightning_material.shader = LIGHTNING_SHADER
	lightning_material.set_shader_parameter("Tint", Color("74bfff"))
	lightning_material.set_shader_parameter("Intensity", 5.355)
	# Analytic surface points + normals for the procedural orb's sphere.
	var points := Image.create(64, 1, false, Image.FORMAT_RGBAF)
	var normals := Image.create(64, 1, false, Image.FORMAT_RGBAF)
	for index in 64:
		var y := 1.0 - 2.0 * (index + 0.5) / 64.0
		var radial := sqrt(1.0 - y * y)
		var angle := index * PI * (3.0 - sqrt(5.0))
		var normal := Vector3(cos(angle) * radial, y, sin(angle) * radial)
		var point := normal * 0.061
		points.set_pixel(index, 0, Color(point.x, point.y, point.z))
		normals.set_pixel(index, 0, Color(normal.x, normal.y, normal.z))
	emission_points = ImageTexture.create_from_image(points)
	emission_normals = ImageTexture.create_from_image(normals)

func add_lightning():
	prepare_lightning()
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0.7))
	curve.add_point(Vector2(0.4, 0.9))
	curve.add_point(Vector2(1, 1.0))
	var scale_curve := CurveTexture.new()
	scale_curve.curve = curve
	for index in LIGHTNING_MESHES.size():
		var emitter := GPUParticles3D.new()
		emitter.name = "Lightning" + str(index + 1)
		emitter.amount = LIGHTNING_PARTICLES / LIGHTNING_MESHES.size()
		emitter.lifetime = 1.0
		emitter.preprocess = 0.55
		emitter.randomness = 0.25
		emitter.local_coords = true
		emitter.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Y_TO_VELOCITY
		emitter.visibility_aabb = AABB(Vector3(-0.2, -0.2, -0.2), Vector3(0.4, 0.4, 0.4))
		emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		emitter.draw_pass_1 = LIGHTNING_MESHES[index]
		emitter.material_override = lightning_material
		var process := ParticleProcessMaterial.new()
		process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_DIRECTED_POINTS
		process.emission_point_count = 64
		process.emission_point_texture = emission_points
		process.emission_normal_texture = emission_normals
		process.direction = Vector3.UP
		process.spread = 180.0
		process.initial_velocity_min = 0.003
		process.initial_velocity_max = 0.012
		process.gravity = Vector3.ZERO
		process.scale_min = 0.025
		process.scale_max = 0.045
		process.scale_curve = scale_curve
		emitter.process_material = process
		add_child(emitter)
