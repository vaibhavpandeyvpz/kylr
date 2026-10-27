class_name RobotCorpse
extends RefCounted
## Shared construction and replication of animated and broken-apart corpses.
## Match rules continue to own expiry, respawn, credit and Energy Core drops.

static func create(world: ArenaMatch, robot: ArenaRobot, placement: Transform3D, clip: String, breakup: Dictionary = {}, settled := false) -> Node3D:
	if not breakup.is_empty():
		var debris := RobotDebris.new()
		debris.name = "death_explode"
		world.add_child(debris)
		debris.global_transform = placement
		debris.build(robot, breakup, world.corpse_materials, not (world.replicating and world.authority and DisplayServer.get_name() == "headless"))
		return debris
	# A corpse owns a fresh visual and animation clock, without live hit bodies,
	# hit overlays or actor-local material ownership copied into its lifecycle.
	var corpse := Assets.model("characters", robot.character.model)
	world.add_child(corpse)
	corpse.show()
	corpse.global_transform = placement
	for mesh: MeshInstance3D in corpse.find_children("*", "MeshInstance3D", true, false):
		var source := robot.body.get_node(corpse.get_path_to(mesh)) as MeshInstance3D
		mesh.visible = source.visible
		for surface in mesh.mesh.get_surface_count():
			mesh.set_surface_override_material(surface, Assets.extinguished_material(source.get_active_material(surface), world.corpse_materials))
		mesh.material_overlay = null
		if String(mesh.name).begins_with("SK_TensorShield"): mesh.hide()
	ShadowBatch.install(corpse)
	var skeleton := Assets.find(corpse, "Skeleton3D") as Skeleton3D
	var animator := AnimationPlayer.new()
	animator.name = "RuntimeAnimator"
	skeleton.get_parent().add_child(animator)
	animator.root_node = NodePath("..")
	var library := AnimationLibrary.new()
	var key := "common_" + clip
	library.add_animation(key, Assets.playback_animation("common/" + clip, robot.character.animation_family, clip != "falling", false))
	animator.add_animation_library("", library)
	animator.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	animator.play(key, 0.0)
	animator.advance(0.0)
	if settled:
		animator.seek(animator.current_animation_length, true, true)
		animator.pause()
	return corpse

static func snapshot(corpse: Node3D) -> Dictionary:
	var animator := corpse.find_child("RuntimeAnimator", true, false) as AnimationPlayer
	return {"transform":corpse.global_transform, "animation":animator.current_animation if animator else "",
		"frame":animator.current_animation_position if animator and animator.current_animation != "" else 0.0,
		"breakup":corpse.snapshot() if corpse is RobotDebris else {}}

static func from_snapshot(world: ArenaMatch, robot: ArenaRobot, state: Dictionary) -> Node3D:
	var breakup: Dictionary = state.get("breakup", {})
	var clip: String = state.animation.trim_prefix("common_")
	var corpse := create(world, robot, state.transform, clip, breakup.get("recipe", {}))
	if corpse is RobotDebris: corpse.restore(breakup.bodies)
	apply_snapshot(corpse, state)
	return corpse

static func apply_snapshot(corpse: Node3D, state: Dictionary) -> void:
	if corpse is RobotDebris: return
	corpse.global_transform = state.transform
	var animator := corpse.find_child("RuntimeAnimator", true, false) as AnimationPlayer
	if animator and state.animation != "":
		animator.play(state.animation)
		animator.seek(state.frame, true)
		animator.pause()
