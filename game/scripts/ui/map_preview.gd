class_name MapPreview
extends VBoxContainer
## Lightweight authored map photography; no world or players run inside this menu.
var map_id := ""
var reduced_motion := false
var shots: Array = []
var textures: Array[Texture2D] = []
var photograph: TextureRect
var caption: Label
var selectors: Array[Button] = []
var selected := 0
var elapsed := 0.0

func _ready():
	add_theme_constant_override("separation",12)
	size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/previews.json"))
	shots=manifest.get(map_id,[])
	var frame:=AspectRatioContainer.new()
	frame.ratio=16.0/9.0
	frame.stretch_mode=AspectRatioContainer.STRETCH_WIDTH_CONTROLS_HEIGHT
	frame.resized.connect(func(): frame.custom_minimum_size.y=maxf(180,frame.size.x*9.0/16.0))
	frame.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	frame.custom_minimum_size.y=180
	add_child(frame)
	photograph=TextureRect.new()
	photograph.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	photograph.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_COVERED
	frame.add_child(photograph)
	var footer:=HBoxContainer.new()
	footer.add_theme_constant_override("separation",8)
	add_child(footer)
	caption=Label.new()
	caption.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	caption.add_theme_font_size_override("font_size",14)
	caption.add_theme_color_override("font_color",MenuSkin.MUTED)
	caption.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	footer.add_child(caption)
	for index in shots.size():
		textures.append(load(shots[index].image) as Texture2D)
		var selector:=Button.new()
		selector.text=str(index+1)
		selector.accessibility_name=String(shots[index].title)
		selector.tooltip_text=String(shots[index].title)
		selector.add_theme_font_size_override("font_size",12)
		selector.custom_minimum_size=Vector2(28,28)
		footer.add_child(selector)
		selectors.append(selector)
		selector.pressed.connect(show_slide.bind(index))
	if not shots.is_empty(): show_slide(0)

func show_slide(index: int):
	selected=posmod(index,shots.size())
	elapsed=0.0
	photograph.texture=textures[selected]
	photograph.accessibility_name=String(shots[selected].title)
	caption.text=String(shots[selected].title)
	for item in selectors.size():
		MenuSkin.apply_button(selectors[item],false,item==selected)
		for state in ["normal","hover","pressed","focus","disabled"]:
			var box:=selectors[item].get_theme_stylebox(state).duplicate() as StyleBoxFlat
			box.set_content_margin_all(4)
			selectors[item].add_theme_stylebox_override(state,box)

func _process(dt: float):
	if reduced_motion or shots.size()<2 or not is_visible_in_tree(): return
	elapsed+=dt
	if elapsed>=2.0: show_slide(selected+1)
