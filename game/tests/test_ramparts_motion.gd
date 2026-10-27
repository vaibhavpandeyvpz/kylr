extends GutTest

func sections() -> Array:
	return JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/ramparts/ramparts_rig.json")).deck_sections

func test_shuttles_stay_inside_spans_and_travel_one_metre_per_second():
	var count:=0
	for section in sections():
		if section.get("motion",{}).get("kind","")!="shuttle":continue
		count+=1
		var spec: Dictionary=section.motion
		assert_almost_eq(absf(MapCarriers.shuttle_offset(.2,spec)-MapCarriers.shuttle_offset(.1,spec)),.1,.0001)
		assert_almost_eq(MapCarriers.shuttle_offset(0,spec),0.0,.0001)
		for step in range(301):
			var time:=step*.1
			var displacement:=MapCarriers.shuttle_offset(time,spec)
			assert_between(displacement+float(spec.start),-.0001,float(spec.distance)+.0001)
			var transform:=MapCarriers.transform_at(time,section)
			assert_between(transform.origin.y,-.5001,.5001)
		assert_almost_eq(MapCarriers.shuttle_offset(15,spec),0.0,.0001)
	assert_eq(count,6)

func test_bob_speed_and_clockwise_junction_rim_speed():
	for section in sections():
		if not section.has("motion"):continue
		var initial:=MapCarriers.transform_at(0,section)
		var next:=MapCarriers.transform_at(.001,section)
		if section.motion.kind=="shuttle":
			assert_almost_eq((next.origin.y-initial.origin.y)/.001,1.0,.001)
		else:
			var tip:=Vector3(float(section.motion.radius),10,0)
			var moved:=next*tip
			assert_gt(moved.z,0.0,"Clockwise from overhead")
			assert_almost_eq(tip.distance_to(moved)/.001,.5,.001)
			var period:=TAU*float(section.motion.radius)/float(section.motion.rim_speed)
			assert_lt((MapCarriers.transform_at(period,section)*tip).distance_to(tip),.001)

func test_authored_geometry_and_all_starting_decks_share_ten_metre_datum():
	var rock_count:=0
	for section in sections():
		assert_almost_eq(float(section.position[2]),10.0,.0001)
		if section.rock:
			rock_count+=1
			assert_eq(section.size_m,[25.0,25.0])
	assert_eq(rock_count,2)
	assert_eq(float(MapCatalog.find("ramparts").fall_boundary),0.0)

func test_carrier_collision_uses_animatable_body_and_retains_native_shape():
	var mount:=Node3D.new()
	add_child_autofree(mount)
	mount.set_meta("moving_platform",true)
	var deck:=Assets.model("maps","ramparts","_deck_A_Floater_1")
	mount.add_child(deck)
	CollisionRig.install(deck,"maps","ramparts",null,"_deck_A_Floater_1_col")
	var bodies:=deck.find_children("*","AnimatableBody3D",true,false)
	assert_gt(bodies.size(),0)
	for body in bodies:
		assert_false(body.sync_to_physics)
		assert_eq(body.collision_layer,1)
		assert_gt(body.find_children("*","CollisionShape3D",true,false).size(),0)
