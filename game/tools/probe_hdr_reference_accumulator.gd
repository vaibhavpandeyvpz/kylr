extends SceneTree
## Independent HDR GPU arithmetic/lifecycle check; does not trace or measure FPS.
const Accumulator=preload("res://tools/hdr_reference_accumulator.gd")
var output:="res://reports/performance/hdr-reference-accumulator.json"
var source_hash:=""
var helper_hash:=""
var engine_hash:=""

func _initialize():
	source_hash=FileAccess.get_sha256("res://tools/probe_hdr_reference_accumulator.gd")
	helper_hash=FileAccess.get_sha256("res://tools/hdr_reference_accumulator.gd")
	engine_hash=FileAccess.get_sha256(OS.get_executable_path())
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
	RenderingServer.call_on_render_thread(_test)

func _test():
	var rd:=RenderingServer.get_rendering_device()
	if rd==null:_finish.call_deferred({"passed":false,"error":"Graphical RenderingDevice required"});return
	var accumulator=Accumulator.new()
	var textures:Array[RID]=[]
	for row in [[Vector2i(4,4),Color(2,0,0,1)],[Vector2i(4,4),Color(0,0,6,1)],[Vector2i(4,4),Color(0,100,0,1)],[Vector2i(8,8),Color(4,8,12,1)]]:
		var image:=Image.create_empty(row[0].x,row[0].y,false,Image.FORMAT_RGBAH);image.fill(row[1])
		var format:=RDTextureFormat.new();format.width=row[0].x;format.height=row[0].y
		format.format=RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT
		format.usage_bits=RenderingDevice.TEXTURE_USAGE_STORAGE_BIT|RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
		textures.append(rd.texture_create(format,RDTextureView.new(),[image.get_data()]))
	var passed:bool=accumulator.append_color(textures[0],Vector2i(4,4),1,true)
	passed=accumulator.append_color(textures[1],Vector2i(4,4),3) and passed
	# A draw without a requested sample must hold the previous HDR mean.
	passed=accumulator.append_color(textures[2],Vector2i(4,4),0) and passed
	var held:=Image.create_from_data(4,4,false,Image.FORMAT_RGBAH,rd.texture_get_data(textures[2],0)).get_pixel(1,1)
	var weighted_error:=Vector3(held.r-.5,held.g,held.b-4.5).length()
	var samples:Dictionary=accumulator.stats()
	passed=passed and weighted_error<.001 and samples.weight==4 and samples.batches==2
	passed=accumulator.append_color(textures[0],Vector2i(4,4),2,true) and passed
	var reset:=Image.create_from_data(4,4,false,Image.FORMAT_RGBAH,rd.texture_get_data(textures[0],0)).get_pixel(1,1)
	var reset_error:=Vector3(reset.r-2,reset.g,reset.b).length()
	passed=passed and reset_error<.001
	passed=accumulator.append_color(textures[3],Vector2i(8,8),1,true) and passed
	var resized:=Image.create_from_data(8,8,false,Image.FORMAT_RGBAH,rd.texture_get_data(textures[3],0)).get_pixel(3,3)
	var resize_error:=Vector3(resized.r-4,resized.g-8,resized.b-12).length()
	passed=passed and resize_error<.001
	accumulator._release_on_render_thread()
	for texture in textures:rd.free_rid(texture)
	_finish.call_deferred({"passed":passed,"weighted_hdr":[held.r,held.g,held.b],"expected_hdr":[.5,0,4.5],"weighted_error":weighted_error,"reset_error":reset_error,"resize_error":resize_error,"released":accumulator.stats().released,"performance_accepted":false})

func _finish(report:Dictionary):
	report["engine_sha256"]=engine_hash;report["probe_sha256"]=source_hash;report["helper_sha256"]=helper_hash
	report["unchanged"]=source_hash==FileAccess.get_sha256("res://tools/probe_hdr_reference_accumulator.gd") and helper_hash==FileAccess.get_sha256("res://tools/hdr_reference_accumulator.gd") and engine_hash==FileAccess.get_sha256(OS.get_executable_path())
	report["passed"]=report.passed and report.unchanged
	DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify(report,"\t"))
	print("HDR_REFERENCE_ACCUMULATOR ",JSON.stringify(report))
	quit(0 if report.passed else 1)
