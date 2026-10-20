extends GutTest
const Preparation=preload("res://scripts/core/resource_preparation.gd")

func test_preparation_covers_manifest_listed_projectile_weapon_clips():
	var ids: Array[String]=["bio_rifle/crouch_walk_backward_right","flak_cannon/crouch_walk_backward_right","grenade_launcher/sprint_forward"]
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/animations/manifest.json"))
	var paths := Preparation.character_animation_paths()
	for id in ids:
		assert_true(manifest.has(id),"Runtime weapon clips must be available to clean CI installations")
		assert_has(paths,"res://assets/animations/tensor/"+id+".glb")
		Preparation.prepared_animations.erase("tensor/"+id)
		Assets.animations.erase("tensor/"+id)
	await Preparation.prepare_character_animations(get_tree())
	var previous_profile := Assets.profile_loads
	var previous_stats := Assets.load_stats.duplicate(true)
	Assets.profile_loads=true
	Assets.load_stats.clear()
	for id in ids:
		assert_true(Preparation.prepared_animations.has("tensor/"+id))
		var clip := Assets.animation(id)
		assert_not_null(clip)
		assert_same(clip,Assets.animation(id),"Prepared clips retain stable shared resource identity")
	assert_true(Assets.load_stats.is_empty(),"First gameplay requests must already hit the prepared cache")
	Assets.profile_loads=previous_profile
	Assets.load_stats=previous_stats
