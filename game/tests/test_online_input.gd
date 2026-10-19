extends GutTest
func command() -> Dictionary:
	return {"generation":"match","seq":1,"move":Vector2.ZERO,"yaw":0.0,"pitch":0.0,"walk":false,"sprint":false,"crouch":false,"fire":false,"secondary":false,"held":false,"jump":false,"release":false,"reload":false,"slot":""}
func test_client_cannot_supply_position_damage_or_inventory():
	for key in ["position","damage","ammo","health","team","display_name"]:
		var value := command()
		value[key] = 100
		assert_false(OnlineInput.valid(value,"match",0),key)
func test_rejects_stale_generation_replay_invalid_numbers_and_speed():
	assert_true(OnlineInput.valid(command(),"match",0))
	assert_false(OnlineInput.valid(command(),"previous",0))
	assert_false(OnlineInput.valid(command(),"match",1))
	for replacement in [Vector2(4,0),Vector2(INF,0),Vector2(NAN,0)]:
		var value := command()
		value.move = replacement
		assert_false(OnlineInput.valid(value,"match",0))
	for replacement in [INF,NAN,100.0,"0"]:
		var value := command()
		value.yaw = replacement
		assert_false(OnlineInput.valid(value,"match",0))
	var leap := command()
	leap.seq = 121
	assert_false(OnlineInput.valid(leap,"match",0))
func test_only_owned_slot_selectors_and_boolean_actions():
	var value := command()
	value.slot = "rocket_launcher"
	assert_false(OnlineInput.valid(value,"match",0))
	value.slot = "pickup"
	assert_true(OnlineInput.valid(value,"match",0))
	value.fire = 1
	assert_false(OnlineInput.valid(value,"match",0))
