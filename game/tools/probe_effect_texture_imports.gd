extends SceneTree
## Verify actual GPU-uploaded level-zero data and generated mip chains.
func _initialize() -> void: run.call_deferred()

func run() -> void:
	var gpu := RenderingServer.get_video_adapter_name()
	if not gpu.contains("NVIDIA"):
		push_error("Texture qualification requires the NVIDIA Vulkan renderer")
		quit(2)
		return
	var folder := "res://assets/models/effects/combat_effects/"
	var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(folder+"combat_effects_rig.json"))
	var cloud: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(folder+"rocket_cloud_rig.json"))
	metadata.texture_samples.merge(cloud.texture_samples)
	var passed := true
	for name in ["turbulence_rgba.png","gas_atlas.png","smoke_atlas.png","fireball_atlas.png","rocket_cloud_albedo_height.png","rocket_cloud_normal_roughness.png","flak_dust_atlas.png","fire_contact_atlas.png"]:
		var texture := load(folder+name) as Texture2D
		var image := texture.get_image()
		if image == null or not image.has_mipmaps():
			push_error("Missing imported mip chain: "+name)
			passed = false
			continue
		if image.is_compressed(): image.decompress()
		if metadata.texture_samples.has(name):
			var original := Image.new()
			if original.load_png_from_buffer(FileAccess.get_file_as_bytes(folder+name)) != OK:
				push_error("Cannot decode source data texture: "+name)
				passed = false
				continue
			var base := image.duplicate() as Image
			base.clear_mipmaps()
			if base.get_data() != original.get_data():
				push_error("Imported level-zero data differs from its source: "+name)
				passed = false
			for sample in metadata.texture_samples[name]:
				var color := image.get_pixel(int(sample.pixel[0]),int(sample.pixel[1]))
				for channel in 4:
					if roundi(color[channel]*255.0) != int(sample.rgba8[channel]):
						push_error("Imported data channel changed: "+name)
						passed = false
		print("EFFECT_TEXTURE ",name," size=",image.get_size()," mip_levels=",image.get_mipmap_count())
	print("EFFECT_TEXTURE_IMPORTS passed=",passed," gpu=",gpu)
	quit(0 if passed else 1)
