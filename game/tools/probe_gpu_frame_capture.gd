extends SceneTree
## Pixel-exact capture control, followed by the same sequence without readback.
const Capture=preload("gpu_frame_capture.gd")
var output:=""

func _initialize():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
	run.call_deferred()

func wait_state(capture,key:String):
	for frame in 300:
		var state:Dictionary=capture.stats()
		if not String(state.error).is_empty() or state.get(key,false):return
		await process_frame;await RenderingServer.frame_post_draw
	push_error("GPU frame-capture fixture deadline");quit(8)

func run():
	if output.is_empty() or FileAccess.file_exists(output):quit(2);return
	create_timer(120).timeout.connect(func():push_error("GPU_FRAME_CAPTURE_TIMEOUT");quit(8))
	root.size=Vector2i(64,64)
	var quad:=ColorRect.new();quad.size=Vector2(64,64)
	var shader:=Shader.new();shader.code="shader_type canvas_item; render_mode unshaded; uniform float phase=0.; void fragment(){COLOR=vec4(UV.x,UV.y,phase,1.);}"
	var material:=ShaderMaterial.new();material.shader=shader;quad.material=material;root.add_child(quad)
	for frame in 4:await process_frame;await RenderingServer.frame_post_draw
	var expected:Array[Image]=[]
	var rows:Array=[];var valid:=true
	for phase in ["paired","deferred"]:
		var capture:=Capture.new();capture.prepare(root.get_texture().get_rid(),8)
		await wait_state(capture,"ready")
		if not String(capture.stats().error).is_empty():valid=false;capture.release();await wait_state(capture,"released");break
		for index in 8:
			material.set_shader_parameter("phase",float(index)/7.)
			await process_frame;await RenderingServer.frame_post_draw
			capture.capture(index)
			if phase=="paired":expected.append(root.get_texture().get_image())
		capture.readback();await wait_state(capture,"readback_ready")
		var images:Array[Image]=capture.images();var passed:=images.size()==8 and String(capture.stats().error).is_empty()
		var matches:Array=[]
		for index in images.size():
			var oracle:=expected[index].duplicate() as Image
			oracle.convert(images[index].get_format())
			var same:=images[index].get_size()==oracle.get_size() and images[index].get_data()==oracle.get_data()
			matches.append(same);passed=passed and same
			images[index].save_png(output.get_base_dir().path_join("%s-%02d.png"%[phase,index]))
		rows.append({"case":phase,"passed":passed,"matches":matches,"capture":capture.stats(),"readback_during_sequence":phase=="paired"})
		valid=valid and passed
		capture.release();await wait_state(capture,"released")
		capture.release()
		for frame in 2:await process_frame;await RenderingServer.frame_post_draw
	quad.queue_free()
	for frame in 4:await process_frame
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"passed":valid,"cases":rows,"repeated_release":true,"helper_sha256":FileAccess.get_sha256(get_script().resource_path.get_base_dir().path_join("gpu_frame_capture.gd")),"probe_sha256":FileAccess.get_sha256(get_script().resource_path),"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"scope":"Pixel-exact GPU viewport snapshots with deferred readback","performance_acceptance":false,"quality_acceptance":false},"\t"))
	if valid:print("GPU_FRAME_CAPTURE_PASS");quit()
	else:push_error("GPU frame capture pixel comparison failed");quit(4)
