extends SceneTree
## Run headless with --verbose. Compare default (unclaimed completed requests)
## with -- --drain. Neither case should leak load tokens at engine shutdown.
const REQUESTS = 24

func _initialize(): run.call_deferred()

func run():
	var paths: Array[String] = []
	var directory := "user://threaded-load-shutdown"
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		quit(2)
		return
	for index in REQUESTS:
		if "--nested" in OS.get_cmdline_user_args():
			var leaf:=directory.path_join("leaf-%d.gd"%index)
			var dependency:=directory.path_join("dependency-%d.gd"%index)
			var scene:=directory.path_join("scene-%d.tscn"%index)
			FileAccess.open(leaf,FileAccess.WRITE).store_string("extends RefCounted\nconst VALUE = %d\n"%index)
			FileAccess.open(dependency,FileAccess.WRITE).store_string('extends Node\nconst DATA = preload("%s")\n'%leaf)
			FileAccess.open(scene,FileAccess.WRITE).store_string('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="%s" id="1"]\n\n[node name="Root" type="Node"]\nscript = ExtResource("1")\n'%dependency)
			paths.append(scene)
			continue
		var path := directory.path_join("resource-%d.tres" % index)
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file == null:
			quit(3)
			return
		file.store_string('[gd_resource type="Resource" format=3]\n\n[resource]\nresource_name = "Shutdown resource %d"\n' % index)
		file.close()
		paths.append(path)
	for path in paths:
		if ResourceLoader.load_threaded_request(path) != OK:
			quit(4)
			return
	if "--inflight" in OS.get_cmdline_user_args():
		print("THREADED_LOAD_SHUTDOWN_READY requests=%d in_flight=true" % REQUESTS)
		quit()
		return
	var deadline := Time.get_ticks_msec() + 10000
	while true:
		var complete := true
		for path in paths:
			var status := ResourceLoader.load_threaded_get_status(path)
			if status == ResourceLoader.THREAD_LOAD_FAILED:
				quit(5)
				return
			complete = complete and status == ResourceLoader.THREAD_LOAD_LOADED
		if complete:
			break
		if Time.get_ticks_msec() > deadline:
			quit(6)
			return
		await process_frame
	var drain := "--drain" in OS.get_cmdline_user_args()
	if drain:
		for path in paths:
			var resource := ResourceLoader.load_threaded_get(path)
			if resource == null:
				quit(7)
				return
	print("THREADED_LOAD_SHUTDOWN_READY requests=%d drained=%s" % [REQUESTS, drain])
	quit()
