class_name CombatTransient
extends MeshInstance3D

var lifetime := 0.3
var age := 0.0
var velocity := Vector3.ZERO
var acceleration := Vector3.ZERO
var spin := Vector3.ZERO
var growth := 0.0
var growth_axes := Vector3.ONE
var anchor: WeakRef
var anchor_offset := Transform3D.IDENTITY
var tracer_from := Vector3.ZERO
var tracer_to := Vector3.ZERO
var tracer := false
var align_velocity := false
var light: OmniLight3D
var light_peak_energy := 1.8
var progress_parameter := "progress"

func _process(dt: float) -> void:
	age += dt
	if age < 0:
		hide()
		return
	show()
	if age >= lifetime:
		queue_free()
		return
	var progress := age / lifetime
	if material_override is ShaderMaterial: set_instance_shader_parameter(progress_parameter, progress)
	if anchor:
		var socket = anchor.get_ref()
		if not is_instance_valid(socket) or not socket.is_inside_tree() or not socket.is_visible_in_tree():
			queue_free()
			return
		global_transform = socket.global_transform * anchor_offset
	else:
		position += velocity * dt + acceleration * dt * dt * 0.5
		velocity += acceleration * dt
		if align_velocity and velocity.length_squared() > 0.0001:
			quaternion = Quaternion(Vector3.UP, velocity.normalized())
		rotation += spin * dt
		if growth != 0.0: scale += growth_axes * growth * dt
	if tracer:
		var distance := tracer_from.distance_to(tracer_to)
		var direction := (tracer_to - tracer_from).normalized()
		var head := minf(distance, age * 360.0)
		var tail := maxf(0.0, head - 2.4)
		global_position = tracer_from + direction * (head + tail) * 0.5
		scale.y = maxf(0.001, head - tail)
	if light: light.light_energy = light_peak_energy * pow(1.0 - progress, 2.0)
