class_name OnlineLayout
extends RefCounted
## Container-based online screens keep navigation and actions outside the scroll area.

static func spacer(parent: Node) -> Control:
	var control := Control.new()
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(control)
	return control

static func frame(ui: ArenaUI, title: String, subtitle: String, section := "ONLINE") -> Dictionary:
	var margin := MarginContainer.new()
	ui.page.add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+side,32)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation",24)
	margin.add_child(stack)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation",24)
	stack.add_child(header)
	var title_block := VBoxContainer.new()
	title_block.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title_block)
	ui.label(title_block,"KYLR / "+section,14,ui.ACTION)
	ui.label(title_block,title,36)
	ui.label(title_block,subtitle,16,ui.MUTED)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	stack.add_child(scroll)
	var body := BoxContainer.new()
	body.add_theme_constant_override("separation",32)
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.add_child(body)
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation",16)
	stack.add_child(footer)
	ui.page.set_meta("online_body",body)
	ui.page.set_meta("online_margin",margin)
	return {"body":body,"footer":footer,"header":header}

static func column(parent: Node, ratio := 1.0) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.size_flags_stretch_ratio = ratio
	box.add_theme_constant_override("separation",16)
	parent.add_child(box)
	return box

static func action(ui: ArenaUI, parent: Node, text: String, callback: Callable, primary := false) -> Button:
	var button := ui.button(parent,text,callback,primary)
	button.alignment = HORIZONTAL_ALIGNMENT_CENTER
	button.custom_minimum_size = Vector2(112,52)
	button.add_theme_font_size_override("font_size",16)
	return button

static func layout(ui: ArenaUI):
	if not is_instance_valid(ui.page) or not ui.page.has_meta("online_body"): return
	var compact := ui.root.size.x < 1100
	var body: BoxContainer = ui.page.get_meta("online_body")
	body.vertical = compact and (ui.screen != "customise" or ui.root.size.x < 740)
	var margin: MarginContainer = ui.page.get_meta("online_margin")
	for side in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+side,16 if compact else 32)
	for child in body.get_children():
		child.custom_minimum_size.x = 0
	if ui.screen == "customise" and not body.vertical and body.get_child_count() == 2:
		body.get_child(0).size_flags_stretch_ratio = 0.75 if compact else 1.0
		body.get_child(1).size_flags_stretch_ratio = 1.25 if compact else 1.15
	for stage in ui.page.find_children("OnlineStage","Control",true,false):
		stage.custom_minimum_size.y = clampf(ui.root.size.y-300,260,760) if not body.vertical else 280
	for grid in ui.page.find_children("ChoicesGrid","GridContainer",true,false):
		grid.columns = 4 if grid.get_meta("colors",false) and grid.size.x >= 520 else 3 if grid.size.x >= 420 else 2
	for container in body.find_children("*","Container",true,false): container.queue_sort()
