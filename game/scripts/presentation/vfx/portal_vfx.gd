class_name PortalVfx
extends RefCounted

const PORTAL = preload("res://shaders/original/field.gdshader")
const GLOW = PORTAL
const PRIMARY_COLOR := Color("6bbaff")
const SECONDARY_COLOR := Color("1456db")

static func install(field: MeshInstance3D) -> MeshInstance3D:
	var material := ShaderMaterial.new()
	material.shader = PORTAL
	material.set_shader_parameter("turbulence_texture",preload("res://assets/models/effects/combat_effects/turbulence_rgba.png"))
	material.set_shader_parameter("primary_color",PRIMARY_COLOR)
	material.set_shader_parameter("secondary_color",SECONDARY_COLOR)
	material.set_shader_parameter("size",Vector2(field.mesh.get_aabb().size.x,field.mesh.get_aabb().size.y))
	field.material_override = material
	field.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Both layers retain the native mesh, skin and bind transform. No expansion
	# outside the authored opening and no changes to the collision or portal rig.
	var glow := field.duplicate(0) as MeshInstance3D
	glow.name = "PortalGlow"
	glow.material_override = material.duplicate()
	glow.material_override.set_shader_parameter("glow_only",true)
	field.get_parent().add_child(glow)
	return glow

static func set_reduced_motion(fields: Array, reduced: bool) -> void:
	for field in fields:
		var state := Vector2i(int(reduced),int(field.visible))
		if field.get_meta("portal_motion_state",Vector2i(-1,-1)) == state: continue
		field.set_meta("portal_motion_state",state)
		(field.material_override as ShaderMaterial).set_shader_parameter("speed_scale",0.0 if reduced else 1.0)
