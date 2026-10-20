class_name TutorialHints
extends RefCounted
var clock := 0.0
var finished := false

func text(game: ArenaMatch, prefs: Preferences, dt: float) -> String:
	if not prefs.values.tutorial_hints or finished or game.local_robot == null: return ""
	var robot: ArenaRobot = game.local_robot
	if game.phase != "Active" or not robot.alive or robot.protection > 0 or robot.repair != null: return ""
	clock += dt
	var step := int(clock/8.0)
	if step >= 5:
		finished = true
		prefs.values.tutorial_hints = false
		prefs.save()
		return ""
	var team := "Free for all" if MatchTypes.individual(game.match_type) else "Team A" if robot.team == 0 else "Team B"
	var fire := Preferences.binding_text(int(prefs.bindings.fire))
	var reload := Preferences.binding_text(int(prefs.bindings.reload))
	var lines := [
		TranslationServer.translate("Your team: %s. Team letters remain visible alongside colors.") % team,
		TranslationServer.translate("Fire: %s. Reload: %s. An empty weapon reloads or switches to your previous gun with ammo, then pistol. Cycle owned guns with the wheel.") % [fire,reload],
		TranslationServer.translate("EP drains while you fight. Collect green Energy Cores before shutdown; purple Shield Cores restore SH."),
		TranslationServer.translate("At 50 AH or less, enter a Ready repair bay. The first second is vulnerable; repair releases you after seven seconds."),
		TranslationServer.translate("Carry the enemy flag home while your own flag is home. Recover a dropped friendly flag by touching it.") if game.match_type == "CTF" else TranslationServer.translate("Eliminate opponents to reach the score goal. Hold the scoreboard key to check the current totals.")]
	if MatchTypes.individual(game.match_type): lines[0]="Free for all. Every other robot is an opponent."
	if game.match_type=="GUNGAME": lines[1]="Fire: %s. Reload: %s. Each kill assigns a new weapon. Collect ammo for your assigned gun."%[fire,reload]
	if game.match_type=="ELIMINATION": lines[4]="Five lives. Reach the kill goal or outlast the others. "+("Your fifth death ends Instant Action." if not game.online else "After your fifth death, spectate until results.")
	return TranslationServer.translate("FIRST LIFE / %d OF 5") % (step+1) + "\n" + lines[step]
