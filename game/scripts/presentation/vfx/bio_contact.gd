class_name BioContact
extends WeaponContactBurst

func _init() -> void:
	size_m = 0.89
	duration = 0.68
	particle_count = 42
	primary_color = Color(0.42, 1, 0.045, 1)
	secondary_color = Color(0.035, 0.7, 0.018, 1)
	core_color = Color(0.70, 1, 0.20, 1)
	tertiary_color = Color(0.004, 0.055, 0.012, 1)
	emission_energy = 4.0
	edge_hardness = 0.7
	flash_pinch = 0.62
	turbulence = 0.36
	streak_length = 1.3

func _build_layers() -> void:
	_add_layer("Core", 0.0, 0.22, 0.0, 0.58, 0.0)
	_add_shell("NovaShell", 1.02, 0.0, 0.78, 1.2)
	_add_layer("Nova", 3.0, 1.12, 0.0, 0.7, 0.6)
	_add_layer("ShockRing", 1.0, 1.0, 0.08, 0.94, 1.4)
	_add_particles("LongRays", 4.0, 1.45, 0.68, 0.08)
	_add_particles("HotSparks", 5.0, 0.6, 0.94, 0.2, 0.55)
