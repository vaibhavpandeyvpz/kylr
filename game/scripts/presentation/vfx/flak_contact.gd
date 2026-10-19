class_name FlakContact
extends WeaponContactBurst

var _dust: MeshInstance3D

func _init() -> void:
	size_m = 0.48
	duration = 0.42
	particle_count = 12
	primary_color = Color(1, 0.96, 0.78, 1)
	secondary_color = Color(1, 0.34, 0.08, 1)
	core_color = Color(1, 1, 1, 1)
	emission_energy = 3.4
	edge_hardness = 0.72
	flash_pinch = 0.7
	turbulence = 0.18
	streak_length = 1.2

func _build_layers() -> void:
	# Contact is a brief friction flash, ejected chips and a small dust puff.
	# It has no sustained fuel, pressure sphere or decorative energy slashes.
	_add_layer("ContactFlash", 0.0, 0.24, 0.0, 0.18, 0.0)
	_dust = MeshInstance3D.new()
	_dust.name = "AbrasionDust"
	_dust.mesh = EffectMeshes.mesh("AxialCard")
	_dust.scale = Vector3.ONE * 1.2
	_dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_dust.custom_aabb = AABB(Vector3.ONE*-1.5,Vector3.ONE*3.0)
	var dust_material := ShaderMaterial.new()
	dust_material.shader = preload("res://shaders/original/gas_volume.gdshader")
	dust_material.set_shader_parameter("volume_atlas",preload("res://assets/models/effects/combat_effects/grenade_atlas.png"))
	dust_material.set_shader_parameter("event_profile",1)
	dust_material.set_shader_parameter("effect_opacity",0.26)
	dust_material.set_shader_parameter("emission",0.0)
	_dust.material_override = dust_material
	add_child(_dust)
	var chips := _base_particles("ImpactChips", 1.0)
	chips.lifetime = 0.26
	chips.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3(0.0,0.1,1.0)
	process.spread = 64.0
	process.initial_velocity_min = 2.0/size_m
	process.initial_velocity_max = 5.0/size_m
	process.gravity = Vector3(0.0,-2.0/size_m,0.0)
	process.angular_velocity_min = -540.0
	process.angular_velocity_max = 540.0
	process.scale_min = 0.006/size_m
	process.scale_max = 0.018/size_m
	chips.process_material = process
	chips.draw_pass_1 = EffectMeshes.mesh("FragmentChip")
	var chip_material := ShaderMaterial.new()
	chip_material.shader = preload("res://shaders/original/casing_fragment.gdshader")
	chips.material_override = chip_material
	_particles.append(chips)

func _render_progress(progress: float) -> void:
	super._render_progress(progress)
	# Begin in the dust part of the atlas, omitting the grenade detonation.
	_dust.set_instance_shader_parameter("progress",lerpf(0.38,1.0,progress))
	_dust.visible = progress < 1.0
