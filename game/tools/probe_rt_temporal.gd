extends SceneTree
var stage: Node3D
var camera: Camera3D
var box: MeshInstance3D
var material: StandardMaterial3D
var options: Dictionary = {}
var output_directory := "res://reports/performance"
var capture_all := false
func option(key: String, fallback: String) -> String:
 return String(options.get(key,fallback))
func _initialize(): call_deferred("run")
func wait_frames(n: int):
 for i in range(n): await process_frame
func wait_color(channel: int) -> bool:
 for i in range(1800):
  await RenderingServer.frame_post_draw
  var color := root.get_texture().get_image().get_pixelv(Vector2i(camera.unproject_position(box.position)))
  if color[channel]>.25 and color[channel]>color[(channel+1)%3]*1.5 and color[channel]>color[(channel+2)%3]*1.5: return true
  await process_frame
 return false
func capture(label: String) -> bool:
 await RenderingServer.frame_post_draw
 var error := root.get_texture().get_image().save_png(output_directory.path_join("rt60-temporal-"+label+".png"))
 if error!=OK: push_error("Temporal capture save failed: "+error_string(error));return false
 return true
func run():
 create_timer(180).timeout.connect(func():push_error("Temporal probe timed out");quit(8))
 for argument in OS.get_cmdline_user_args():
  if argument.begins_with("--") and "=" in argument: options[argument.get_slice("=",0).trim_prefix("--")]=argument.get_slice("=",1)
 var raster := option("mode","rt")=="raster"
 if not raster and not Preferences.ray_tracing_unavailable_reason().is_empty():
  push_error(Preferences.ray_tracing_unavailable_reason());quit(2);return
 var preset := option("rr-preset","?").to_upper()
 if preset not in ["?","D","E"]: push_error("RR preset must be ?, D or E");quit(5);return
 var scale := clampf(float(option("scale","0.5")),0.25,1.0)
 capture_all=option("capture-motion","0")=="1"
 var frame_count := clampi(int(option("frames","90")),10,360)
 if capture_all:
  output_directory=output_directory.path_join("temporal-%s-%s-%s"%["raster" if raster else "rt","auto" if preset=="?" else preset,str(scale).replace(".","_")])
 if DirAccess.make_dir_recursive_absolute(output_directory)!=OK:push_error("Cannot create temporal capture directory");quit(6);return
 if not raster and Engine.has_singleton("Streamline"):
  Engine.get_singleton("Streamline").set_parameter(ClassDB.class_get_integer_constant("Streamline","STREAMLINE_PARAM_DLSS_RR_PRESET"),preset)
 root.size=Vector2i(int(option("width","1280")),int(option("height","720")))
 stage=Node3D.new();root.add_child(stage)
 ArenaLighting.install(stage,true)
 camera=Camera3D.new();stage.add_child(camera)
 camera.position=Vector3(0,1.4,4);camera.look_at(Vector3(0,.7,0));camera.current=true
 box=MeshInstance3D.new();box.mesh=BoxMesh.new();stage.add_child(box);box.position=Vector3(0,.7,0)
 material=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.albedo_color=Color(1,0,0);box.material_override=material
 var floor:=MeshInstance3D.new();var plane:=PlaneMesh.new();plane.size=Vector2(12,12);floor.mesh=plane;floor.material_override=Assets.material(Color("454d54"));stage.add_child(floor)
 var prefs:=Preferences.new("user://rt60-temporal-unused.cfg");prefs.values.quality=3;prefs.values.ray_tracing=not raster;prefs.values.fixture_lighting=true;prefs.apply_rendering(stage)
 root.scaling_3d_scale=1.0 if raster else scale
 if not await wait_color(0): push_error("Initial StandardMaterial RT color missing");quit(2);return
 material.albedo_color=Color(0,1,0)
 if not await wait_color(1): push_error("Live material uniform update missing");quit(3);return
 material.shading_mode=BaseMaterial3D.SHADING_MODE_PER_PIXEL
 material.albedo_color=Color(0,0,1)
 material.emission_enabled=true;material.emission=Color(0,0,1);material.emission_energy_multiplier=1.8
 if not await wait_color(2): push_error("StandardMaterial shader feature update missing");quit(4);return
 if not await capture("source-refresh"):quit(6);return
 var moving:=MeshInstance3D.new();var sphere:=SphereMesh.new();sphere.radius=.22;sphere.height=.44;moving.mesh=sphere
 var yellow:=StandardMaterial3D.new();yellow.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;yellow.albedo_color=Color(1,1,0);moving.material_override=yellow;stage.add_child(moving);moving.position=Vector3(-1,.7,1)
 await wait_frames(180)
 var samples: Array = []
 for i in range(frame_count):
  var progress := float(i)/float(frame_count-1)
  var a:=lerpf(-.55,.55,progress)
  camera.position=Vector3(sin(a)*4,1.4,cos(a)*4);camera.look_at(Vector3(0,.7,0))
  moving.position.x=lerpf(-1.3,1.3,progress)
  await RenderingServer.frame_post_draw
  if capture_all or i in [0,frame_count/3,frame_count*2/3,frame_count-1]:
   var filename := "rt60-temporal-motion-%03d.png"%i
   var picture := root.get_texture().get_image()
   if picture.save_png(output_directory.path_join(filename))!=OK:push_error("Cannot save motion capture");quit(6);return
   samples.append({"frame":i,"file":filename,"camera_transform":str(camera.global_transform),"moving_position":str(moving.position),"moving_screen":str(camera.unproject_position(moving.position)),"image_size":str(picture.get_size())})
 var report := {"mode":"raster" if raster else "rt","preset_requested":preset,"internal_scale":root.scaling_3d_scale,"output_size":str(root.size),"motion_frames":frame_count,"per_frame_motion_identical_across_runs":true,"performance_benchmark":false,"samples":samples}
 FileAccess.open(output_directory.path_join("temporal-capture.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
 print("RT_TEMPORAL_PASS source_refresh camera_sweep moving_object")
 quit()
