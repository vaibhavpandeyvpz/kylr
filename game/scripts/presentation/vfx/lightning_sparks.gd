class_name LightningSparks
extends Node3D

# Procedural electrical ribbons are shared by contacts and beam tips.
var continuous := false
var remaining := 0.0
var emitters: Array[GPUParticles3D] = []
static var contact_points: ImageTexture
static var contact_normals: ImageTexture

func _ready():
	LightningOrb.prepare_lightning()
	if contact_points == null:
		var points := Image.create(32, 1, false, Image.FORMAT_RGBAF)
		var normals := Image.create(32, 1, false, Image.FORMAT_RGBAF)
		for index in 32:
			var y := 0.1 + 0.9 * (index + 0.5) / 32.0
			var radial := sqrt(1.0 - y * y)
			var angle := index * PI * (3.0 - sqrt(5.0))
			var normal := Vector3(cos(angle) * radial, y, sin(angle) * radial)
			var point := normal * 0.07
			points.set_pixel(index, 0, Color(point.x, point.y, point.z))
			normals.set_pixel(index, 0, Color(normal.x, normal.y, normal.z))
		contact_points = ImageTexture.create_from_image(points)
		contact_normals = ImageTexture.create_from_image(normals)
	for index in 2:
		var emitter := GPUParticles3D.new()
		emitter.amount = 3 if continuous else 6
		emitter.lifetime = 0.7 if continuous else 0.4
		emitter.preprocess = 0.35 if continuous else 0.0
		emitter.one_shot = not continuous
		emitter.explosiveness = 0.0 if continuous else 1.0
		emitter.emitting = continuous
		emitter.local_coords = true
		emitter.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Y_TO_VELOCITY
		emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		emitter.visibility_aabb = AABB(Vector3.ONE * -0.4, Vector3.ONE * 0.8)
		emitter.draw_pass_1 = LightningOrb.LIGHTNING_MESHES[index]
		emitter.material_override = LightningOrb.lightning_material
		var process := ParticleProcessMaterial.new()
		process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_DIRECTED_POINTS
		process.emission_point_count = 64 if continuous else 32
		process.emission_point_texture = LightningOrb.emission_points if continuous else contact_points
		process.emission_normal_texture = LightningOrb.emission_normals if continuous else contact_normals
		process.emission_shape_scale = Vector3.ONE * 0.18 if continuous else Vector3.ONE
		process.direction = Vector3.UP
		process.spread = 0.0
		process.initial_velocity_min = 0.002 if continuous else 0.08
		process.initial_velocity_max = 0.008 if continuous else 0.2
		process.gravity = Vector3.ZERO
		process.scale_min = 0.014 if continuous else 0.05
		process.scale_max = 0.024 if continuous else 0.09
		var curve := Curve.new()
		curve.add_point(Vector2(0, 0.7))
		curve.add_point(Vector2(1, 1.0))
		var scale_curve := CurveTexture.new()
		scale_curve.curve = curve
		process.scale_curve = scale_curve
		emitter.process_material = process
		add_child(emitter)
		emitters.append(emitter)
	set_process(false)
	if not continuous: hide()

func fire(point: Vector3, normal: Vector3):
	global_position = point
	global_basis = Basis(Quaternion(Vector3.UP, normal))
	remaining = 0.48
	show()
	for emitter in emitters:
		emitter.restart()
		emitter.emitting = true
	set_process(true)

func _process(dt: float):
	remaining = maxf(0, remaining - dt)
	if remaining <= 0:
		for emitter in emitters: emitter.emitting = false
		hide()
		set_process(false)
