class_name EnergySurface
extends RefCounted
## Shared surface-following protection and accepted-hit feedback; no hit volume.
const SHADER=preload("res://shaders/combat/energy_surface.gdshader")
const HIT_COLORS={
	"lightning_gun":Color("357dff"),"pulse_gun":Color("37edff"),"bio_rifle":Color("58ff69"),
	"pistol":Color("ffe24d"),"rifle":Color("ffe24d"),"minigun":Color("ffe24d"),
	"grenade_launcher":Color("ff3535"),"rocket_launcher":Color("ff3535"),
	"flak_cannon":Color("ff8c2e"),"flamethrower":Color("ff8c2e"),"emp_gun":Color("a6abb3")}

static func weapon_color(cause: String) -> Color:
	if cause=="rifle_headshot":cause="rifle"
	return HIT_COLORS.get(cause,Color("a6abb3"))

static func material(tint: Color,offset:=0.05) -> ShaderMaterial:
	var result:=ShaderMaterial.new()
	result.shader=SHADER
	result.set_shader_parameter("tint",tint)
	result.set_shader_parameter("surface_offset",offset)
	return result

static func parameter(material: ShaderMaterial,key: String,value) -> void:
	if material.get_shader_parameter(key)!=value:material.set_shader_parameter(key,value)

static func update(robot) -> void:
	var visible: bool=robot.alive and robot.spawn_remaining<=0
	var shield: bool=visible and (robot.protection>0 or robot.sh>0)
	var strength: float=pow(clampf(robot.hit_flash/.2,0,1),1.2) if visible else 0.0
	parameter(robot.surface_material,"shield_strength",1.0 if shield else 0.0)
	parameter(robot.surface_material,"hit_strength",strength)
	parameter(robot.surface_material,"tint",robot.tint)
	parameter(robot.surface_material,"hit_tint",weapon_color(robot.last_hit_weapon))
	parameter(robot.surface_material,"motion_enabled",not robot.arena_match.reduced_motion)
	var active: bool=shield or strength>0
	if active!=robot.surface_active:
		for mesh in robot.surface_meshes:mesh.material_overlay=robot.surface_material if active else null
		robot.surface_active=active

static func clear(robot) -> void:
	for mesh in robot.surface_meshes:mesh.material_overlay=null
	robot.surface_active=false
