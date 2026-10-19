extends SceneTree
## Compare denoised shadow boundaries with the same physical lighting at 128 spp.
func _initialize():run.call_deferred()

func profile(image: Image,pixels: Array) -> Dictionary:
	var values:=[];var distances:=[0.0]
	for index in pixels.size():
		var point:=Vector2(float(pixels[index][0]),float(pixels[index][1]))
		var value:=0.
		for dy in range(-1,2):
			for dx in range(-1,2):
				var color:=image.get_pixel(roundi(point.x)+dx,roundi(point.y)+dy)
				value+=Vector3(color.r,color.g,color.b).dot(Vector3(.2126,.7152,.0722))
		values.append(value/9.)
		if index>0:
			var previous:=Vector2(float(pixels[index-1][0]),float(pixels[index-1][1]))
			distances.append(distances[-1]+point.distance_to(previous))
	var dark:=0.;var lit:=0.
	for index in 5:dark+=values[index]/5.;lit+=values[-1-index]/5.
	var first20:=-1;var first80:=-1
	for index in values.size()-1:
		if first20<0 and minf(values[index],values[index+1])>=lerpf(dark,lit,.2):first20=index
		if first80<0 and minf(values[index],values[index+1])>=lerpf(dark,lit,.8):first80=index
	return {"valid":lit-dark>.04 and first20>=0 and first80>first20,
		"dark":dark,"lit":lit,"width_pixels":distances[first80]-distances[first20] if first20>=0 and first80>first20 else -1.,
		"values":values}

func dependency_hashes(manifest: Dictionary) -> Dictionary:
	if manifest.get("input_coverage","")!="project-scripts-data-assets-shaders-addons-tools-imported-v1":return {}
	var hashes:Dictionary={};var preferences_recorded:=false
	for entry in manifest.get("inputs",[]):
		var path:=String(entry.get("path","")).replace("\\","/")
		var digest:=String(entry.get("sha256",""))
		if path.is_empty() or digest.length()!=64 or hashes.has(path):return {}
		hashes[path]=digest
		preferences_recorded=preferences_recorded or path.ends_with("/scripts/core/preferences.gd")
	return hashes if preferences_recorded else {}

func run():
	var prefix:="shadow-quality";var mode:="dlss";var reference_prefix:=""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--prefix="):prefix=argument.get_slice("=",1)
		if argument.begins_with("--mode="):mode=argument.get_slice("=",1)
		if argument.begins_with("--reference-prefix="):reference_prefix=argument.get_slice("=",1)
	if reference_prefix.is_empty():reference_prefix=prefix
	var reference_base:="res://reports/performance/"+reference_prefix+"-reference/"
	var base:="res://reports/performance/"+prefix+"-"
	var reference:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(reference_base+"report.json"))
	var candidate:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(base+mode+"/report.json"))
	var reference_manifest:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(reference_base+"manifest.json"))
	var candidate_manifest:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(base+mode+"/manifest.json"))
	if not reference_manifest.get("capture_passed",false) or not candidate_manifest.get("capture_passed",false) or not reference_manifest.get("validation",false) or not candidate_manifest.get("validation",false):
		push_error("Missing validated capture provenance");quit(2);return
	if reference_manifest.engine_sha256!=candidate_manifest.engine_sha256 or reference_manifest.probe_sha256!=candidate_manifest.probe_sha256:
		push_error("Shadow reference and candidate must use the same engine and fixture");quit(2);return
	if reference.get("capture_revision",1)!=candidate.get("capture_revision",1):
		push_error("Shadow capture protocols differ");quit(2);return
	if reference.get("capture_revision",1)>=2:
		for pair in [[reference,reference_manifest],[candidate,candidate_manifest]]:
			if pair[1].get("capture_revision")!=2 or String(pair[0].get("observer_sha256","")).is_empty() or String(pair[0].observer_sha256).to_upper()!=pair[1].get("observer_sha256"):
				push_error("Shadow observer provenance is incomplete");quit(2);return
		if reference_manifest.observer_sha256!=candidate_manifest.observer_sha256 or reference_manifest.get("runtime_dlls")!=candidate_manifest.get("runtime_dlls"):
			push_error("Shadow observer or runtime libraries differ");quit(2);return
	var controls:=int(candidate_manifest.get("settings_control_revision",0))
	if controls!=int(reference_manifest.get("settings_control_revision",0)) or controls!=2:
		push_error("Shadow settings-control protocols differ");quit(2);return
	if controls==2:
		var inputs:=dependency_hashes(reference_manifest)
		if inputs.is_empty() or inputs!=dependency_hashes(candidate_manifest) or reference_manifest.get("engine_entrypoint_sha256")!=candidate_manifest.get("engine_entrypoint_sha256") or reference_manifest.get("wrapper_sha256")!=candidate_manifest.get("wrapper_sha256"):
			push_error("Shadow reference and candidate dependencies differ");quit(2);return
		for receipt in [reference_manifest,candidate_manifest]:
			if receipt.get("light_grid")!=false or receipt.get("light_proposals")!=false:
				push_error("Unexpected shadow light-policy experiment");quit(2);return
	var expected_size:=Vector2i(int(reference.native_output[0]),int(reference.native_output[1]))
	if reference.native_output!=candidate.native_output:push_error("Output dimensions differ");quit(2);return
	if reference.cases.size()!=4 or candidate.cases.size()!=4 or reference.samples_per_pixel!=128:quit(2);return
	var rows:=[];var valid:=true
	var small_reference:=Image.load_from_file(reference_base+"area-small.png")
	var large_reference:=Image.load_from_file(reference_base+"area-large.png")
	# Matching a reference is insufficient if the renderer ignores light size
	# in both paths. The source dimensions must change the physical reference.
	var area_size_affects_reference:bool=small_reference!=null and large_reference!=null and small_reference.get_data()!=large_reference.get_data()
	valid=valid and area_size_affects_reference
	var sheet:=Image.create_empty(1280,1440,false,Image.FORMAT_RGB8)
	for index in 4:
		var original:Dictionary=reference.cases[index];var current:Dictionary=candidate.cases[index]
		if original.light!=current.light or original.shadow_profile_pixels!=current.shadow_profile_pixels:
			push_error("Shadow scene/profile mismatch");quit(3);return
		var ref:=Image.load_from_file(reference_base+""+original.image)
		var image:=Image.load_from_file(base+mode+"/"+current.image)
		if ref==null or image==null or ref.get_size()!=expected_size or image.get_size()!=ref.get_size():quit(4);return
		var ref_profile:=profile(ref,original.shadow_profile_pixels)
		var img_profile:=profile(image,current.shadow_profile_pixels)
		var contrast:float=(img_profile.lit-img_profile.dark)/maxf(.001,ref_profile.lit-ref_profile.dark)
		var passed:bool=ref_profile.valid and img_profile.valid and contrast>.8 and contrast<1.2 and absf(img_profile.lit-ref_profile.lit)<.05 and img_profile.width_pixels<=maxf(ref_profile.width_pixels*1.5,ref_profile.width_pixels+3.)
		if original.light=="area-back":
			passed=maxf(ref_profile.dark,ref_profile.lit)<.05 and maxf(img_profile.dark,img_profile.lit)<.05
		valid=valid and passed
		rows.append({"light":original.light,"passed":passed,"contrast_retained":contrast,"reference":ref_profile,"candidate":img_profile})
		ref.convert(Image.FORMAT_RGB8);image.convert(Image.FORMAT_RGB8)
		ref.resize(640,360);image.resize(640,360)
		sheet.blit_rect(ref,Rect2i(0,0,640,360),Vector2i(0,index*360))
		sheet.blit_rect(image,Rect2i(0,0,640,360),Vector2i(640,index*360))
	sheet.save_png(base+mode+"/comparison.png")
	FileAccess.open(base+mode+"/comparison.json",FileAccess.WRITE).store_string(JSON.stringify({
		"passed":valid,"mode":mode,"reference_directory":reference_base,"settings_control_revision":controls,"comparison_sha256":FileAccess.get_sha256(get_script().resource_path),"dependency_coverage":candidate_manifest.get("input_coverage","legacy-subset"),"cases":rows,"area_size_affects_reference":area_size_affects_reference,
		"full_game_quality_acceptance":false,"performance_acceptance":false},"\t"))
	if valid:print("SHADOW_QUALITY_COMPARE_PASS ",mode);quit()
	else:push_error("Shadow quality comparison failed: "+mode);quit(5)
