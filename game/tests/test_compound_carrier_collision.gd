extends GutTest

func test_fixed_carrier_parts_share_bodies_without_changing_native_shapes():
	var rig: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(MapCatalog.find("skyfall").metadata))
	var marker: Dictionary=rig.markers.filter(func(m):return m.role=="platform")[0]
	var fixed:=Assets.model(marker.category,marker.asset,marker.asset_suffix)
	var moving:=Assets.model(marker.category,marker.asset,marker.asset_suffix)
	add_child_autofree(fixed);add_child_autofree(moving)
	moving.set_meta("moving_platform",true)
	CollisionRig.install(fixed,marker.category,marker.asset,null,marker.asset_suffix+"_col")
	CollisionRig.install(moving,marker.category,marker.asset,null,marker.asset_suffix+"_col")
	await wait_physics_frames(2)
	var original: Array=fixed.find_children("*","StaticBody3D",true,false)
	var compound: Array=moving.find_children("*","StaticBody3D",true,false)
	assert_lt(compound.size(),original.size(),"A casting updates fewer physics body transforms")
	var old_shapes: Array=fixed.find_children("*","CollisionShape3D",true,false)
	var new_shapes: Array=moving.find_children("*","CollisionShape3D",true,false)
	assert_eq(new_shapes.size(),old_shapes.size(),"Every authored surface remains present")
	var used: Dictionary={}
	for old in old_shapes:
		var found: int=-1
		for index in new_shapes.size():
			if used.has(index):continue
			var candidate: CollisionShape3D=new_shapes[index]
			if candidate.shape!=old.shape or not candidate.global_transform.is_equal_approx(old.global_transform):continue
			if candidate.get_parent().get_meta("lethal_surface")!=old.get_parent().get_meta("lethal_surface"):continue
			found=index;used[index]=true;break
		assert_gte(found,0,"Compound physics retains the exact native shape, frame and lethal policy")
	for body in compound:
		assert_true(body is AnimatableBody3D)
		assert_eq(body.collision_layer,1);assert_eq(body.collision_mask,0)

func test_mounted_weapon_and_barricade_compounds_preserve_shape_counts():
	for spec in [["weapons","minigun"],["gameplay","barricade"]]:
		var fixed:=Assets.model(spec[0],spec[1]);var moving:=Assets.model(spec[0],spec[1])
		add_child_autofree(fixed);add_child_autofree(moving);moving.set_meta("moving_platform",true)
		CollisionRig.install(fixed,spec[0],spec[1]);CollisionRig.install(moving,spec[0],spec[1])
		await wait_physics_frames(2)
		var original: Array=fixed.find_children("*","StaticBody3D",true,false)
		var compact: Array=moving.find_children("*","StaticBody3D",true,false)
		assert_lte(compact.size(),original.size(),spec[1]+" preserves independently moving bone bodies")
		var old_shapes: Array=fixed.find_children("*","CollisionShape3D",true,false)
		var new_shapes: Array=moving.find_children("*","CollisionShape3D",true,false)
		assert_eq(new_shapes.size(),old_shapes.size())
		var used: Dictionary={}
		for old in old_shapes:
			var found: int=-1
			for index in new_shapes.size():
				if used.has(index):continue
				if new_shapes[index].shape==old.shape and new_shapes[index].global_transform.is_equal_approx(old.global_transform):found=index;used[index]=true;break
			assert_gte(found,0,"Mounted native geometry and motion frames stay exact")

func test_carrier_groups_preserve_world_shapes_materials_and_bobbing():
	var game:=ArenaMatch.new();game.map_id="skyfall";game.online=true;game.authority=false
	add_child_autofree(game)
	while not game.initialization_complete:await wait_physics_frames(1)
	game.set_process(false);game.set_physics_process(false);game.map.set_process(false)
	game.map.config=game.map.config.duplicate(true);game.map.config.rigid_carrier_collision=false
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	await wait_physics_frames(1)
	var snapshot: Dictionary={}
	for shape: CollisionShape3D in game.map.model.find_children("*","CollisionShape3D",true,false):
		var parent:=shape.get_parent() as CollisionObject3D
		snapshot[shape.get_instance_id()]={"shape":shape.shape,"transform":Assets.socket_world_transform(shape),"layer":parent.collision_layer,"mask":parent.collision_mask,"material":parent.get_meta("spatio_material",""),"lethal":parent.get_meta("lethal_surface",false)}
	var result:=CarrierCollision.consolidate(game.map.carriers)
	assert_gt(int(result.bodies_before)-int(result.bodies_after),100)
	var shapes: Array=game.map.model.find_children("*","CollisionShape3D",true,false)
	assert_eq(shapes.size(),snapshot.size(),"Consolidation preserves all solids and triggers")
	for shape: CollisionShape3D in shapes:
		var old: Dictionary=snapshot[shape.get_instance_id()]
		var parent:=shape.get_parent() as CollisionObject3D
		assert_same(shape.shape,old.shape)
		assert_true(Assets.socket_world_transform(shape).is_equal_approx(old.transform))
		assert_eq(parent.collision_layer,old.layer);assert_eq(parent.collision_mask,old.mask)
		assert_eq(parent.get_meta("spatio_material",""),old.material);assert_eq(parent.get_meta("lethal_surface",false),old.lethal)
	for time in [1.7,4.2]:
		game.elapsed=time;game.map.carriers.sample(time)
		for shape: CollisionShape3D in shapes:
			if not shape.has_meta("carrier_group"):continue
			var group: String=shape.get_meta("carrier_group")
			var section: Dictionary=game.map.carriers.sections.filter(func(d):return game.map.carriers.rigid_groups[d.name]==group)[0]
			var expected: Transform3D=MapCarriers.transform_at(time,section)*snapshot[shape.get_instance_id()].transform
			assert_true(Assets.socket_world_transform(shape).is_equal_approx(expected),"Compound geometry follows the exact native rigid group")
