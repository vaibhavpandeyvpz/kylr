class_name FlameContactLoop
extends Node3D
## Two staggered instances keep the contact cloud flowing across cycle seams.
var clouds: Array[OriginalEffect] = []
var elapsed := 0.0
var active := false

func _ready() -> void:
	for index in 2:
		var cloud := preload("res://assets/effects/original/fire_hit.tscn").instantiate() as OriginalEffect
		cloud.emission = 1.2
		add_child(cloud)
		cloud.set_process(false)
		for surface in cloud.surfaces:
			# A sustained contact has flowing gas, not repeated ignition flashes.
			if surface.role=="spatial_gas" and int(surface.layer)==2:
				surface.material.set_shader_parameter("effect_opacity",0.0)
			else:
				surface.material.set_shader_parameter("effect_opacity",0.65)
		clouds.append(cloud)
	stop()

func follow(point: Vector3, normal: Vector3, surface_offset := 0.015) -> void:
	global_transform = Transform3D(Basis(Quaternion(Vector3.UP,normal.normalized())).scaled(Vector3.ONE*0.6),point+normal.normalized()*surface_offset)
	if not active: elapsed = 0.0
	active = true
	show()
	set_process(true)
	update_clouds()

func stop() -> void:
	active = false
	hide()
	set_process(false)

func _process(dt: float) -> void:
	if not active: return
	elapsed += dt
	update_clouds()

func update_clouds() -> void:
	for index in clouds.size():
		var cloud := clouds[index]
		cloud.show()
		cloud.age = fmod(elapsed/cloud.duration+float(index)*0.5,1.0)*cloud.duration
		cloud._process(0.0)
