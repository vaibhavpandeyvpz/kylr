extends Node
## Regression for resource loaders exhausting the pool while awaiting shaders.
## Prepare with the dummy renderer, then run graphically with one worker and
## shader caching disabled. Use an external timeout: the regression can block
## the main thread as well as every resource-loading worker.
const MESH_COUNT := 16
var directory := ""
var prepare := false
var retained: Array[Resource] = []

func _ready(): run.call_deferred()

func quit(code: int = 0):get_tree().quit(code)

func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--directory="):directory=argument.trim_prefix("--directory=")
		if argument=="--prepare":prepare=true
	if directory.is_empty() or not directory.is_absolute_path():
		push_error("Provide an absolute fixture directory");quit(2);return
	if prepare:
		if DirAccess.make_dir_recursive_absolute(directory)!=OK:quit(3);return
		for index in MESH_COUNT:
			var mesh:=ArrayMesh.new()
			var arrays:=[]
			arrays.resize(Mesh.ARRAY_MAX)
			arrays[Mesh.ARRAY_VERTEX]=PackedVector3Array([Vector3.ZERO,Vector3.RIGHT,Vector3.UP])
			arrays[Mesh.ARRAY_NORMAL]=PackedVector3Array([Vector3.BACK,Vector3.BACK,Vector3.BACK])
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			var shader:=Shader.new()
			shader.code="shader_type spatial; void fragment() { ALBEDO = vec3(%f, 0.25, 0.5); }" % (0.1+index*0.04)
			var material:=ShaderMaterial.new()
			material.shader=shader
			mesh.surface_set_material(0,material)
			if ResourceSaver.save(mesh,directory.path_join("mesh-%d.res"%index))!=OK:quit(4);return
		print("THREADED_SHADER_LOADING_PREPARED meshes=",MESH_COUNT)
		quit();return
	if DisplayServer.get_name()=="headless" or RenderingServer.get_current_rendering_method()!="forward_plus":
		push_error("Run the verification with the graphical Forward+ renderer");quit(5);return
	if int(ProjectSettings.get_setting("threading/worker_pool/max_threads",-1))!=1 or bool(ProjectSettings.get_setting("rendering/shader_compiler/shader_cache/enabled",true)):
		push_error("The regression requires one worker and disabled shader caching");quit(6);return
	var paths:Array[String]=[]
	for index in MESH_COUNT:
		var path:=directory.path_join("mesh-%d.res"%index)
		if ResourceLoader.load_threaded_request(path,"ArrayMesh",false,ResourceLoader.CACHE_MODE_IGNORE)!=OK:quit(7);return
		paths.append(path)
	var deadline:=Time.get_ticks_msec()+120000
	while not paths.is_empty():
		for index in range(paths.size()-1,-1,-1):
			var status:=ResourceLoader.load_threaded_get_status(paths[index])
			if status==ResourceLoader.THREAD_LOAD_FAILED:quit(8);return
			if status==ResourceLoader.THREAD_LOAD_LOADED:
				var mesh:=ResourceLoader.load_threaded_get(paths[index]) as ArrayMesh
				if mesh==null or mesh.get_surface_count()!=1:quit(9);return
				retained.append(mesh)
				paths.remove_at(index)
		if Time.get_ticks_msec()>deadline:push_error("Threaded shader loading timed out");quit(10);return
		await get_tree().process_frame
	print("THREADED_SHADER_LOADING_PASS meshes=",retained.size()," workers=1")
	retained.clear()
	quit()
