extends GutTest

func test_common_character_clips_do_not_keep_a_weapon_in_hand():
	for clip in ["idle", "falling", "falling_to_landing", "defeated", "death_front", "death_flying_back"] + RobotClips.VICTORIES:
		assert_false(RobotClips.uses_weapon("common/" + clip), clip)
	for clip in ["idle", "fire", "reload", "jump_loop"]:
		assert_true(RobotClips.uses_weapon("rifle/" + clip), clip)

func test_character_clip_selection_covers_every_available_gameplay_context():
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/animations/manifest.json"))
	var used := {}
	var families := {}
	for weapon in Arsenal.WEAPONS.values(): families[String(weapon.animation_family)]=true
	for family in families:
		for crouched in [false, true]:
			for aiming in [false, true]: used[family + "/" + RobotClips.idle(crouched, aiming)] = true
		used[family + "/" + RobotClips.idle(true, false, family, true)] = true
		for input in [Vector2(0,-1), Vector2(1,-1), Vector2(1,0), Vector2(1,1), Vector2(0,1), Vector2(-1,1), Vector2(-1,0), Vector2(-1,-1)]:
			for speed in [ArenaTuning.WALK_SPEED, ArenaTuning.RUN_SPEED, ArenaTuning.SPRINT_SPEED]: used[family + "/" + RobotClips.travel(input, speed, false, family, 0.0)] = true
			used[family + "/" + RobotClips.travel(input, 2.5, true, family, 0.0)] = true
		for turn in [-0.2, 0.2]:
			for crouched in [false, true]: used[family + "/" + RobotClips.turn(crouched, turn)] = true
			for speed in [ArenaTuning.WALK_SPEED, ArenaTuning.RUN_SPEED]:
				for heading in [Vector2(0,-1), Vector2(0,1)]:
					used[family + "/" + RobotClips.travel(heading, speed, false, family, turn)] = true
		for moving in [false, true]:
			for charged in [false, true]: used[family + "/" + RobotClips.takeoff(family, moving, charged)] = true
		for clip in ["jump_loop", "jump_down", "fire", "reload", "hit_reaction", "aim_down45", "aim_down30", "aim_down15", "aim_level", "aim_up15", "aim_up30", "aim_up45"]:
			used[family + "/" + clip] = true
		if family == "pistol":
			used[family + "/stand_to_kneel"] = true
			used[family + "/kneel_to_stand"] = true
	for clip in ["idle", "falling", "falling_to_landing", "defeated"]:
		used["common/" + clip] = true
	for clip in ["death_front", "death_back", "death_right", "death_front_headshot", "death_back_headshot", "death_crouching_headshot", "death_flying_back"]:
		used["common/" + clip] = true
	for clip in RobotClips.VICTORIES: used["common/" + clip] = true
	var missing := []
	for clip in used:
		if not manifest.has(clip): missing.append(clip)
		elif not FileAccess.file_exists("res://assets/animations/" + manifest[clip].file): missing.append(clip + " (asset missing)")
	assert_eq(missing, [], "Every selected clip has an imported animation asset")
	var unassigned := []
	for clip in manifest:
		if not used.has(clip): unassigned.append(clip)
	unassigned.sort()
	assert_eq(unassigned, [], "The runtime animation manifest contains only gameplay clips")
