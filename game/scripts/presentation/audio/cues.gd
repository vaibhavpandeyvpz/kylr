class_name AudioCues
extends RefCounted
const PLAYBACK_GAIN_DB := 12.0
const FAR_ATTENUATION_DB := -30.0
static var profiles: Dictionary = {}

static func profile(id: String) -> Dictionary:
	if profiles.is_empty():
		profiles=JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/cues.json"))
	var value := {"asset":id,"gain":-14.0,"near":4.0,"far":55.0,"priority":40,"limit":4,"cooldown":0.06,"pitch":0.025,"bus":"World","loop":false}
	value.merge(profiles.get(id,{}),true)
	return value

static func importance(profile: Dictionary,distance: float,local: bool) -> float:
	return float(profile.priority)+(30 if local else 0)-clampf(distance/float(profile.far),0,1)*25

static func distance_attenuation_db(profile: Dictionary, distance: float) -> float:
	var near_distance: float = profile.near
	var far_distance: float = profile.far
	if far_distance <= near_distance: return 0.0
	var t := clampf((distance-near_distance)/(far_distance-near_distance),0.0,1.0)
	return FAR_ATTENUATION_DB * t * t * (3.0 - 2.0 * t)
