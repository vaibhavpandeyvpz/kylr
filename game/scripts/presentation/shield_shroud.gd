class_name ShieldShroud
extends RefCounted

static func install(robot) -> MeshInstance3D:
	var source := Assets.scene("res://assets/models/characters/%s/%s.glb" % [robot.character.model,robot.character.shield])
	var source_skeleton := Assets.find(source,"Skeleton3D") as Skeleton3D
	var selected: MeshInstance3D
	for mesh in source.find_children("*","MeshInstance3D",true,false):
		if String(mesh.name).to_lower().ends_with(robot.head): selected=mesh; break
	assert(selected!=null,"Missing shield shroud for head "+robot.head)
	# Bind directly to the live body skeleton: no duplicate skeleton or animator.
	var skin: Skin=selected.skin.duplicate()
	for bind in skin.get_bind_count():
		var name := skin.get_bind_name(bind)
		if name==&"": name=source_skeleton.get_bone_name(skin.get_bind_bone(bind))
		var bone: int=robot.skeleton.find_bone(name)
		assert(bone>=0,"Shield bone missing: "+String(name))
		skin.set_bind_name(bind,name)
		skin.set_bind_bone(bind,bone)
	selected.get_parent().remove_child(selected)
	selected.owner=null
	robot.skeleton.add_child(selected)
	selected.transform=Transform3D.IDENTITY
	selected.skeleton=NodePath("..")
	selected.skin=skin
	selected.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	selected.extra_cull_margin=0.3
	var material := ShaderMaterial.new()
	material.shader=load("res://shaders/shield.gdshader")
	material.set_shader_parameter("tint",robot.tint)
	selected.material_override=material
	selected.visible=false
	source.free()
	return selected
