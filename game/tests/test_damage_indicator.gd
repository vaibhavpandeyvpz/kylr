extends GutTest

func test_fall_impact_flashes_edges_without_an_attacker_bearing():
	var indicator := DamageIndicator.new()
	add_child_autofree(indicator)
	indicator.mark_fall_impact()
	assert_true(indicator.hits.is_empty())
	assert_eq(indicator.impact_age,0.0)
	assert_true(indicator.is_processing())
	indicator._process(0.4)
	assert_false(indicator.is_processing())
	indicator.clear()
	assert_eq(indicator.impact_age,INF)

func test_damage_bearing_tracks_camera_turn_merges_hits_and_expires():
	var viewer := Node3D.new()
	add_child_autofree(viewer)
	var camera := Camera3D.new()
	viewer.add_child(camera)
	var indicator := DamageIndicator.new()
	add_child_autofree(indicator)
	indicator.viewer = viewer
	indicator.camera = camera
	indicator.size = Vector2(1280,720)
	indicator.mark(Vector3(0,0,-10),20)
	assert_eq(indicator.hits.size(),1)
	assert_almost_eq(indicator.relative_angle(indicator.hits[0].direction),0.0,0.001)
	camera.rotation.y = -PI * 0.5
	assert_almost_eq(indicator.relative_angle(indicator.hits[0].direction),-PI * 0.5,0.001,"Front hit moves around the edge as the view turns right")
	indicator.mark(Vector3(1,0,-10),30)
	assert_eq(indicator.hits.size(),1,"Nearby shots refresh the same cue")
	indicator.mark(Vector3(0,0,10),45)
	assert_eq(indicator.hits.size(),2,"Opposite hit keeps a separate cue")
	indicator._process(1.31)
	assert_true(indicator.hits.is_empty(),"Damage cue clears after its brief hold and fade")

func test_local_damage_emits_source_only_for_accepted_hits():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.phase = "Active"
	var victim := game.add_robot(0,"Victim",0,false,"projector") as ArenaRobot
	var shooter := game.add_robot(1,"Shooter",1,false,"projector") as ArenaRobot
	game.local_robot = victim
	victim.protection = 0.0
	shooter.protection = 0.0
	shooter.position = Vector3(5,0,0)
	var indicator := DamageIndicator.new()
	add_child_autofree(indicator)
	indicator.viewer = victim
	indicator.camera = game.camera
	game.damage_taken.connect(indicator.mark)
	var audio_events_before := game.audio.events.size()
	assert_true(victim.hit(12.0,shooter,"pistol"))
	assert_eq(indicator.hits.size(),1)
	assert_gt(indicator.hits[0].direction.x,0.99)
	assert_eq(game.audio.events.size(), audio_events_before, "Taking damage adds no separate local sound")
	victim.protection = 5.0
	assert_false(victim.hit(12.0,shooter,"pistol"))
	assert_eq(indicator.hits.size(),1,"Blocked spawn-protection hits cannot paint a damage cue")
	victim.protection = 0.0
	game.local_robot = shooter
	for cause in ["pistol", "rifle", "minigun", "rocket_launcher", "emp_gun", "lightning_gun", "flamethrower"]:
		game.hit_marker = 0.0
		assert_true(victim.hit(1.0,shooter,cause))
		assert_gt(game.hit_marker,0.2,cause + " confirms accepted damage")
	game.hit_marker = 0.0
	victim.protection = 5.0
	assert_false(victim.hit(12.0,shooter,"rocket_launcher"))
	assert_eq(game.hit_marker,0.0,"Blocked hits never show confirmation")
	victim.protection = 0.0
	assert_false(victim.hit(0.0,shooter,"flamethrower"))
	assert_eq(game.hit_marker,0.0,"Zero damage cannot confirm a hit")
	assert_eq(game.audio.events.size(), audio_events_before, "A confirmed hit adds no local confirmation sound")
