extends GutTest

func test_map_photographs_cover_both_maps_at_compact_runtime_resolution():
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/previews.json"))
	for map in MapCatalog.all():
		assert_true(manifest.has(map.id))
		if not manifest.has(map.id): continue
		assert_eq(manifest[map.id].size(),5)
		for shot in manifest[map.id]:
			var texture:=load(shot.image) as Texture2D
			assert_not_null(texture)
			if texture: assert_eq(texture.get_size(),Vector2(1280,720))

func test_cycle_manual_selection_and_reduced_motion_keep_the_selected_map():
	var preview:=MapPreview.new()
	preview.map_id="faceoff"
	add_child_autofree(preview)
	preview.set_process(false)
	assert_eq(preview.selected,0)
	preview._process(1.99)
	assert_eq(preview.selected,0)
	preview._process(0.01)
	assert_eq(preview.selected,1)
	preview.selectors[4].pressed.emit()
	assert_eq(preview.selected,4)
	preview._process(2.0)
	assert_eq(preview.selected,0)
	preview.reduced_motion=true
	preview._process(10.0)
	assert_eq(preview.selected,0)
	preview.selectors[2].pressed.emit()
	assert_eq(preview.selected,2)
	var other:=MapPreview.new()
	other.map_id="skyfall"
	add_child_autofree(other)
	other.set_process(false)
	assert_eq(other.selected,0)
	assert_ne(preview.photograph.texture,other.photograph.texture)
