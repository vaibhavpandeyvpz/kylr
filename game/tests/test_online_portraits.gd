extends GutTest

func test_every_account_choice_has_a_compact_authored_portrait():
	var character := ContentRegistry.character("tensor")
	var paths: Array[String] = []
	for primary in OnlineTransport.PALETTE:
		for head in character.heads: paths.append("heads/"+head+"/"+primary)
		for emote in character.emotes: paths.append("emotes/"+emote+"/"+primary)
		for secondary in OnlineTransport.PALETTE: paths.append("armor/"+primary+"/"+secondary)
	for path in paths:
		var resource := "res://assets/ui/customisation/"+path+".webp"
		assert_true(ResourceLoader.exists(resource),resource)
		if not ResourceLoader.exists(resource): continue
		var texture := load(resource) as Texture2D
		assert_not_null(texture,resource)
		if texture: assert_eq(texture.get_size(),Vector2(192,192),resource)

func test_thumbnail_palette_matches_account_color_identifiers():
	var palette: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/online_palette.json"))
	assert_eq(palette.size(),OnlineTransport.PALETTE.size())
	for key in OnlineTransport.PALETTE:
		assert_eq(palette.get(key,""),OnlineTransport.PALETTE[key],key)
