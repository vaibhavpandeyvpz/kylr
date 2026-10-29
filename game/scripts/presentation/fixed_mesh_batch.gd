class_name FixedMeshBatch
extends RefCounted
## Spatially batch permanently baked fixture geometry. Gameplay nodes and lights
## retain their native hierarchy; carrier bones own the shared render anchors.

static func install(arena) -> Dictionary:
	var markers: Dictionary={}
	for marker in arena.markers: markers[marker.name]=marker
	var anchors: Dictionary={"static":arena.model}
	var batches: Dictionary={}
	var variants: Dictionary={}
	for fixture in arena.fixtures:
		if fixture.kind not in ["platform","pillar","prop"]: continue
		var deck: String=markers.get(fixture.id,{}).get("deck","")
		var group := "static"
		if arena.carriers and arena.carriers.rigid_groups.has(deck):
			group=arena.carriers.rigid_groups[deck]
			if not anchors.has(group):
				var anchor := BoneAttachment3D.new()
				anchor.name="FixedRender_"+group
				anchor.bone_name="Deck_"+deck
				arena.carriers.skeleton.add_child(anchor)
				anchors[group]=anchor
		var anchor: Node3D=anchors[group]
		var inverse := Assets.socket_world_transform(anchor).affine_inverse()
		for source: MeshInstance3D in fixture.node.find_children("*","MeshInstance3D",true,false):
			if not source.get_meta("fixed_render_mesh",false) or source.skin!=null or not source.is_visible_in_tree() or source.get_child_count()!=0: continue
			if moving_attachment(source,fixture.node): continue
			var transform := inverse*Assets.socket_world_transform(source)
			var cell := Vector3i(floori(transform.origin.x/12.0),floori(transform.origin.y/8.0),floori(transform.origin.z/12.0))
			var overrides: Array=[]
			for surface in source.mesh.get_surface_count(): overrides.append(source.get_surface_override_material(surface))
			var render_mesh := source.mesh as ArrayMesh
			var remainder: ArrayMesh
			var override_material := source.material_override
			var opaque: Array[int]=[]
			var individual: Array[int]=[]
			var materials: Array=[]
			for surface in render_mesh.get_surface_count():
				var material := source.get_active_material(surface)
				materials.append(material)
				if material is StandardMaterial3D and material.transparency==BaseMaterial3D.TRANSPARENCY_DISABLED and not material.grow: opaque.append(surface)
				else: individual.append(surface)
			if opaque.is_empty(): continue
			if not individual.is_empty():
				var variant_key: Array=[source.mesh,materials]
				if not variants.has(variant_key): variants[variant_key]=[subset(render_mesh,opaque,materials),subset(render_mesh,individual,materials)]
				render_mesh=variants[variant_key][0]
				remainder=variants[variant_key][1]
				override_material=null
				overrides=[]
				for surface in render_mesh.get_surface_count(): overrides.append(null)
			var key: Array=[group,cell,render_mesh,override_material,source.material_overlay,overrides,source.layers,source.cast_shadow,source.lod_bias,source.extra_cull_margin]
			if not batches.has(key): batches[key]=[]
			batches[key].append({"source":source,"transform":transform,"remainder":remainder})
	var before := 0
	var after := 0
	for key: Array in batches:
		var entries: Array=batches[key]
		if entries.size()<2: continue
		var source: MeshInstance3D=entries[0].source
		var mesh: ArrayMesh=key[2]
		if key[5].any(func(material):return material!=null):
			mesh=mesh.duplicate()
			for surface in key[5].size():
				if key[5][surface]!=null: mesh.surface_set_material(surface,key[5][surface])
		var data := MultiMesh.new()
		data.transform_format=MultiMesh.TRANSFORM_3D
		data.mesh=mesh
		data.instance_count=entries.size()
		for index in entries.size(): data.set_instance_transform(index,entries[index].transform)
		var instance := MultiMeshInstance3D.new()
		instance.name="FixedFixtureBatch"
		instance.multimesh=data
		instance.material_override=key[3]
		instance.material_overlay=source.material_overlay
		instance.layers=source.layers
		instance.cast_shadow=source.cast_shadow
		instance.lod_bias=source.lod_bias
		instance.extra_cull_margin=source.extra_cull_margin
		anchors[key[0]].add_child(instance)
		for entry in entries:
			if entry.remainder!=null:
				var individual := MeshInstance3D.new()
				individual.name="FixedFixtureTransparent"
				individual.mesh=entry.remainder
				individual.transform=entry.source.transform
				individual.layers=entry.source.layers
				individual.cast_shadow=entry.source.cast_shadow
				individual.lod_bias=entry.source.lod_bias
				individual.material_overlay=entry.source.material_overlay
				individual.extra_cull_margin=entry.source.extra_cull_margin
				entry.source.get_parent().add_child(individual)
			entry.source.hide()
		before+=entries.size()
		after+=1
	return {"sources":before,"batches":after}

static func subset(mesh: ArrayMesh, surfaces: Array[int], materials: Array) -> ArrayMesh:
	var result := ArrayMesh.new()
	var lods: Array=[]
	for surface in surfaces:
		lods.append(MeshLods.surface(mesh,surface))
		result.add_surface_from_arrays(mesh.surface_get_primitive_type(surface),mesh.surface_get_arrays(surface),[],lods.back())
		result.surface_set_material(result.get_surface_count()-1,materials[surface])
	result.set_meta("imported_lods",lods)
	return result

static func moving_attachment(source: Node, root: Node) -> bool:
	var node := source.get_parent()
	while node!=null and node!=root:
		if node is BoneAttachment3D and (node.bone_name.begins_with("CargoLift") or node.bone_name.begins_with("Spot")): return true
		node=node.get_parent()
	return false
