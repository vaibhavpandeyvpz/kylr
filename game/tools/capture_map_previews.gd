extends SceneTree
## Capture fully assembled map fixtures without spawning robots or HUD.
const Preparation = preload("res://scripts/core/resource_preparation.gd")
var game: ArenaMatch
func _initialize(): run.call_deferred()
func settle(frames: int):
	for frame in frames:
		if is_instance_valid(game) and game.phase=="Active": game.map.tick(1.0/60.0)
		await process_frame
func run():
	root.size=Vector2i(1920,1080)
	root.content_scale_size=Vector2i(1920,1080)
	Engine.max_fps=60
	AudioServer.set_bus_mute(0,true)
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/previews.json"))
	var settings:=Preferences.new("user://map-preview-capture.cfg")
	settings.values=Preferences.DEFAULTS.duplicate(true)
	settings.values.merge(Preferences.QUALITY_PRESETS[3],true)
	settings.values.quality=3
	settings.values.rt_upscaling=false
	for map_id in manifest:
		var requested := ""
		for argument in OS.get_cmdline_user_args():
			if argument.begins_with("--map="): requested=argument.trim_prefix("--map=")
		if requested!="" and requested!=map_id: continue
		game=ArenaMatch.new()
		game.map_id=map_id
		game.match_type="CTF"
		game.online=true
		game.authority=false
		game.fixture_lighting_enabled=true
		game.fixture_shadows_enabled=true
		root.add_child(game)
		while not game.initialization_complete: await process_frame
		assert(game.robots.is_empty())
		game.set_process(false)
		game.camera_rig.host.set_process(false)
		game.map.start_map_assembly()
		game.map.assembly.seek(5.0,true)
		game.map.assembly.pause()
		game.map.start_loadout()
		game.phase="Active"
		for flag in game.flags:
			flag.node.visible=true
			flag.base_effect.configure(game.team_colors[game.flags.find(flag)],false)
		var observer:=Camera3D.new()
		observer.far=500
		observer.attributes=CameraAttributesPractical.new()
		observer.attributes.exposure_multiplier=1.4
		game.add_child(observer)
		observer.make_current()
		game.camera=observer
		settings.apply_rendering(game)
		assert(is_equal_approx(root.scaling_3d_scale,1.0))
		var requested_shot:=0
		for argument in OS.get_cmdline_user_args():
			if argument.begins_with("--shot="): requested_shot=int(argument.trim_prefix("--shot="))
		var index:=0
		for shot in manifest[map_id]:
			index+=1
			if requested_shot>0 and index!=requested_shot: continue
			observer.position=MapCatalog.vector(shot.position)
			observer.look_at(MapCatalog.vector(shot.target))
			observer.fov=float(shot.fov)
			var ready:=await Preparation.wait_for_rendering(self,root,true)
			assert(ready.ready)
			await settle(45)
			await RenderingServer.frame_post_draw
			var directory:=ProjectSettings.globalize_path("res://reports/map-previews/"+map_id)
			DirAccess.make_dir_recursive_absolute(directory)
			assert(root.get_texture().get_image().save_png(directory+"/%02d.png"%index)==OK)
			print("MAP_PREVIEW ",map_id," / ",shot.title," / robots=0 / native resolution")
		game.free()
		game=null
		await settle(3)
	quit()
