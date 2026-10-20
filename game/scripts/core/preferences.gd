class_name Preferences
extends RefCounted
const DEFAULTS = {"tutorial_hints":true,"map":"skyfall","name":"","type":0,"difficulty":1,"count":10,"goal":25,"minutes":15,"mode":"Instant Action","online_type":0,"third_person":false,
	"sensitivity":0.0022,"fov":60.0,"fov_version":1,"master":1.0,"effects":1.0,"music":0.6,"interface":1.0,"announcer":1.0,"voices":1.0,"reduced_audio_range":false,"hud_scale":1.0,"reduced_motion":false,"contrast":false,"subtitles":true,"invert":false,
	"display_mode":0,"resolution":Vector2i(1280,720),"quality":1,"quality_version":1,"quality_benchmarked":false,"separate_rendering_thread":false,"rt_denoiser":0,"rt_upscaling":true,"ray_tracing":false,"fixture_lighting":false,"shadows":true,"ambient_occlusion":false,"bloom":true,"antialiasing":1,"sprint_blur":0.35,"speed_lines":true,"callouts":0}
const QUALITY_PRESETS = [
	{"shadows":false,"ambient_occlusion":false,"bloom":false,"antialiasing":0,"ray_tracing":false,"fixture_lighting":false},
	{"shadows":true,"ambient_occlusion":false,"bloom":true,"antialiasing":1,"ray_tracing":false,"fixture_lighting":false},
	{"shadows":true,"ambient_occlusion":true,"bloom":true,"antialiasing":2,"ray_tracing":false,"fixture_lighting":true},
	{"shadows":true,"ambient_occlusion":true,"bloom":true,"antialiasing":3,"ray_tracing":true,"rt_denoiser":0,"rt_upscaling":true,"fixture_lighting":true}]
const CUSTOM_QUALITY := 4
const RENDERER_SETTINGS_PATH := "user://renderer.cfg"
const OFFLINE_COUNTS = [2,4,6,8,10]
const DENOISER_DLSS := 0
var setup_notices: Array[String] = []
var storage_path := "user://preferences.cfg"
var values := DEFAULTS.duplicate(true)
const DEFAULT_BINDINGS := {"forward":KEY_W,"backward":KEY_S,"left":KEY_A,"right":KEY_D,"jump":KEY_SPACE,"charged_jump":KEY_Q,"sprint":KEY_CTRL,"walk":KEY_SHIFT,"crouch":KEY_C,"reload":KEY_R,"view":KEY_V,"pistol":KEY_1,"pickup":KEY_2,"scoreboard":KEY_TAB,"fire":-MOUSE_BUTTON_LEFT,"secondary":-MOUSE_BUTTON_RIGHT}
var bindings := DEFAULT_BINDINGS.duplicate()

static func read_bindings(config: ConfigFile) -> Dictionary:
	var result := DEFAULT_BINDINGS.duplicate()
	for key in result: result[key] = config.get_value("bindings",key,result[key])
	if not config.has_section_key("bindings","walk") and config.has_section_key("bindings","sprint"):
		result.walk = config.get_value("bindings","sprint",KEY_SHIFT)
		result.sprint = KEY_ALT if result.walk == KEY_CTRL else KEY_CTRL
	return result

static func valid_name(value: String) -> bool:
	var regex := RegEx.new()
	regex.compile("^[A-Za-z0-9._]{1,20}$")
	var found := regex.search(value)
	return found != null and found.get_string() == value

func _init(path := "user://preferences.cfg"):
	storage_path = path
	var config := ConfigFile.new()
	if config.load(storage_path) == OK:
		for key in values: values[key] = config.get_value("preferences",key,values[key])
		# Index 3 used to mean Custom, never silently opt old saves into Ultra.
		if not config.has_section_key("preferences","quality_version") and int(values.quality)==3: values.quality=CUSTOM_QUALITY
		if not config.has_section_key("preferences","fov_version") and is_equal_approx(float(values.fov),78.0): values.fov = 60.0
		if not config.has_section_key("preferences","ray_tracing"): values.ray_tracing=int(values.quality)==3
		bindings = read_bindings(config)
	values.rt_denoiser=DENOISER_DLSS
	if not config.has_section_key("preferences","resolution"): values.resolution=resolutions().back()
	var previous_count := int(values.count)
	values.count = clampi(int(ceil(previous_count / 2.0)) * 2,2,10)
	if previous_count != values.count: setup_notices.append("Saved robot count reset to %d." % values.count)
	for option in [["goal",1,999],["minutes",5,60],["difficulty",0,3],["type",0,2]]:
		var key: String = option[0]
		var previous := int(values[key])
		values[key] = clampi(previous,option[1],option[2])
		if previous != values[key]: setup_notices.append("Saved %s was unavailable and has been reset." % key)
	for option in [["display_mode",0,2],["quality",0,4],["antialiasing",0,3],["callouts",0,2]]:
		values[option[0]] = clampi(int(values[option[0]]),option[1],option[2])
	# Restore the current High preset; individual lighting choices use Custom.
	if int(values.quality)==2:
		values.fixture_lighting=true
		values.shadows=true
	for option in [["fov",60.0,100.0],["hud_scale",0.8,1.4],["sprint_blur",0.0,1.0],["sensitivity",0.0005,0.006]]:
		values[option[0]] = clampf(float(values[option[0]]),option[1],option[2])
	if typeof(values.resolution) != TYPE_VECTOR2I or not values.resolution in resolutions(): values.resolution=resolutions().back()
	apply()

func apply():
	ArenaMix.configure(values.reduced_audio_range)
	for key in bindings:
		if not InputMap.has_action(key): InputMap.add_action(key)
		InputMap.action_erase_events(key)
		var event: InputEvent
		if int(bindings[key]) < 0:
			event = InputEventMouseButton.new()
			event.button_index = -int(bindings[key])
		else:
			event = InputEventKey.new()
			event.physical_keycode = bindings[key]
		InputMap.action_add_event(key,event)
	for bus in ["Effects","Music","Interface"]:
		if AudioServer.get_bus_index(bus) < 0:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.bus_count-1,bus)
	AudioServer.set_bus_volume_db(0,linear_to_db(values.master))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Effects"),linear_to_db(values.effects))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"),linear_to_db(values.music))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Interface"),linear_to_db(values.interface))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Announcer"),linear_to_db(values.announcer))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Voices"),linear_to_db(values.voices))

static func binding_text(value: int) -> String:
	return "Mouse %d" % -value if value < 0 else OS.get_keycode_string(value)

static func resolutions() -> Array[Vector2i]:
	var native := DisplayServer.screen_get_size()
	var result: Array[Vector2i] = []
	for size in [Vector2i(800,600),Vector2i(960,540),Vector2i(1024,768),Vector2i(1280,720),Vector2i(1600,900),Vector2i(1920,1080),Vector2i(2560,1440),Vector2i(3840,2160)]:
		if size.x <= native.x and size.y <= native.y: result.append(size)
	if native.x > 0 and native.y > 0 and not native in result: result.append(native)
	if result.is_empty(): result.append(Vector2i(1280,720))
	return result

func apply_display(options: Dictionary = {}):
	if options.is_empty(): options = values
	if DisplayServer.get_name() == "headless": return
	var mode := clampi(int(options.display_mode),0,2)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if mode == 0 else DisplayServer.WINDOW_MODE_FULLSCREEN if mode == 1 else DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN)
	if mode == 0:
		var size: Vector2i = options.resolution
		var usable := DisplayServer.screen_get_usable_rect()
		size = size.min(usable.size)
		DisplayServer.window_set_size(size)
		DisplayServer.window_set_position(usable.position + (usable.size-size)/2)

static func ray_tracing_unavailable_reason(requested: int = -1) -> String:
	var reason:=ray_tracing_hardware_unavailable_reason()
	if not reason.is_empty():return reason
	var capabilities:=rt_denoiser_capabilities()
	if not capabilities.dlss:
		return "DLSS Ray Reconstruction is not supported by this device, driver or installed runtime."
	if requested!=-1 and requested!=DENOISER_DLSS:
		return "The selected ray-tracing denoiser is unavailable on this build."
	return ""

static func ray_tracing_hardware_unavailable_reason() -> String:
	if DisplayServer.get_name() == "headless": return "Ray tracing is unavailable without a graphical display."
	if RenderingServer.get_current_rendering_method() != "forward_plus": return "Ray tracing requires the Forward+ renderer."
	if not ClassDB.class_has_method("Environment","set_pathtracing_enabled"): return "Ray tracing requires the KYLR RTX engine."
	var device := RenderingServer.get_rendering_device()
	if device == null or not device.has_feature(RenderingDevice.SUPPORTS_RAYTRACING_PIPELINE):
		return "This graphics device or driver does not support hardware ray tracing."
	return ""

static func rt_denoiser_capabilities() -> Dictionary:
	var dlss:bool=Engine.has_singleton("Streamline") and Engine.get_singleton("Streamline").get_capability(2)
	return {"dlss":dlss}

static func resolve_rt_denoiser(requested: int, capabilities: Dictionary) -> int:
	if requested==DENOISER_DLSS and capabilities.dlss:return DENOISER_DLSS
	return -1

static func active_renderer_label(target: Node) -> String:
	if DisplayServer.get_name()=="headless":return "Headless"
	var worlds:=target.find_children("*","WorldEnvironment",true,false)
	var active_match=target.get("match_node")
	if is_instance_valid(active_match) and not target.is_ancestor_of(active_match):
		worlds.append_array(active_match.find_children("*","WorldEnvironment",true,false))
	for world in worlds:
		var environment:Environment=world.environment
		if environment==null or not environment.has_method("set_pathtracing_enabled") or not environment.get("pathtracing_enabled"):continue
		var backend:="DLSS Ray Reconstruction" if int(environment.get("pathtracing_denoiser"))==1 else "Unfiltered path tracing"
		var viewport:Viewport=world.get_viewport()
		if ClassDB.class_has_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_SCENE_READY"):
			var ready_key:=ClassDB.class_get_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_SCENE_READY")
			if RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,ready_key)==0:return "Preparing "+backend
		return backend+" / "+("native resolution" if is_equal_approx(viewport.scaling_3d_scale,1.0) else str(roundi(viewport.scaling_3d_scale*100))+"% internal resolution")
	return "Raster"

func _apply_viewport_rendering(viewport: Viewport, rt_enabled: bool):
	viewport.set_meta("effect_quality",int(values.quality))
	var denoiser:=resolve_rt_denoiser(int(values.rt_denoiser),rt_denoiser_capabilities()) if rt_enabled else -1
	var dlss:=rt_enabled and denoiser==DENOISER_DLSS
	viewport.msaa_3d = Viewport.MSAA_DISABLED if rt_enabled else clampi(int(values.antialiasing),0,3)
	viewport.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS if dlss else Viewport.SCALING_3D_MODE_BILINEAR
	viewport.scaling_3d_scale = 0.5 if dlss and values.rt_upscaling else 1.0
	viewport.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
	if rt_enabled:viewport.use_taa=false

func _restore_authored_environment_gi(env: Environment):
	# Preserve authored lighting in every preset. Restore live environments that
	# still carry a snapshot from the earlier Ultra RT override.
	if env.has_meta("quality_raster_gi"):
		var original: Dictionary = env.get_meta("quality_raster_gi")
		for property in original: env.set(property, original[property])
		env.remove_meta("quality_raster_gi")

func _apply_environment_reflections(env: Environment, rt_enabled: bool):
	var disable_maps := rt_enabled and bool(values.fixture_lighting)
	if disable_maps:
		if not env.has_meta("quality_reflection_maps"):
			var original := {"source": env.reflected_light_source}
			if env.sky and env.sky.sky_material is ShaderMaterial:
				var material := env.sky.sky_material as ShaderMaterial
				if material.shader != null and material.shader.resource_path == "res://shaders/original/lunar_sky.gdshader":
					original["material"] = material
					for parameter in ["reflection_fill_energy", "reflection_detail_strength", "reflection_panorama"]:
						original[parameter] = material.get_shader_parameter(parameter)
			env.set_meta("quality_reflection_maps", original)
		var original: Dictionary = env.get_meta("quality_reflection_maps")
		env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
		if original.has("material"):
			var material: ShaderMaterial = original.material
			# RT misses still see the authored cosmic sky, without the artificial
			# chrome panorama that is only meant to fill raster reflections.
			material.set_shader_parameter("reflection_fill_energy", 0.0)
			material.set_shader_parameter("reflection_detail_strength", 0.0)
			material.set_shader_parameter("reflection_panorama", null)
	elif env.has_meta("quality_reflection_maps"):
		var original: Dictionary = env.get_meta("quality_reflection_maps")
		env.reflected_light_source = original.source
		if original.has("material"):
			var material: ShaderMaterial = original.material
			for parameter in ["reflection_fill_energy", "reflection_detail_strength", "reflection_panorama"]:
				material.set_shader_parameter(parameter, original[parameter])
		env.remove_meta("quality_reflection_maps")

func apply_rendering(target: Node):
	if target == null: return
	if target is ArenaMatch:
		target.fixture_lighting_enabled=bool(values.fixture_lighting)
		target.fixture_shadows_enabled=bool(values.shadows)
	# Online matches are mounted beside the app under the transport.
	var active_match = target.get("match_node")
	if is_instance_valid(active_match):
		active_match.fixture_lighting_enabled=bool(values.fixture_lighting)
		active_match.fixture_shadows_enabled=bool(values.shadows)
	if is_instance_valid(active_match) and not target.is_ancestor_of(active_match): apply_rendering(active_match)
	var rt_enabled := bool(values.ray_tracing) and ray_tracing_unavailable_reason(int(values.rt_denoiser)).is_empty()
	if target.get_meta("menu_studio_host",false) and not is_instance_valid(active_match): rt_enabled=false
	_apply_viewport_rendering(target.get_viewport(),rt_enabled)
	for effect in target.find_children("*","Node3D",true,false):
		if effect is OriginalEffect: effect.set_detail(int(values.quality))
	for environment in target.find_children("*","WorldEnvironment",true,false):
		if environment.environment == null: continue
		_apply_viewport_rendering(environment.get_viewport(),rt_enabled)
		var env: Environment = environment.environment
		_restore_authored_environment_gi(env)
		_apply_environment_reflections(env, rt_enabled)
		if env.has_method("set_pathtracing_enabled"):
			env.set("pathtracing_samples_per_pixel",1)
			env.set("pathtracing_max_bounces",3)
			env.set("pathtracing_denoiser",1)
			env.set("pathtracing_enabled",rt_enabled)
		if env.sky and env.sky.sky_material is ShaderMaterial:
			var sky_material := env.sky.sky_material as ShaderMaterial
			if sky_material.shader.resource_path == "res://shaders/original/lunar_sky.gdshader":
				sky_material.set_shader_parameter("reduced_motion", values.reduced_motion)
		if not environment.has_meta("quality_ao"):
			environment.set_meta("quality_ao",env.ssao_enabled)
			environment.set_meta("quality_bloom",env.glow_enabled)
		env.ssao_enabled = not rt_enabled and values.ambient_occlusion and bool(environment.get_meta("quality_ao"))
		env.glow_enabled = values.bloom and bool(environment.get_meta("quality_bloom"))
	for light in target.find_children("*","Light3D",true,false):
		if light.get_meta("fixture_light",false):
			FixtureLighting.configure(light,bool(values.fixture_lighting),bool(values.shadows))
			continue
		if not light.has_meta("quality_shadow"): light.set_meta("quality_shadow",light.shadow_enabled)
		light.shadow_enabled = values.shadows and bool(light.get_meta("quality_shadow"))

static func render_thread_restart_required(enabled: bool) -> bool:
	if DisplayServer.get_name()=="headless": return false
	# This queries the actual server thread, including command-line overrides.
	return enabled == RenderingServer.is_on_render_thread()

func save_rendering_startup(path: String = RENDERER_SETTINGS_PATH) -> Error:
	var startup:=ConfigFile.new()
	startup.set_value("rendering","driver/threads/thread_model",2 if values.separate_rendering_thread else 1)
	return startup.save(path)

func save() -> Error:
	var config := ConfigFile.new()
	for key in values: config.set_value("preferences",key,values[key])
	for key in bindings: config.set_value("bindings",key,bindings[key])
	var error:=config.save(storage_path)
	if error!=OK: return error
	# Isolated tests/tools must not change the player's next launch.
	return save_rendering_startup() if storage_path=="user://preferences.cfg" else OK
