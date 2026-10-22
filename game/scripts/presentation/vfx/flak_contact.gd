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
	# Contact owns the friction flash and dust; ArenaEffects emits shared sparks.
	# It has no sustained fuel, pressure sphere or decorative energy slashes.
	_add_layer("ContactFlash", 0.0, 0.24, 0.0, 0.18, 0.0)
	_dust = MeshInstance3D.new()
	_dust.name = "AbrasionDust"
	_dust.mesh = EffectMeshes.mesh("AxialCard")
	_dust.scale = Vector3.ONE * 1.2
	_dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_dust.custom_aabb = AABB(Vector3.ONE*-1.5,Vector3.ONE*3.0)
	var dust_material := ShaderMaterial.new()
	dust_material.shader = preload("res://shaders/original/flak_dust.gdshader")
	dust_material.set_shader_parameter("volume_atlas",preload("res://assets/models/effects/combat_effects/flak_dust_atlas.png"))
	dust_material.set_shader_parameter("effect_opacity",0.26)
	_dust.material_override = dust_material
	add_child(_dust)

func _render_progress(progress: float) -> void:
	super._render_progress(progress)
	# Begin in the dust part of the atlas, omitting the grenade detonation.
	_dust.set_instance_shader_parameter("progress",lerpf(0.38,1.0,progress))
	_dust.visible = progress < 1.0
