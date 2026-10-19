class_name WeaponReadout
extends Control
var robot
var icons: Dictionary = {}
var icon_regions: Dictionary = {}
var active_weight: Dictionary = {}
var screen_width := 1920.0
var previous_weapon := "pistol"
var switch_flash := 0.0
var reduced_motion := false

func _ready():
	for id in ContentRegistry.weapons():
		icons[id]=load("res://assets/ui/weapons/"+id+".png")
		var used: Rect2i = icons[id].get_image().get_used_rect()
		icon_regions[id] = Rect2(Vector2(used.position.x, used.position.y), Vector2(used.size.x, used.size.y))
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _process(dt: float) -> void:
	if robot == null: return
	if robot.equipped != previous_weapon:
		previous_weapon = robot.equipped
		switch_flash = 1.0
	for id in robot.owned_weapons:
		active_weight[id] = lerpf(float(active_weight.get(id,0.0)),1.0 if id==robot.equipped else 0.0,1.0-exp(-13.0*dt))
	switch_flash = maxf(0.0, switch_flash - dt * 3.0)
	queue_redraw()

static func slot_rects(count: int, area: Vector2, viewport_width: float) -> Array[Rect2]:
	var result: Array[Rect2] = []
	count=clampi(count,0,10)
	if count==0 or viewport_width<=0: return result
	var columns := mini(count,5)
	var rows := ceili(count/5.0)
	var gap := 6.0
	if area.x<=gap*(columns-1) or area.y<=gap*(rows-1): return result
	var width := minf(viewport_width*.15,(area.x-gap*(columns-1))/columns)
	var height := minf(126.0,(area.y-gap*(rows-1))/rows)
	var top := area.y-height*rows-gap*(rows-1)
	for index in count:
		var row := index/5
		var row_count := mini(5,count-row*5)
		var start := area.x-row_count*width-gap*(row_count-1)
		result.append(Rect2(start+(index%5)*(width+gap),top+row*(height+gap),width,height))
	return result

func _draw():
	if robot==null or size.x<60 or size.y<30: return
	var rectangles := slot_rects(robot.owned_weapons.size(),size,screen_width)
	for index in rectangles.size():
		var rect := rectangles[index]
		var id: String = robot.owned_weapons[index]
		var active: bool = id==robot.equipped
		var weight: float = active_weight.get(id,1.0 if active else 0.0)
		var x := rect.position.x
		var y := rect.position.y
		var w := rect.size.x
		var h := rect.size.y
		if w<32 or h<30: continue
		draw_rect(rect,Color(0.02,0.04,0.06,.65 if active else .38))
		if active: draw_rect(rect,HudSkin.CYAN,false,1.0)
		var font_size := 16 if h>95 else 11
		var key := "0" if index==9 else str(index+1)
		HudSkin.label(self,key,Vector2(x+6,y+font_size+3),font_size,HudSkin.WHITE,20,true)
		HudSkin.label(self,Arsenal.WEAPONS[id].title.to_upper() if w>50 else "",Vector2(x+27,y+font_size+3),font_size,HudSkin.WHITE,w-33,true,HORIZONTAL_ALIGNMENT_RIGHT,true)
		if icons.has(id):
			var region := Rect2(x+8,y+font_size+8,w-16,h*.34)
			var source: Rect2 = icon_regions[id]
			draw_texture_rect_region(icons[id],fit_icon(source.size,region),source,Color(1,1,1,.3+.35*weight))
		var ammo: Dictionary = robot.ammo_for(id)
		HudSkin.label(self,"∞" if id=="pistol" else str(ammo.loaded),Vector2(x+7,y+h-10),mini(28 if h>95 else 18,int(w*.3)),HudSkin.WHITE,minf(48,w-14),true)
		var caption := ("UNLIMITED" if w>=130 else "") if id=="pistol" else ("%d PACKS" % ammo.packs if w>=130 else "P%d" % ammo.packs)
		var caption_width := w-54 if w>=130 else 22.0
		HudSkin.label(self,caption,Vector2(x+w-caption_width-6,y+h-11),11 if h>95 else 10,HudSkin.WHITE,caption_width,true,HORIZONTAL_ALIGNMENT_RIGHT,true)
		if active and robot.reload_time>0:
			var progress := clampf(1.0-robot.reload_time/2.0,0.0,1.0)
			draw_rect(Rect2(x+3,y+h-4,(w-6)*progress,2),HudSkin.CYAN)
		if active and switch_flash>0 and not reduced_motion:
			draw_rect(rect,Color(1,1,1,switch_flash*.10))

static func fit_icon(source: Vector2, bounds: Rect2) -> Rect2:
	if source.x <= 0.0 or source.y <= 0.0: return bounds
	var scale := minf(bounds.size.x / source.x, bounds.size.y / source.y)
	var fitted := source * scale
	return Rect2(bounds.position + (bounds.size - fitted) * 0.5, fitted)
