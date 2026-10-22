extends GutTest

func test_four_consumers_dispatch_to_one_shared_pool():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	effects.impact(Vector3.ZERO,Vector3.UP)
	effects.sparks(Vector3.RIGHT,Vector3.UP,false,&"welding")
	effects.flak_contact(Vector3.LEFT,Vector3.UP)
	effects.emp_contact(Vector3.BACK,Vector3.UP)
	assert_eq(effects.spark_pool.size(),4)
	var profiles: Array[StringName] = []
	for emitter in effects.spark_pool:
		profiles.append(emitter.profile)
		assert_same(emitter.renderer.multimesh.mesh,effects.spark_pool[0].renderer.multimesh.mesh)
		assert_same(emitter.renderer.material_override,effects.spark_pool[0].renderer.material_override)
	assert_eq(profiles,[&"ballistic",&"welding",&"flak",&"emp"])
	assert_true(effects.emp_pool[0].effect.emitters.is_empty(),"EMP has no duplicate legacy emitter")
	var flak := FlakContact.new()
	add_child_autofree(flak)
	assert_true(flak._particles.is_empty(),"Flak keeps its flash and dust, without separate chips")
	assert_true(flak.has_node("ContactFlash"))
	assert_true(flak.has_node("AbrasionDust"))

func tracer() -> ImpactSparks:
	var burst := ImpactSparks.new()
	add_child_autofree(burst)
	burst.fire(Vector3(0,10,0),Vector3.UP,false,0.0)
	for spark in burst.tracers: spark.max_length=0.05
	burst.set_physics_process(false)
	return burst

func test_cylinders_grow_from_origin_then_shrink_in_twenty_five_milliseconds():
	var burst := tracer()
	var geometry := burst.renderer.multimesh.mesh as CylinderMesh
	assert_almost_eq(geometry.top_radius*2.0,0.01,0.000001)
	assert_almost_eq(geometry.bottom_radius*2.0,0.01,0.000001)
	burst._physics_process(0.01)
	for spark in burst.tracers:
		assert_almost_eq(spark.head.length(),0.02,0.00001,"Every nose travels at 2 m/s")
		assert_almost_eq(spark.length,0.02,0.00001)
		assert_almost_eq(spark.head-spark.direction*spark.length,Vector3.ZERO,Vector3.ONE*0.00001,"Tail starts at the source")
	burst._physics_process(0.015)
	for spark in burst.tracers: assert_almost_eq(spark.length,0.05,0.00001)
	for spark in burst.tracers:
		var transform := burst.cylinder_transform(spark.head,burst.tail_position(spark.path,0.05))
		assert_almost_eq(transform.basis.y.length(),0.05,0.00001,"Length scales along each cylinder's rotated local axis")
		assert_almost_eq(transform.basis.x.length(),1.0,0.00001,"Diameter stays one centimetre in every direction")
		assert_almost_eq(transform.basis.z.length(),1.0,0.00001)
	burst._physics_process(0.475)
	for spark in burst.tracers:
		assert_almost_eq(spark.head.length(),1.0,0.00001)
		assert_almost_eq(spark.length,0.05,0.00001)
	burst._physics_process(0.0125)
	for spark in burst.tracers:
		assert_almost_eq(spark.head.length(),1.0,0.00001,"Nose stays put during absorption")
		assert_almost_eq(spark.length,0.025,0.00001)
	burst._physics_process(0.0125)
	assert_eq(burst.renderer.multimesh.visible_instance_count,0)
	assert_false(burst.visible)
	assert_eq(burst.remaining,0.0)

func test_flower_distribution_covers_all_axes_and_pool_reuses_fixed_capacity():
	var burst := tracer()
	for axis in 3:
		var low := 0.0
		var high := 0.0
		for spark in burst.tracers:
			low=minf(low,spark.direction[axis])
			high=maxf(high,spark.direction[axis])
		assert_lt(low,-0.7)
		assert_gt(high,0.7)
	var mesh := burst.renderer.multimesh.mesh
	burst.fire(Vector3.ONE,Vector3.ZERO,true,8.0,&"welding")
	assert_eq(burst.tracers.size(),16)
	assert_same(burst.renderer.multimesh.mesh,mesh)
	assert_eq(burst.renderer.multimesh.instance_count,32)
	assert_eq(burst.global_position,Vector3.ONE)
	assert_true(burst.global_basis.is_equal_approx(Basis.IDENTITY))

func test_jolt_sweep_stops_the_nose_and_consumes_tail_without_crossing_wall():
	var wall := StaticBody3D.new()
	add_child_autofree(wall)
	wall.position=Vector3(0,1,-0.3)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size=Vector3(2,2,0.02)
	collision.shape=shape
	wall.add_child(collision)
	await wait_physics_frames(2)
	var burst := tracer()
	burst.fire(Vector3(0,1,0),Vector3.UP,false,0.0)
	for spark in burst.tracers: spark.max_length=0.05
	burst.set_physics_process(false)
	burst.tracers.resize(1)
	burst.tracers[0].direction=Vector3.FORWARD
	burst.tracers[0].velocity=Vector3.FORWARD*2.0
	burst.tracers[0].max_length=0.05
	burst.acceleration=Vector3.ZERO
	burst._physics_process(0.14)
	assert_almost_eq(burst.tracers[0].head.z,-0.28,0.0001)
	burst._physics_process(0.01)
	var nose: Vector3=burst.tracers[0].head
	assert_gt(nose.z,-0.29,"The 5 mm nose radius cannot penetrate the wall")
	assert_lt(nose.z,-0.28)
	assert_gte(burst.tracers[0].stop_age,0.14)
	burst._physics_process(0.025)
	assert_eq(burst.tracers[0].head,nose)
	assert_eq(burst.tracers[0].length,0.0)
	assert_false(burst.visible)

func test_gravity_curves_flight_and_random_lengths_remain_between_two_and_five_cm():
	var burst := tracer()
	burst.fire(Vector3(0,10,0),Vector3.UP,false,8.0)
	burst.set_physics_process(false)
	var low := 1.0
	var high := 0.0
	for spark in burst.tracers:
		assert_almost_eq(spark.velocity.length(),2.0,0.00001)
		assert_between(spark.max_length,0.02,0.05)
		low=minf(low,spark.max_length)
		high=maxf(high,spark.max_length)
	assert_gt(high-low,0.01,"A burst contains varied lengths")
	var initial: Vector3=burst.tracers[0].velocity
	burst._physics_process(0.1)
	assert_almost_eq(burst.tracers[0].head,initial*0.1+Vector3.DOWN*0.04,Vector3.ONE*0.00001)
	assert_almost_eq(burst.tracers[0].velocity,initial+Vector3.DOWN*0.8,Vector3.ONE*0.00001)
	for spark in burst.tracers:
		assert_lte(spark.length,spark.max_length+0.00001)
	assert_gt(burst.renderer.custom_aabb.size.y,4.0,"Visibility bounds include the downward gravity arc")
