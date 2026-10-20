class_name MenuStudio
extends RefCounted
## All menu portraits share a native-resolution raster studio, independent of match presets.
static func create(tree: SceneTree, dimensions: Vector2i, transparent := true) -> SubViewport:
	var viewport := SubViewport.new()
	viewport.name = "MenuPortraitStudio"
	viewport.size = dimensions
	viewport.world_3d = World3D.new()
	viewport.transparent_bg = transparent
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.scaling_3d_scale = 1.0
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	tree.root.add_child(viewport)
	ArenaLighting.install(viewport,true)
	return viewport
