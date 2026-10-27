class_name ArchitectureLights
extends RefCounted

static var rigid_meshes: Dictionary = {}
static var pending_meshes: Dictionary = {}

static func share_fixed_pose_meshes(root: Node3D) -> void:
	# Call only after permanently pausing an authored prop pose. Socket and
	# collider hierarchies stay native; differing extensions cannot share a bake.
	if DisplayServer.get_name()=="headless": return
	for instance: MeshInstance3D in root.find_children("*","MeshInstance3D",true,false):
		if instance.skin==null: continue
		# Snapshot eligible meshes now: later attachments can contain animated parts.
		if pending_meshes.is_empty():
			RenderingServer.frame_post_draw.connect(bake_pending_meshes,CONNECT_ONE_SHOT)
		pending_meshes[instance.get_instance_id()] = weakref(instance)

static func bake_pending_meshes() -> void:
	var pending := pending_meshes
	pending_meshes = {}
	for reference: WeakRef in pending.values():
		var instance := reference.get_ref() as MeshInstance3D
		if not is_instance_valid(instance) or not instance.is_inside_tree() or instance.skin==null: continue
		# Bone globals update synchronously, but the skin palette uploads later.
		# Baking before this render boundary can permanently cache the rest pose.
		var skeleton := instance.get_node(instance.skeleton) as Skeleton3D
		skeleton.force_update_all_bone_transforms()
		var poses: Array[Transform3D] = []
		for bone in skeleton.get_bone_count(): poses.append(skeleton.get_bone_global_pose(bone))
		var key := [instance.mesh.get_instance_id(),instance.skin.get_instance_id(),poses]
		share_mesh(instance,key)

static func share_mesh(instance: MeshInstance3D, key: Variant) -> void:
	var source := instance.mesh
	if not rigid_meshes.has(key):
		var skeleton := instance.get_node(instance.skeleton) as Skeleton3D
		skeleton.force_update_all_bone_transforms()
		var baked := instance.bake_mesh_from_current_skeleton_pose()
		baked.set_meta("source_mesh_path",source.resource_path)
		for surface in source.get_surface_count():
			baked.surface_set_material(surface,source.surface_get_material(surface))
		rigid_meshes[key]=baked
	instance.mesh=rigid_meshes[key]
	instance.skin=null
	instance.skeleton=NodePath("")
	ShadowBatch.install_one(instance)

static func share_static_meshes(root: Node3D) -> void:
	# Only assets declared static by their native rig metadata use this path.
	# Keep their socket hierarchy,
	# but share unskinned render geometry so Forward+ can instance the lamps.
	# Parent platform motion still moves the complete lamp normally.
	share_fixed_pose_meshes(root)

static func emissive_only(root: Node3D) -> void:
	for mesh: MeshInstance3D in root.find_children("*","MeshInstance3D",true,false):
		mesh.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

static func install(root: Node3D, category: String, asset: String, suffix: String = "", emissive_assets: Array = []) -> int:
	var path := "res://assets/models/%s/%s/%s%s_rig.json"%[category,asset,asset,suffix]
	if not FileAccess.file_exists(path):return 0
	var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	if metadata.get("static",false): share_static_meshes(root)
	var count := 0
	if asset in ["sconce_light","batten_light"]:
		if asset in emissive_assets:emissive_only(root)
		else:FixtureLighting.area(Assets.socket(root,"LightProjection"),asset,float(metadata.gizmos[0].range_m))
		return 1
	if asset=="pole_light":
		for beam in metadata.gizmos:
			var projection:=Assets.socket(root,beam.name)
			assert(projection!=null,"Missing pole head projection: "+String(beam.name))
			FixtureLighting.spot(projection,"pole_light",beam)
			count+=1
	for gizmo in metadata.get("gizmos",[]):
		var lamp_asset: String = gizmo.get("attachment","")
		if lamp_asset not in ["sconce_light","batten_light"]:continue
		var mount := Assets.socket(root,String(gizmo.name))
		assert(mount != null,"Missing architecture light socket: "+String(gizmo.name))
		if mount == null or mount.has_node("MountedLuminaire"):continue
		var lamp := Assets.model("environments",lamp_asset)
		lamp.name="MountedLuminaire"
		mount.add_child(lamp)
		lamp.transform=Transform3D.IDENTITY
		share_static_meshes(lamp)
		var projection := Assets.socket(lamp,"LightProjection")
		assert(projection != null,"Luminaire requires its native projection gizmo")
		if lamp_asset in emissive_assets:emissive_only(lamp)
		else:FixtureLighting.area(projection,lamp_asset,8.0 if lamp_asset=="batten_light" else 6.0)
		count+=1
	return count
