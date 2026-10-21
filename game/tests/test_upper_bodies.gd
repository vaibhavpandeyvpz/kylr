extends GutTest

class HitOwner extends RefCounted:
	var head := "projector"
	var upper_body := "default"
	var hit_rids: Array[RID] = []

func test_upper_bodies_swap_independently_of_heads_and_preserve_paint():
	var visual := Assets.model("characters","tensor")
	add_child_autofree(visual)
	var catalog := ContentRegistry.character("tensor")
	assert_eq(catalog.upper_bodies.size(),6)
	for upper in catalog.upper_bodies:
		for head in catalog.heads:
			for dark in [false,true]:
				Assets.paint(visual,Color.RED,Color.BLUE,head,dark,upper)
				var shown_upper := 0
				var shown_heads := 0
				for mesh: MeshInstance3D in visual.find_children("*","MeshInstance3D",true,false):
					if not mesh.visible: continue
					if String(mesh.name).begins_with("SK_TensorUpperBody"):
						shown_upper += 1
						assert_true(String(mesh.name).to_lower().ends_with(upper))
						for surface in mesh.mesh.get_surface_count():
							var material := mesh.get_active_material(surface) as StandardMaterial3D
							if material == null: continue
							var role := Assets.material_role(material.resource_name)
							if role == "M_Primary": assert_eq(material.albedo_color,Color.RED)
							if role == "M_Secondary": assert_eq(material.albedo_color,Color.BLUE)
					if String(mesh.name).begins_with("SK_TensorHead"):
						shown_heads += 1
						assert_true(String(mesh.name).to_lower().ends_with(head))
				assert_eq(shown_upper,1)
				assert_eq(shown_heads,1)
	# Release per-instance finishes while their mesh nodes still exist, then
	# let the rendering server retire those overrides before GUT frees the tree.
	for mesh: MeshInstance3D in visual.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			mesh.set_surface_override_material(surface,null)
	await get_tree().process_frame

func test_only_equipped_upper_body_installs_hit_geometry():
	for upper in ContentRegistry.character("tensor").upper_bodies:
		var owner := HitOwner.new()
		owner.upper_body = upper
		var visual := Assets.model("characters","tensor")
		add_child_autofree(visual)
		CollisionRig.install(visual,"characters","tensor",owner)
		var upper_shapes := 0
		for collision in visual.find_children("*","StaticBody3D",true,false):
			var mesh := String(collision.get_meta("hit_mesh",""))
			if mesh.begins_with("SK_TensorUpperBody"):
				upper_shapes += 1
				assert_true(mesh.trim_suffix("Col").to_lower().ends_with(upper))
		assert_gt(upper_shapes,0)

func test_selected_upper_body_is_in_authoritative_actor_snapshots():
	var robot := ArenaRobot.new()
	autofree(robot)
	for upper in ContentRegistry.character("tensor").upper_bodies:
		robot.upper_body = upper
		assert_eq(robot.snapshot().upper_body,upper)
