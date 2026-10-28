extends GutTest

class DamageWorld extends ArenaMatch:
	func eliminate(victim, _killer, _cause: String, _contact: Dictionary = {}):
		victim.alive = false

func fixture() -> Dictionary:
	var game := DamageWorld.new()
	autofree(game)
	game.phase = "Active"
	var victim := ArenaRobot.new()
	autofree(victim)
	victim.arena_match = game
	victim.protection = 0
	victim.surface_material = EnergySurface.material(Color.WHITE)
	return {"game":game,"victim":victim}

func test_full_strength_stream_kills_an_unshielded_robot_within_three_seconds():
	for weapon in ["lightning_gun", "flamethrower"]:
		var setup := fixture()
		var victim: ArenaRobot = setup.victim
		var profile: Dictionary = Arsenal.WEAPONS[weapon]
		var tick := 0
		while victim.alive and tick <= 30:
			victim.hit(profile.damage * profile.damage_tick,null,weapon)
			tick += 1
		assert_false(victim.alive,weapon + " kills by three seconds at full strength")
		assert_gte(float(tick-1)*profile.damage_tick,2.9-0.00001)
		assert_lte(float(tick-1)*profile.damage_tick,3.0+0.00001)

func test_elemental_hits_refresh_their_slow_without_stacking():
	for weapon in ["lightning_gun", "flamethrower"]:
		var setup := fixture()
		var victim: ArenaRobot = setup.victim
		var duration := 0.05 if weapon == "lightning_gun" else 0.025
		for hit in 5:
			assert_true(victim.hit(1.0,null,weapon))
			assert_eq(victim.slow_multiplier,0.8 if weapon == "lightning_gun" else 0.9)
			assert_eq(victim.slow_remaining,duration)
			victim.tick_movement_slow(duration*0.5)
			assert_almost_eq(victim.slow_remaining,duration*0.5,0.00001)
		victim.tick_movement_slow(duration*0.5)
		assert_eq(victim.slow_remaining,0.0)
		assert_eq(victim.slow_multiplier,1.0)

func test_rejected_or_zero_damage_hits_do_not_slow():
	for weapon in ["lightning_gun", "flamethrower"]:
		var setup := fixture()
		var victim: ArenaRobot = setup.victim
		victim.protection = 5.0
		assert_false(victim.hit(10.0,null,weapon))
		victim.protection = 0.0
		assert_false(victim.hit(0.0,null,weapon))
		assert_eq(victim.slow_remaining,0.0)
		assert_eq(victim.slow_multiplier,1.0)

func test_bio_impact_slow_expires_after_25_ms_and_poison_does_not_refresh_it():
	var setup := fixture()
	var victim: ArenaRobot = setup.victim
	var projectile := BallisticProjectile.new()
	autofree(projectile)
	projectile.weapon = "bio_rifle"
	projectile.profile = Arsenal.WEAPONS.bio_rifle
	for hit in 3:
		projectile.apply_status(victim)
		assert_eq(victim.slow_multiplier,0.9)
		assert_eq(victim.slow_remaining,0.025)
	victim.tick_movement_slow(0.024)
	assert_eq(victim.slow_multiplier,0.9)
	victim.tick_movement_slow(0.002)
	assert_eq(victim.slow_multiplier,1.0)
	var poison := victim.get_node("Poison_bio_rifle") as ProjectileStatus
	poison._physics_process(1.0)
	assert_eq(victim.ah,95.0)
	assert_eq(victim.slow_remaining,0.0)
	assert_eq(victim.slow_multiplier,1.0)
