class_name ImpactSparks
extends GPUParticles3D

var remaining := 0.0
var physics := ParticleProcessMaterial.new()
var appearance := ShaderMaterial.new()

func _init():
	amount = 24
	lifetime = 0.36
	one_shot = true
	explosiveness = 1.0
	randomness = 0.35
	emitting = false
	local_coords = false
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visibility_aabb = AABB(Vector3.ONE * -3, Vector3.ONE * 6)
	physics.direction = Vector3.UP
	physics.spread = 65.0
	physics.initial_velocity_min = 3.5
	physics.initial_velocity_max = 7.0
	physics.damping_min = 2.0
	physics.damping_max = 4.0
	physics.scale_min = 0.65
	physics.scale_max = 1.4
	physics.particle_flag_align_y = true
	process_material = physics
	var streak := CylinderMesh.new()
	streak.top_radius = 0.002
	streak.bottom_radius = 0.008
	streak.height = 0.14
	streak.radial_segments = 4
	appearance.shader = preload("res://shaders/combat/particle_spark.gdshader")
	streak.material = appearance
	draw_pass_1 = streak
	hide()
	set_process(false)

func fire(point: Vector3, normal: Vector3, energy: bool, gravity: float):
	global_position = point
	global_basis = Basis(Quaternion(Vector3.UP, normal.normalized()))
	physics.gravity = Vector3.DOWN * gravity
	appearance.set_shader_parameter("tint", Color("79c8ff") if energy else Color("ffe08a"))
	remaining = lifetime + 0.08
	show()
	restart()
	emitting = true
	set_process(true)

func _process(dt: float):
	remaining = maxf(0, remaining - dt)
	if remaining <= 0:
		hide()
		set_process(false)
