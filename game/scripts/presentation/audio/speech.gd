class_name ArenaSpeech
extends RefCounted
## Stable recording keys keep account names and weapon names out of audio paths.
const ROBOT_VOICES := 10

static func line_key(text: String) -> String:
	if text in ["Double Kill","Triple Kill","Mega Kill","Champion","Death Bringer"]: return text.to_lower().replace(" ","_")
	if text in ["Armor hit","Armor hit."]: return "armor_hit"
	if text.ends_with(" acquired"): return "pickup"
	if text.begins_with("Repair complete"): return "repair_complete"
	if text.begins_with("POWER /"):
		return "power_critical" if text.contains("Critical") else "power_low"
	if text.begins_with("ARENA /"):
		return "arena_warning" if text.contains(" seconds") else "arena_changed"
	if text.contains("captured the flag"): return "flag_captured"
	if text.contains("took the flag"): return "flag_taken"
	if text.contains("returned the flag") or text.begins_with("Flag returned"): return "flag_returned"
	if text == "Flag dropped.": return "flag_dropped"
	if text == "Eliminated": return "eliminated"
	if text == "Draw": return "draw"
	if text == "Canceled": return "canceled"
	if text.ends_with(" wins"): return "match_won"
	return text

static func recording(bank: Dictionary, text: String, critical: bool, robot_id: int) -> Dictionary:
	var key := line_key(text)
	if robot_id >= 0:
		var variants: Array = bank.get("robots",[])
		if variants.size() != ROBOT_VOICES: return {}
		var voice: Dictionary = variants[posmod(robot_id,ROBOT_VOICES)]
		var asset := str(voice.get("lines",{}).get(key,""))
		return {} if asset.is_empty() else {"asset":asset,"pitch_scale":clampf(float(voice.get("pitch_scale",1.0)),0.75,1.3),"bus":"Voices"}
	var entries: Dictionary = bank.get("announcer" if critical else "robot",{})
	var asset := str(entries.get(key,entries.get(text,"")))
	return {} if asset.is_empty() else {"asset":asset,"pitch_scale":1.0,"bus":"Announcer" if critical else "Voices","gain":-8.0 if key in ["double_kill","triple_kill","mega_kill","champion","death_bringer"] else -14.0}
