extends GutTest

func test_pulse_contact_is_volumetric_and_recycles_without_shared_animation():
	var a := PulseContact.new()
	var b := PulseContact.new()
	add_child_autofree(a)
	add_child_autofree(b)
	assert_almost_eq(a.size_m,0.46,0.00001,"Pulse retains its independent footprint")
	assert_shared_geometry(a,b)
	assert_eq(a._layers.size(),11)
	for entry in a._layers:
		assert_false(entry.node.mesh is QuadMesh,"Every pulse impact layer has depth")
	assert_not_same(a._materials[0],b._materials[0])
	a.fire(Vector3.ZERO,Vector3.UP)
	a._process(0.2)
	assert_true(a.visible)
	assert_eq(b.remaining,0.0)
	a._process(1.0)
	assert_false(a.visible)
	a.fire(Vector3.ONE,Vector3.RIGHT)
	assert_eq(a.global_position,Vector3.ONE)
	assert_almost_eq(a._elapsed,0.0,0.00001)

func test_pulse_tracer_grows_from_muzzle_and_absorbs_at_contact():
	var projectile := Node3D.new()
	add_child_autofree(projectile)
	var tracer := PulseProjectileVisual.new()
	projectile.add_child(tracer)
	assert_false(tracer.visible)
	tracer.update_length(0.1)
	assert_almost_eq(tracer.length_m,0.1,0.00001)
	assert_almost_eq(float(tracer.layers[0].get_instance_shader_parameter("length_m")),0.1,0.00001)
	tracer.update_length(1.0)
	assert_almost_eq(tracer.length_m,0.25,0.00001)
	var contact := Vector3(0,1,-10)
	tracer.absorb(contact,1.0)
	assert_same(tracer.get_parent(),self,"Contact survives projectile deletion")
	assert_eq(tracer.global_position,contact)
	tracer._process(0.125)
	assert_almost_eq(tracer.length_m,0.125,0.00001)
	assert_eq(tracer.global_position,contact,"The nose stays at the hit surface")
	tracer._process(0.125)
	assert_false(tracer.visible)
	assert_true(tracer.is_queued_for_deletion())
	await get_tree().process_frame
	assert_false(is_instance_valid(tracer),"The absorbed tracer releases its nodes")

func test_flak_fragments_share_resources_and_keep_fades_independent():
	var pair: Array[FlakRoundVisual] = []
	for index in 2:
		var visual := FlakRoundVisual.new()
		visual.fragmented = true
		add_child_autofree(visual)
		pair.append(visual)
	assert_same(pair[0]._head.mesh, pair[1]._head.mesh)
	assert_same(pair[0]._head.material_override, pair[1]._head.material_override)
	assert_same(pair[0]._tail.mesh, pair[1]._tail.mesh)
	var envelope: AABB = pair[0]._head.transform * pair[0]._head.mesh.get_aabb()
	for axis in 3:
		assert_lte(envelope.size[axis], FlakRoundVisual.DEFAULT_DIAMETER_M)
	pair[0].set_alpha(0.2)
	assert_almost_eq(float(pair[0]._head.get_instance_shader_parameter("opacity")), 0.2, 0.001)
	assert_almost_eq(float(pair[1]._head.get_instance_shader_parameter("opacity")), 1.0, 0.001)

func test_emp_charge_recycling_resets_fade_transform_and_keeps_live_shots_independent():
	var effects := ArenaEffects.new()
	add_child_autofree(effects)
	var first := Node3D.new()
	var second := Node3D.new()
	add_child_autofree(first)
	add_child_autofree(second)
	var charge := effects.acquire_emp_charge(first)
	var concurrent := effects.acquire_emp_charge(second)
	assert_not_same(charge,concurrent)
	assert_not_same(charge.core_material,concurrent.core_material)
	charge.update_travel(Arsenal.EMP_MAX_RANGE)
	charge.position = Vector3(1,2,3)
	charge.rotation = Vector3(0.2,0.3,0.4)
	assert_false(charge.visible)
	assert_eq(concurrent.core_material.albedo_color.a,1.0)
	effects.recycle_emp_charge(charge)
	assert_same(charge.get_parent(),effects)
	var reused := effects.acquire_emp_charge(second)
	assert_same(reused,charge,"Reuses the complete nodes and materials")
	assert_true(reused.visible)
	assert_eq(reused.position,Vector3.ZERO)
	assert_eq(reused.rotation,Vector3.ZERO)
	assert_eq(reused.scale,Vector3.ONE*EmpCharge.VISUAL_SCALE)
	assert_eq(reused.core_material.albedo_color.a,1.0)
	assert_eq(float(reused.shell_material.get_shader_parameter("opacity")),1.0)
	assert_true(effects.idle_emp_charges.is_empty())

func test_bio_splash_particles_remain_within_one_metre_of_contact():
	var contact := BioContact.new()
	add_child_autofree(contact)
	assert_almost_eq(contact.size_m,0.445,0.00001,"The main bloom keeps its current diameter")
	assert_eq(contact._particles.size(),2)
	for particle in contact._particles:
		var process := particle.process_material as ParticleProcessMaterial
		var lifetime := particle.lifetime
		var travel := process.initial_velocity_max*lifetime+0.5*process.gravity.length()*lifetime*lifetime
		var sprite_radius := particle.draw_pass_1.get_aabb().size.length()*0.5*process.scale_max
		var world_bound := (travel+process.emission_sphere_radius+sprite_radius)*contact.size_m
		assert_lte(world_bound,1.0,"Include the whole sprite and gravity, even before damping slows it")
		assert_gte(process.damping_min,0.0)

func test_impact_primitives_share_geometry_but_not_animated_materials():
	for effect_type in [FlakContact,BioContact]:
		var pair: Array = []
		for index in 2:
			var effect: WeaponContactBurst = effect_type.new()
			add_child_autofree(effect)
			pair.append(effect)
		var first := geometry(pair[0])
		var second := geometry(pair[1])
		for key in first:
			if first[key] is TubeTrailMesh: continue # Curve-backed trails retain their own resource.
			assert_same(first[key],second[key],pair[0].get_class()+" "+key)
			if first[key] is PrimitiveMesh:
				assert_null(first[key].material,"Generated geometry never owns mutable materials")
		assert_gt(pair[0]._materials.size(),0)
		for index in pair[0]._materials.size():
			assert_not_same(pair[0]._materials[index],pair[1]._materials[index])
		var original = pair[1]._materials[0].get_shader_parameter("effect_progress")
		pair[0]._materials[0].set_shader_parameter("effect_progress",0.73)
		assert_eq(pair[1]._materials[0].get_shader_parameter("effect_progress"),original)

func geometry(root: Node) -> Dictionary:
	var result := {}
	for node in root.find_children("*","GeometryInstance3D",true,false):
		var path := String(root.get_path_to(node))
		if node is MeshInstance3D: result[path] = node.mesh
		if node is GPUParticles3D:
			for index in node.draw_passes: result[path+str(index)] = node.get("draw_pass_"+str(index+1))
	return result

func assert_shared_geometry(a: Node, b: Node) -> void:
	var first := geometry(a)
	var second := geometry(b)
	assert_gt(first.size(),0)
	assert_eq(first.keys(),second.keys())
	for key in first: assert_same(first[key],second[key],key+" reuses one mesh resource")

func test_runtime_projectiles_share_geometry_without_sharing_mutable_state():
	for visual_type in [BioProjectileVisual,PulseProjectileVisual]:
		var a: Node3D = visual_type.new()
		var b: Node3D = visual_type.new()
		add_child_autofree(a)
		var count := ProjectileResources.meshes.size()
		add_child_autofree(b)
		assert_eq(ProjectileResources.meshes.size(),count,"Second shot creates no meshes")
		assert_shared_geometry(a,b)
	var flak_a := FlakRoundVisual.new()
	var flak_b := FlakRoundVisual.new()
	add_child_autofree(flak_a)
	add_child_autofree(flak_b)
	assert_shared_geometry(flak_a,flak_b)
	flak_a.set_alpha(.2)
	assert_almost_eq(float(flak_b._head.get_instance_shader_parameter("opacity")),1.0,.0001)
	var emp_a := EmpCharge.new()
	var emp_b := EmpCharge.new()
	add_child_autofree(emp_a)
	add_child_autofree(emp_b)
	assert_shared_geometry(emp_a,emp_b)
	emp_a.update_travel(24.0)
	assert_almost_eq(emp_b.core_material.albedo_color.a,1.0,.0001,"EMP fade stays local")
	var orb_a := LightningOrb.new()
	var orb_b := LightningOrb.new()
	add_child_autofree(orb_a)
	add_child_autofree(orb_b)
	assert_shared_geometry(orb_a,orb_b)
	assert_same(orb_a.get_node("Core").material_override,orb_b.get_node("Core").material_override)
	orb_a.get_node("Core").set_instance_shader_parameter("phase",123.0)
	assert_ne(orb_b.get_node("Core").get_instance_shader_parameter("phase"),123.0)

func test_original_projectile_keeps_shared_meshes_and_isolated_palette():
	var a := FireOrb.new()
	var b := FireOrb.new()
	add_child_autofree(a)
	add_child_autofree(b)
	assert_shared_geometry(a,b)
	var first := PackVfx.materials(a.composition)
	var second := PackVfx.materials(b.composition)
	assert_gt(first.size(),0)
	var original = second[0].get_shader_parameter("primary_color")
	first[0].set_shader_parameter("primary_color",Color.MAGENTA)
	assert_eq(second[0].get_shader_parameter("primary_color"),original)

func test_mesh_recipe_does_not_alias_different_projectile_sizes():
	var small := ProjectileResources.primitive(&"SphereMesh",{"radius":.1,"height":.2})
	var large := ProjectileResources.primitive(&"SphereMesh",{"radius":.2,"height":.4})
	assert_not_same(small,large)
	assert_same(small,ProjectileResources.primitive(&"SphereMesh",{"radius":.1,"height":.2}))

func test_bio_particle_recipes_share_resources_but_keep_simulation_and_variants_separate():
	var visual := BioProjectileVisual.new()
	autofree(visual)
	var a := visual._build_poison_core_rays()
	var b := visual._build_poison_core_rays()
	add_child_autofree(a)
	add_child_autofree(b)
	assert_same(a.process_material,b.process_material)
	assert_same(a.material_override,b.material_override)
	assert_same(a.draw_pass_1,b.draw_pass_1)
	a.speed_scale=0.4
	a.emitting=false
	assert_almost_eq(b.speed_scale,1.0,0.00001)
	assert_true(b.emitting)
	var original_radius: float = b.process_material.emission_sphere_radius
	visual.model_size *= 2.0
	visual.vfx_primary_color=Color.GREEN
	visual.vfx_secondary_color=Color.BLUE
	var variant := visual._build_poison_core_rays()
	add_child_autofree(variant)
	assert_not_same(b.process_material,variant.process_material)
	assert_not_same(b.process_material.color_ramp,variant.process_material.color_ramp)
	assert_not_same(b.material_override,variant.material_override)
	assert_not_same(b.draw_pass_1,variant.draw_pass_1)
	assert_almost_eq(b.process_material.emission_sphere_radius,original_radius,0.00001)
	assert_almost_eq(variant.process_material.emission_sphere_radius,original_radius*2,0.00001)
	assert_eq(variant.process_material.color_ramp.gradient.colors[1],Color(0,1,0,0.95))
