extends RefCounted
## Threaded I/O plus strong shared resource ownership; instantiated nodes stay
## independent. Keep extraction/scene-tree work on the main thread in batches.
static var resources: Dictionary = {}
static var prepared_animations: Dictionary = {}
static var map_jobs: Dictionary = {}

static func character_animation_paths() -> Array[String]:
	var paths: Array[String]=[]
	var families: Dictionary={}
	for character in ContentRegistry.characters(): families[String(character.animation_family)]=true
	for family in families:
		var pending: Array[String]=["res://assets/animations/"+family]
		while not pending.is_empty():
			var directory: String=pending.pop_back()
			# ResourceLoader also resolves imported/remapped paths in exported PCKs.
			for name in ResourceLoader.list_directory(directory):
				var path: String=directory.path_join(name)
				if name.ends_with("/"): pending.append(path.trim_suffix("/"))
				elif name.ends_with(".glb"): paths.append(path)
	paths.sort()
	return paths

static func prepare_character_animations(tree: SceneTree,paths: Array[String]=[]) -> void:
	if paths.is_empty(): paths=character_animation_paths()
	await preload_paths(tree,paths)
	var batch_started := Time.get_ticks_usec()
	for path in paths:
		var key := path.trim_prefix("res://assets/animations/").trim_suffix(".glb")
		if prepared_animations.has(key): continue
		var family := key.get_slice("/",0)
		if Assets.animation(key.substr(family.length()+1),family)==null:
			push_error("Cannot prepare character animation: "+path)
			continue
		prepared_animations[key]=true
		if Time.get_ticks_usec()-batch_started>8000:
			await tree.process_frame
			batch_started=Time.get_ticks_usec()

static func preload_paths(tree: SceneTree,paths: Array[String]) -> void:
	if DisplayServer.get_name()=="headless":
		# The dummy renderer's mesh RID allocator is not worker-thread safe.
		# Servers/tests have no VRAM upload work; keep this path cooperative.
		var batch_started := Time.get_ticks_usec()
		for path in paths:
			if resources.has(path) or not ResourceLoader.exists(path): continue
			var resource: Resource=load(path)
			resources[path]=resource
			if resource is PackedScene and path.begins_with("res://assets/models/"): Assets.scenes[path]=resource
			if Time.get_ticks_usec()-batch_started>=8000:
				await tree.process_frame
				batch_started=Time.get_ticks_usec()
		return
	var requests: Array[String] = []
	for path in paths:
		if resources.has(path) or not ResourceLoader.exists(path): continue
		if path in requests: continue
		var error := ResourceLoader.load_threaded_request(path)
		if error!=OK:
			push_error("Cannot prepare resource: "+path)
			continue
		requests.append(path)
	while not requests.is_empty():
		for index in range(requests.size()-1,-1,-1):
			var path := requests[index]
			var status := ResourceLoader.load_threaded_get_status(path)
			if status==ResourceLoader.THREAD_LOAD_IN_PROGRESS: continue
			if status==ResourceLoader.THREAD_LOAD_LOADED:
				var resource := ResourceLoader.load_threaded_get(path)
				resources[path]=resource
				if resource is PackedScene and path.begins_with("res://assets/models/"): Assets.scenes[path]=resource
			else: push_error("Resource preparation failed: "+path)
			requests.remove_at(index)
		await tree.process_frame

static func menu(tree: SceneTree) -> void:
	var paths: Array[String]=["res://assets/models/characters/tensor/tensor.glb"]
	var clips: Array[String]=["common/idle"]
	for id in RobotClips.VICTORIES:
		var key: String = "common/"+String(id)
		if ResourceLoader.exists("res://assets/animations/tensor/"+key+".glb"): clips.append(key)
	for clip in clips: paths.append("res://assets/animations/tensor/"+clip+".glb")
	await preload_paths(tree,paths)
	var batch_started := Time.get_ticks_usec()
	for clip in clips:
		if not prepared_animations.has("tensor/"+clip):
			Assets.animation(clip)
			prepared_animations["tensor/"+clip]=true
			if Time.get_ticks_usec()-batch_started>8000:
				await tree.process_frame
				batch_started=Time.get_ticks_usec()

static func match_resources(tree: SceneTree,map_id: String) -> void:
	while map_jobs.get(map_id,"")=="preparing": await tree.process_frame
	if map_jobs.get(map_id,"")=="ready": return
	map_jobs[map_id]="preparing"
	var config: Dictionary=MapCatalog.find(map_id)
	var paths: Array[String]=[]
	var markers: Array=JSON.parse_string(FileAccess.get_file_as_string(config.metadata)).markers
	markers=markers.duplicate()
	markers.append({"category":"maps","asset":config.model})
	for marker in markers:
		if not marker.has("category") or not marker.has("asset"): continue
		var prefix := "res://assets/models/%s/%s/%s%s"%[marker.category,marker.asset,marker.asset,marker.get("asset_suffix","")]
		paths.append(prefix+".glb")
		paths.append(prefix+"_col.glb")
	for name in ["jumbotron","pole_light","sconce_light","batten_light"]:
		paths.append("res://assets/models/environments/%s/%s.glb"%[name,name])
	for name in ["energy_core","shield_core","energy_core_pickup"]:
		paths.append("res://assets/models/gameplay/%s/%s.glb"%[name,name])
	for id in Arsenal.WEAPONS:
		var model: String=Arsenal.WEAPONS[id].model
		for suffix in ["","_col","_ammo","_ammo_col","_rocket","_rocket_col"]:
			paths.append("res://assets/models/weapons/%s/%s%s.glb"%[model,model,suffix])
	# The authoring manifest omits some bundled weapon-family aliases. Prepare
	# the resources the runtime can actually request, including those aliases.
	var animations := character_animation_paths()
	paths.append_array(animations)
	await preload_paths(tree,paths)
	CoreOrb.prepare_energy_materials()
	await prepare_character_animations(tree,animations)
	map_jobs[map_id]="ready"

static func wait_for_rendering(tree: SceneTree,viewport: Viewport,rt_requested: bool,timeout_s := 90.0) -> Dictionary:
	if DisplayServer.get_name()=="headless" or not rt_requested: return {"ready":true,"seconds":0.0}
	if not ClassDB.class_has_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_SCENE_READY"):
		return {"ready":false,"error":"The custom engine needs its rendering-readiness update."}
	var ready_key := ClassDB.class_get_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_SCENE_READY")
	var pending_key := ClassDB.class_get_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_PENDING_MATERIALS")
	var started := Time.get_ticks_msec()
	var stable := 0
	var pending := 0
	while Time.get_ticks_msec()-started<timeout_s*1000:
		await RenderingServer.frame_post_draw
		var ready := RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,ready_key)
		pending=RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,pending_key)
		stable=stable+1 if ready>0 and pending==0 else 0
		if stable>=3: return {"ready":true,"seconds":(Time.get_ticks_msec()-started)/1000.0}
	return {"ready":false,"seconds":(Time.get_ticks_msec()-started)/1000.0,"pending_materials":pending,"error":"Ray tracing did not finish preparing."}
