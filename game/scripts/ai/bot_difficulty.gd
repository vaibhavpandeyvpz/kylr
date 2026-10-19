class_name BotDifficulty
extends RefCounted

static var data: Dictionary = load_data()
static var trace_enabled := OS.is_debug_build() and "--bot-trace" in OS.get_cmdline_user_args()

static func load_data() -> Dictionary:
	var config: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/ai/difficulty.json"))
	assert(config.schema_version == 1 and config.profiles.size() == 4,"Unsupported bot difficulty data")
	for index in 4:
		var profile: Dictionary = config.profiles[index]
		assert(profile.accuracy == [0.8,0.9,0.9,1.0][index] and profile.damage == [0.5,0.75,1.0,1.25][index],"Locked difficulty table changed")
		assert(profile.decision_interval > 0 and profile.perception_radius > 0 and profile.memory_seconds >= 0)
		assert(profile.aim_turn_rate>0 and profile.aim_sample_interval>=0 and profile.projectile_lead>=0 and profile.projectile_lead<=1)
		assert(profile.fire_burst>0 and profile.fire_pause>=0 and profile.strafe_pause>=0)
		assert(profile.precision_interval>=0.25)
		assert(profile.dodge_chance>=0 and profile.dodge_chance<=1 and profile.dodge_cooldown>0)
		assert(profile.ammo_horizon>0 and profile.equipment_detour>0 and profile.weapon_upgrade_ratio>1)
		assert(profile.reload_fraction>0 and profile.reload_fraction<1 and profile.reload_memory_remaining>=0 and profile.reload_memory_remaining<=profile.memory_seconds)
		assert(profile.headshot_chance>=0 and profile.headshot_chance<=1 and profile.headshot_max_speed>=0 and profile.orb_min_range>0)
	return config

static func profile(index: int) -> Dictionary:
	return data.profiles[clampi(index,0,3)]

static func trace(event: String, details: Dictionary) -> void:
	if trace_enabled:
		print("BOT_TRACE ",JSON.stringify({"event":event,"revision":data.revision,"details":details}))
