class_name ArenaSpeech
extends RefCounted
## Stable recording keys keep account names and weapon names out of audio paths.
const ROBOT_VOICES := 10
const KILL_QUIPS := {
	"eat_that":"Eat that!", "say_no_more":"Say no more.",
	"rot_in_hell":"Rot in hell.", "goodbye_fella":"Goodbye fella.",
	"loser":"Loser.", "you_suck":"You suck!",
	"anyone_else":"Anyone else wants some?", "next":"Next!",
	"yeehaw":"Yeehaw!", "step_aside":"Step aside.",
	"boom_baby":"Boom baby!", "headshot":"Headshot!"
}

static func kill_quip_choices(weapon: String) -> Array[String]:
	var choices: Array[String] = []
	for key in KILL_QUIPS:
		if key == "boom_baby" and weapon not in ["rocket_launcher","grenade_launcher"]: continue
		if key == "headshot" and weapon != "rifle_headshot": continue
		choices.append(KILL_QUIPS[key])
	return choices

static func is_kill_quip(text: String) -> bool:
	return text in KILL_QUIPS.values()

static func follows_speaker(text: String) -> bool:
	return is_kill_quip(text) or line_key(text) in ["repair_complete","power_low","power_critical"]

static func line_key(text: String) -> String:
	for key in KILL_QUIPS:
		if KILL_QUIPS[key] == text: return key
	if text in ["Double Kill","Triple Kill","Mega Kill","Champion","Death Bringer"]: return text.to_lower().replace(" ","_")
	if text in ["Armor hit","Armor hit."]: return "armor_hit"
	if text.ends_with(" acquired"): return "pickup"
	if text == "Let's go!": return "repair_complete"
	if text == "Finding energy core.": return "power_low"
	if text == "Emergency!": return "power_critical"
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
		return {} if asset.is_empty() else {"asset":asset,"pitch_scale":clampf(float(voice.get("pitch_scale",1.0)),0.75,1.3),"bus":"Voices","gain":-8.0}
	var entries: Dictionary = bank.get("announcer" if critical else "robot",{})
	var asset := str(entries.get(key,entries.get(text,"")))
	return {} if asset.is_empty() else {"asset":asset,"pitch_scale":1.0,"bus":"Announcer" if critical else "Voices","gain":-8.0 if key in ["double_kill","triple_kill","mega_kill","champion","death_bringer"] else -14.0}
