class_name CarrierCollision
extends RefCounted
## Assemble fixed native fixture shapes into rigid carrier groups after deployment.
## Gameplay machinery and payloads retain their independent collision bodies.
static func consolidate(carriers: MapCarriers) -> Dictionary:
	var arena=carriers.arena
	var markers: Dictionary={}
	for marker in arena.markers:markers[marker.name]=marker
	var anchors: Dictionary={}
	for section in carriers.sections:
		var group: String=carriers.rigid_groups[section.name]
		if not anchors.has(group):anchors[group]=section
	var batches: Dictionary={}
	for fixture in arena.fixtures:
		if fixture.kind not in ["platform","pillar","prop"]:continue
		var marker: Dictionary=markers.get(fixture.id,{})
		var deck: String=marker.get("deck","")
		if not carriers.rigid_groups.has(deck):continue
		var group: String=carriers.rigid_groups[deck]
		for body: StaticBody3D in fixture.node.find_children("*","StaticBody3D",true,false):
			# Mounted holders and payloads are separate assets below fixed wall mounts.
			if body.get_meta("collision_asset_root",0)!=fixture.node.get_instance_id():continue
			var bone_attachment:=body.get_parent() as BoneAttachment3D
			if bone_attachment!=null:
				var rig:=bone_attachment.get_parent() as Skeleton3D
				var bone:=rig.find_bone(bone_attachment.bone_name)
				var moving:=false
				while bone>=0:
					if String(rig.get_bone_name(bone)).begins_with("CargoLift"):moving=true;break
					bone=rig.get_bone_parent(bone)
				if moving:continue
			var material: String=body.get_meta("spatio_material","")
			var lethal: bool=body.get_meta("lethal_surface",false)
			var policy: Array=[group,material,lethal,body.collision_layer,body.collision_mask,body.physics_material_override]
			if not batches.has(policy):batches[policy]=[]
			batches[policy].append(body)
	var before:=0;var after:=0;var shape_count:=0
	for policy: Array in batches:
		var bodies: Array=batches[policy]
		before+=bodies.size()
		var section: Dictionary=anchors[policy[0]]
		var attachment:=BoneAttachment3D.new()
		attachment.name="CarrierCollision_"+String(policy[0])
		attachment.bone_name="Deck_"+String(section.name)
		attachment.set_meta("moving_platform",true)
		carriers.skeleton.add_child(attachment)
		var body:=AnimatableBody3D.new();body.sync_to_physics=false
		body.collision_layer=policy[3];body.collision_mask=policy[4];body.physics_material_override=policy[5]
		body.set_meta("spatio_material",policy[1]);body.set_meta("lethal_surface",policy[2])
		attachment.add_child(body)
		var inverse:=Assets.socket_world_transform(attachment).affine_inverse()
		for original: StaticBody3D in bodies:
			var parent:=original.get_parent()
			for shape: CollisionShape3D in original.find_children("*","CollisionShape3D",false,false):
				var transform:=inverse*Assets.socket_world_transform(shape)
				shape.reparent(body,false);shape.transform=transform
				shape.set_meta("carrier_group",policy[0]);shape_count+=1
			original.free()
			if parent.get_meta("collision_anchor",false) and parent.get_child_count()==0:parent.free()
		after+=1
	carriers.skeleton.force_update_all_bone_transforms()
	return {"bodies_before":before,"bodies_after":after,"shapes":shape_count}
