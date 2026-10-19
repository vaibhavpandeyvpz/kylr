extends Control
## Finished-match presentation; the authoritative result remains read-only.
signal return_requested
signal exit_requested
const TEXT=Color("f3f6f7")
const MUTED=Color("b9c9d1")
const ACCENT=Color("6fe5ea")
const DISPLAY=preload("res://assets/ui/fonts/Rajdhani-SemiBold.ttf")
var result: Dictionary
var map_title := ""
var online := false
var local_id := -1
var team_colors: Array = []
var status: Label
var return_button: Button
var exit_button: Button
var padding: MarginContainer
var content: VBoxContainer
var heading: BoxContainer
var summary: VBoxContainer
var mvp_label: Label
var title: Label
var teams: BoxContainer
var standings: ScrollContainer
var table: VBoxContainer
var actions: BoxContainer
var sized_labels: Array[Label] = []
var table_rows: Array[HBoxContainer] = []
var visible_columns: Array[int] = []
var header_clip: Control
var column_header: PanelContainer

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	visible_columns.assign([0,2,3,4,6] if result.match_type=="DM" else [0,1,2,3,4,6] if result.match_type=="TDM" else [0,1,2,3,4,5,6])
	padding=MarginContainer.new()
	padding.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(padding)
	content=VBoxContainer.new()
	padding.add_child(content)
	text(content,"KYLR     •     MATCH COMPLETE",14,ACCENT)
	heading=BoxContainer.new()
	content.add_child(heading)
	var winner := VBoxContainer.new()
	winner.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	heading.add_child(winner)
	title=text(winner,String(result.title).to_upper(),52,TEXT,true)
	title.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	text(winner,"%s  /  %s"%[map_title.to_upper(),String(result.match_type)],16,MUTED)
	summary=VBoxContainer.new()
	heading.add_child(summary)
	if not result.get("canceled",false):
		text(summary,"MOST VALUABLE PLAYER",12,ACCENT)
		mvp_label=text(summary,String(result.mvp),26,TEXT,true)
		mvp_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	else:
		var reason := text(summary,String(result.get("reason","Match canceled")),16,MUTED)
		reason.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if result.match_type!="DM":
		teams=BoxContainer.new()
		content.add_child(teams)
		for index in result.teams.size():
			var team: Dictionary=result.teams[index]
			var block := HBoxContainer.new()
			block.size_flags_horizontal=Control.SIZE_EXPAND_FILL
			block.add_theme_constant_override("separation",16)
			teams.add_child(block)
			var color: Color=team_colors[index] if index<team_colors.size() else ACCENT
			var icon := TextureRect.new()
			icon.texture=preload("res://assets/ui/icons/material_symbols/flag.svg") if result.match_type=="CTF" else preload("res://assets/ui/icons/material_symbols/skull.svg")
			icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
			icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			icon.custom_minimum_size=Vector2(24,24)
			icon.size_flags_vertical=Control.SIZE_SHRINK_CENTER
			icon.modulate=color
			block.add_child(icon)
			text(block,str(team.score),40,color,true)
			var details := VBoxContainer.new()
			block.add_child(details)
			text(details,String(team.name).to_upper(),14,TEXT)
			text(details,"%s  /  reached %.2f s"%["Captures" if result.match_type=="CTF" else "Kills",team.time],14,MUTED)
	var separator := HSeparator.new()
	separator.modulate=Color("415464")
	content.add_child(separator)
	var table_caption := HBoxContainer.new()
	content.add_child(table_caption)
	var caption := text(table_caption,"FINAL STANDINGS",14,MUTED)
	caption.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	text(table_caption,"%d ROBOTS"%result.entries.size(),14,MUTED)
	var ranking := VBoxContainer.new()
	ranking.size_flags_vertical=Control.SIZE_EXPAND_FILL
	ranking.add_theme_constant_override("separation",2)
	content.add_child(ranking)
	header_clip=Control.new()
	header_clip.clip_contents=true
	ranking.add_child(header_clip)
	standings=ScrollContainer.new()
	standings.name="Standings"
	standings.size_flags_vertical=Control.SIZE_EXPAND_FILL
	standings.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_AUTO
	ranking.add_child(standings)
	table=VBoxContainer.new()
	table.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	table.add_theme_constant_override("separation",2)
	standings.add_child(table)
	row(["ROBOT","TEAM","KILLS","ASSISTS","DEATHS","CAPTURES","KILL TIME"],true)
	var entries: Array=result.entries.duplicate()
	entries.sort_custom(func(a,b):
		if a.kills!=b.kills: return a.kills>b.kills
		if a.reached!=b.reached: return a.reached<b.reached
		return String(a.name).naturalnocasecmp_to(String(b.name))<0)
	var place := 1
	for index in entries.size():
		var entry: Dictionary=entries[index]
		if index>0 and (entry.kills!=entries[index-1].kills or entry.reached!=entries[index-1].reached): place=index+1
		var local := int(entry.get("id",-2))==local_id
		var name_text := "%02d   %s%s"%[place,entry.name,"  / YOU" if local else ""]
		var values := [name_text,"—" if result.match_type=="DM" else "A" if entry.team==0 else "B",str(entry.kills),str(entry.assists),str(entry.deaths),str(entry.captures),"%.2f s"%entry.reached]
		row(values,false,local,index)
	var note := text(content,"Kill time is elapsed match time at the final kill. It resolves tied kill scores.",13,MUTED)
	note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	status=text(content,"",14,ACCENT)
	status.name="ResultsStatus"
	status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	status.visible=online
	actions=BoxContainer.new()
	content.add_child(actions)
	return_button=action("RETURN TO LOBBY" if online else "RETURN TO MAIN MENU",true)
	return_button.name="ReturnToMenu"
	return_button.pressed.connect(func(): return_requested.emit())
	exit_button=action("EXIT GAME",false)
	exit_button.name="ExitGame"
	exit_button.pressed.connect(func(): exit_requested.emit())
	resized.connect(reflow)
	reflow()
	return_button.grab_focus.call_deferred()

func text(parent: Node,value: String,font_size: int,color: Color,display := false) -> Label:
	var label := Label.new()
	label.text=value
	label.add_theme_color_override("font_color",color)
	label.set_meta("base_size",font_size)
	if display: label.add_theme_font_override("font",DISPLAY)
	parent.add_child(label)
	sized_labels.append(label)
	return label

func row(values: Array,header := false,local := false,index := 0) -> void:
	var backing := PanelContainer.new()
	var style := StyleBoxFlat.new()
	style.bg_color=Color(0.43,0.9,0.92,0.09) if local else Color(0.09,0.14,0.18,0.96) if index%2==0 and not header else Color(0.06,0.09,0.12,0.96)
	style.content_margin_left=16
	style.content_margin_right=16
	style.content_margin_top=8
	style.content_margin_bottom=8
	backing.add_theme_stylebox_override("panel",style)
	if header:
		column_header=backing
		header_clip.add_child(backing)
	else: table.add_child(backing)
	var cells := HBoxContainer.new()
	backing.add_child(cells)
	table_rows.append(cells)
	for column in visible_columns:
		var color := MUTED if header else ACCENT if local and column==0 else TEXT
		var cell := text(cells,str(values[column]),12 if header else 18,color,not header and column>1)
		cell.set_meta("column_index",column)
		cell.horizontal_alignment=HORIZONTAL_ALIGNMENT_LEFT if column==0 else HORIZONTAL_ALIGNMENT_CENTER if column==1 else HORIZONTAL_ALIGNMENT_RIGHT
		cell.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
		if column==0:
			cell.size_flags_horizontal=Control.SIZE_EXPAND_FILL
			cell.tooltip_text=str(values[column])

func action(value: String,primary: bool) -> Button:
	var button := Button.new()
	button.text=value
	button.size_flags_horizontal=Control.SIZE_FILL
	button.alignment=HORIZONTAL_ALIGNMENT_CENTER
	for state in ["normal","hover","pressed","focus"]:
		var style := StyleBoxFlat.new()
		style.bg_color=(ACCENT if state=="normal" else Color("a9f5f4")) if primary else Color("17222d") if state=="normal" else Color("243341")
		style.set_content_margin_all(16)
		if state=="focus":
			style.set_border_width_all(2)
			style.border_color=TEXT
		button.add_theme_stylebox_override(state,style)
		button.add_theme_color_override("font_"+state+"_color",Color("0b1119") if primary else TEXT)
	button.add_theme_color_override("font_color",Color("0b1119") if primary else TEXT)
	actions.add_child(button)
	return button

func reflow() -> void:
	if not is_instance_valid(content): return
	var scale := clampf(minf(size.x/1600.0,size.y/1000.0),0.85,1.5)
	var side := maxf(16,(size.x-1360*scale)*0.5)
	for edge in ["left","right"]: padding.add_theme_constant_override("margin_"+edge,int(side))
	for edge in ["top","bottom"]: padding.add_theme_constant_override("margin_"+edge,int(24*scale))
	content.add_theme_constant_override("separation",int(16*scale))
	heading.vertical=size.x<900
	heading.add_theme_constant_override("separation",int(16*scale))
	summary.custom_minimum_size.x=0 if heading.vertical else 340*scale
	summary.size_flags_horizontal=Control.SIZE_EXPAND_FILL if heading.vertical else Control.SIZE_FILL
	for node in summary.get_children():
		if node is Label: node.horizontal_alignment=HORIZONTAL_ALIGNMENT_LEFT if heading.vertical else HORIZONTAL_ALIGNMENT_RIGHT
	if teams:
		teams.vertical=size.x<620
		teams.add_theme_constant_override("separation",int(24*scale))
	for label in sized_labels: label.add_theme_font_size_override("font_size",maxi(12,int(label.get_meta("base_size")*scale)))
	if size.y<700: title.add_theme_font_size_override("font_size",32)
	var widths := [240,64,64,80,80,96,110]
	header_clip.custom_minimum_size.y=32*scale
	for cells in table_rows:
		cells.add_theme_constant_override("separation",int(16*scale))
		for cell in cells.get_children(): cell.custom_minimum_size.x=widths[int(cell.get_meta("column_index"))]*scale
	actions.vertical=size.x<560
	actions.alignment=BoxContainer.ALIGNMENT_END
	actions.add_theme_constant_override("separation",int(12*scale))
	for button in [return_button,exit_button]:
		button.size_flags_horizontal=Control.SIZE_EXPAND_FILL if actions.vertical else Control.SIZE_FILL
		button.custom_minimum_size.y=52*scale
		button.add_theme_font_size_override("font_size",maxi(16,int(18*scale)))
	return_button.custom_minimum_size.x=0 if actions.vertical else 320*scale
	exit_button.custom_minimum_size.x=0 if actions.vertical else 180*scale

func _unhandled_key_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and not event.is_echo():
		get_viewport().set_input_as_handled()
		return_requested.emit()

func _process(_dt: float) -> void:
	if not is_instance_valid(column_header): return
	var dimensions := Vector2(table.size.x,header_clip.size.y)
	if column_header.size!=dimensions: column_header.size=dimensions
	var offset := Vector2(-standings.scroll_horizontal,0)
	if column_header.position!=offset: column_header.position=offset
