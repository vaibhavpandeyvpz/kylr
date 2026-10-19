"""Library-only bio cluster rifle. Procedural source and mechanical animations.

Uses the established EMP mesh/rig/check/export kit and long-gun contact geometry.
The receiver, pressure barrel, glass accumulator and feed circuit are authored here.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_BioAmmoLiquid': 'Emissive',
    'M_BioLiquid': 'Emissive',
    'M_Bronze': 'Metallic',
    'M_Frame': 'Metallic',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Metal': 'Metallic',
    'M_Receiver': 'Metallic',
    'M_Screen': 'Emissive',
    'M_Secondary': 'Diffuse',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bio_framework', HERE.parent/'emp_gun/model.py')
k = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = k
spec.loader.exec_module(k)
rifle_spec = importlib.util.spec_from_file_location('bio_rifle_contacts', HERE.parent/'rifle/model.py')
r = importlib.util.module_from_spec(rifle_spec)
sys.modules[rifle_spec.name] = r
rifle_spec.loader.exec_module(r)

k.NAME, k.TITLE, k.HERE = 'bio_rifle', 'BioRifle', HERE
k.BLEND_PATH = HERE/'bio_rifle.blend'
k.RIG_JSON_PATH = HERE/'bio_rifle_rig.json'
Z = .276
BIO = 'M_Bio'
SCREEN = 'M_Screen'
LIQUID = 'M_BioLiquid'
RECEIVER = 'M_Receiver'
AMMO_LIQUID = 'M_BioAmmoLiquid'
k.SLOTS += [BIO, SCREEN, LIQUID, RECEIVER, AMMO_LIQUID]
k.MATERIALS[BIO] = ((.04,.24,.008),.0,.24,.20)
k.MATERIALS[k.GLS] = ((.06,.35,.025),0,.10,0,.10)
k.MATERIALS[RECEIVER] = ((.075,.085,.095),.75,.28,0)
k.MATERIALS[AMMO_LIQUID] = ((.025,.30,.006),0,.19,.15)
k.MATERIALS[LIQUID] = ((.025,.30,.006),0,.19,.15)
k.MATERIALS[SCREEN] = ((.08,.65,.025),0,.4,3)
k.JOINT_SPECS = [
 ('Root',None,'fixed',(0,0,0),k.UP,k.UP,None),
 (k.BARREL,'Root','slide',(0,-.045,Z),k.BACK,None,(0,.010)),
 ('BioValve','Root','hinge',(.027,-.057,.220),k.UP,k.FWD,(0,30)),
 (k.TRIGGER,'Root','hinge',k.TRIGGER_PIVOT,(1,0,0),k.DOWN,(0,k.TRIGGER_PULL)),
 (k.MAG,'Root','slide',(0,k.POST[0],k.BATTERY[2][0]),k.DOWN,None,(0,k.MAG_TRAVEL)),
 (k.CATCH_BONE,'Root','slide',(0,k.CATCH[0],k.CATCH[1]),k.LEFT,None,(0,k.CATCH_TRAVEL)),
]
k.PISTON_SPECS=[]
# Weapon clips are in-place; only machinery moves, at the shared 30 fps.
N=24
k.ANIMATIONS={
 'idle':(True,'LINEAR',{k.BARREL:k.hold_keys(0,60),'BioValve':k.hold_keys(0,60),k.TRIGGER:k.hold_keys(0,60)}),
 'fire_start':(False,'LINEAR',{k.TRIGGER:k.eased([(0,0),(3,k.TRIGGER_PULL),(8,k.TRIGGER_PULL)]),'BioValve':k.eased([(0,0),(2,0),(8,30)])}),
 'fire':(True,'LINEAR',{k.TRIGGER:k.hold_keys(k.TRIGGER_PULL,30),'BioValve':k.wave(30,lambda u:30-2*(1-math.cos(2*math.pi*u))/2),k.BARREL:k.recoil_pulse()}),
 'fire_end':(False,'LINEAR',{k.TRIGGER:k.eased([(0,k.TRIGGER_PULL),(3,0),(14,0)]),'BioValve':k.eased([(0,30),(3,30),(14,0)]),k.BARREL:k.hold_keys(0,14)}),
 'mag_release':(False,'LINEAR',{k.CATCH_BONE:k.eased([(0,0),(4,k.CATCH_TRAVEL),(N,k.CATCH_TRAVEL)]),k.MAG:k.eased([(0,0),(4,0),(16,k.MAG_TRAVEL),(N,k.MAG_TRAVEL)])}),
 'mag_insert':(False,'LINEAR',{k.MAG:k.eased([(0,k.MAG_TRAVEL),(16,0),(N,0)]),k.CATCH_BONE:k.eased([(0,k.CATCH_TRAVEL),(16,k.CATCH_TRAVEL),(20,0),(N,0)])}),
 'reload':(False,'LINEAR',{k.MAG:k.eased([(0,0),(4,0),(16,k.MAG_TRAVEL),(30,k.MAG_TRAVEL),(46,0),(54,0)]),k.CATCH_BONE:k.eased([(0,0),(4,k.CATCH_TRAVEL),(46,k.CATCH_TRAVEL),(50,0),(54,0)]),'BioValve':k.hold_keys(0,54),k.TRIGGER:k.hold_keys(0,54)}),
 'valve_open':(False,'LINEAR',{'BioValve':k.eased([(0,0),(18,30),(24,30)])}),
 'valve_close':(False,'LINEAR',{'BioValve':k.eased([(0,30),(18,0),(24,0)])})}
# Each action owns every mechanical channel, so direct playback cannot inherit
# an open latch or detached pack from a previous clip.
for _,(_,_,keys) in k.ANIMATIONS.items():
 end=max(f for ks in keys.values() for f,_ in ks)
 for name,_,kind,*_spec in k.JOINT_SPECS:
  if kind!='fixed':keys.setdefault(name,k.hold_keys(0,end))
k.FK_TEST_STATE={'BioValve':10,k.BARREL:.006,k.TRIGGER:5,k.MAG:.01,k.CATCH_BONE:.004}
k.PREVIEW_STATES={'valve_open':{'BioValve':30},'recoil':{k.BARREL:.010},'pack_out':{k.MAG:k.MAG_TRAVEL,k.CATCH_BONE:k.CATCH_TRAVEL}}
k.PREVIEW_VIEWS={'valve_open':['front_left'],'recoil':['left'],'pack_out':['front_left']}
k.SHOWCASE=['idle','fire_start','fire','fire','fire_end','reload','valve_open','valve_close','idle']

def side_poly(x,y0,y1,z0,z1,c=.003):
 return [(x,y,z) for y,z in [(y0+c,z0),(y1-c,z0),(y1,z0+c),(y1,z1-c),(y1-c,z1),(y0+c,z1),(y0,z1-c),(y0,z0+c)]]

def lower_ring(y):
 zt=.184 if y<=-.125 else (.192 if y>=-.044 else .184+.008*(y+.125)/.081)
 pts=k.keel_points(y)+[(.032,zt-.005),(.027,zt)]
 return [Vector((x,y,z)) for x,z in pts+[(-x,z) for x,z in reversed(pts)]]

def shell_ring(y):
 # A single profiled pressure receiver, narrow behind the chamber shoulder.
 t=max(0,min(1,(y+.030)/.075))
 w=.047-.015*t
 top=.322-.012*t
 if y>.160:
  w-=.004*(y-.160)/.015
  top-=.024*(y-.160)/.015
 # Machined radiused cross section: three tangent steps per quarter-round.
 rad=.008
 corners=[(w-rad,.192+rad,-90), (w-rad,top-rad,0),
          (-w+rad,top-rad,90), (-w+rad,.192+rad,180)]
 return [Vector((cx+rad*math.cos(math.radians(a+i*30)),y,
                 cz+rad*math.sin(math.radians(a+i*30))))
         for cx,cz,a in corners for i in range(4)]

def build_shell(kit):
 # The black contact keel is separate from the pressure receiver casting.
 k.carve(kit,k.loft([-.292,-.289,-.180,-.125,-.044,.158,.160,.173,.175],lower_ring),'Root',k.SEC,
         boxes=[((0,k.POST[0],.166),(.014,.014,.018))])
 bores=[((0,-.060,Z),(0,.086,Z),.0294,12),
        ((0,k.POST[0],.155),(0,k.POST[0],.191),k.POST[1]+.00015,12)]
 # Open upper frame exposes the pressure train instead of broad armour plates.
 # Front and rear bulkheads retain the barrel bore and stock load path.
 k.carve(kit,k.loft([-.044,-.041,-.030,.045,.158,.160,.173,.175],shell_ring),'Root',RECEIVER,
         cuts=bores,boxes=[((0,.099,.292),(.120,.098,.110))],
         subtract=[(side_poly(0,-.018,.041,.255,.295,.005),k.LEFT,.20)])
 # Turned batch chamber: cylindrical liner, seal grooves, shoulder and lock rings.
 # Its front end seats behind the recoil throat; rear end enters the bulkhead.
 profile=[(0,-.014),(.027,-.014),(.027,.056),(.030,.056),
          (.032,.059),(.032,.068),(.027,.071),(.027,.080),
          (.027,.132),
          (.032,.135),(.032,.145),(.029,.148),(.027,.151),(0,.151)]
 k.lathe(kit,profile,'Root',k.MTL,segs=12,cz=Z,loop=True)
 # Thin captured conductive seal bands sit between turned radial shoulders.
 for a,b in [(.072,.078)]:
  k.lathe(kit,[(.027,a),(.028,a),(.028,b),(.027,b)],'Root',k.BRZ,segs=12,cz=Z,loop=True)
 # A keyed axial rib is machined into the upper chamber's service spine.
 kit.box((0,.102,.303),(.010,.064,.010),'Root',RECEIVER,bevel=.001)
 # Display pedestal is seated on the lower web and fits behind its bezel.
 kit.box((.026,.115,.251),(.012,.034,.032),'Root',RECEIVER,bevel=.001)
 # Opposite flank carries an inset circular service plug on a bored mounting land.
 mount=k.Kit()
 mount.box((-.027,.103,.246),(.012,.026,.026),'Root',RECEIVER,bevel=.002)
 k.carve(kit,mount.bm,'Root',RECEIVER,
         cuts=[((-.036,.103,.246),(-.024,.103,.246),.0071,12)])
 kit.cyl((-.033,.103,.246),(-.025,.103,.246),.0069,'Root',k.JNT,segs=12)
 kit.cyl((-.034,.103,.246),(-.033,.103,.246),.0035,'Root',k.MTL,segs=6)
 # Front sleeve seated in the receiver bore and its front shoulder.
 sleeve=k.Kit()
 k.lathe(sleeve,[(.0294,-.067),(.037,-.067),(.040,-.062),(.040,-.047),(.038,-.044),(.0294,-.044)],'Root',k.FRM,segs=12,cz=Z,loop=True)
 # Machine a flat on the fixed collar, normal to the heavy feed fitting axis.
 k.carve(kit,sleeve.bm,'Root',k.FRM,boxes=[((.048,-.0555,Z),(.024,.030,.100))])
 for az in (45,135,225,315):
  x=.034*math.cos(math.radians(az));z=Z+.034*math.sin(math.radians(az))
  k.bolt(kit,(x,-.067,z),k.FWD,'Root',r=.0021,head=.001)

def build_barrel(kit):
 # Continuous turned shell: pressure throat, two machined fin banks and nozzle.
 outer=[(.041,-.362),(.045,-.358),(.045,-.331),(.041,-.327),(.029,-.327)]
 for y0,y1 in [(-.319,-.291),(-.244,-.220)]:
  outer += [(.029,y0)]
  for j in range(2):
   a=y0+j*(y1-y0)/2
   outer += [(.040,a),(.040,a+.0045),(.029,a+.006)]
  outer += [(.029,y1)]
 outer += [(.029,-.025),(.018,-.025),(.018,-.327),(.025,-.327),(.025,-.362)]
 turned=k.Kit()
 k.lathe(turned,outer,k.BARREL,k.JNT,segs=12,cz=Z,loop=True)
 # Four machined relief windows reveal the dark replaceable nozzle liner.
 ports=[((sx*.038,-.347,Z),(.028,.012,.014)) for sx in (-1,1)]
 ports += [((0,-.347,Z+sz*.038),(.014,.012,.028)) for sz in (-1,1)]
 k.carve(kit,turned.bm,k.BARREL,k.JNT,boxes=ports)
 # A ported replaceable ceramic nozzle liner, flush behind the steel muzzle lip.
 k.lathe(kit,[(.016,-.361),(.025,-.361),(.025,-.340),(.016,-.340)],k.BARREL,k.MTL,segs=12,cz=Z,loop=True)
 # Black sight-dark bore face is well inside the nozzle, not an exposed cap.
 kit.cyl((0,-.315,Z),(0,-.313,Z),.018,k.BARREL,k.SEC,segs=8)
 # Two split-free protective collars; their bore exactly seats on the tube.
 for a,b in [(-.278,-.269),(-.163,-.154)]:
  k.lathe(kit,[(.029,a),(.042,a),(.044,a+.002),(.044,b-.002),(.042,b),(.029,b)],k.BARREL,k.MTL,segs=12,cz=Z,loop=True)
 # Structural longitudinal guard rods anchor on flats machined into collar tops.
 # Each rod is supported through the collars, rather than hovering above them.
 for sx in (-1,1):
  kit.cyl((sx*.020,-.275,.312),(sx*.020,-.159,.312),.0025,k.BARREL,k.JNT,segs=8)

def build_reservoir(kit):
 # A real pressure-vessel load path: shell/end closures -> bolted saddles -> keel.
 # Fluid is contained behind a protected sight sleeve, never painted on the shell.
 rz=.207
 # Green 10%-opaque pressure glass is captured by the end closures and saddles.
 k.lathe(kit,[(.0180,-.274),(.0205,-.274),(.0205,-.066),(.0180,-.066)],
         'Root',k.GLS,segs=12,cz=rz,loop=True)
 # Turned front closure has a flat central service-plug seat and a domed shoulder.
 front=k.Kit()
 k.lathe(front,[(0,-.289),(.011,-.289),(.022,-.278),
               (.022,-.274),(.018,-.274),(0,-.274)],'Root',k.MTL,segs=12,cz=rz,loop=True)
 k.carve(kit,front.bm,'Root',k.MTL,
         cuts=[((0,-.290,rz),(0,-.285,rz),.0051,8)])
 kit.cyl((0,-.289,rz),(0,-.283,rz),.0048,'Root',k.JNT,segs=6)
 # Rear valve head closes the vessel and provides a flat compression-fitting land.
 head=k.Kit()
 k.lathe(head,[(0,-.066),(.020,-.066),(.022,-.063),(.022,-.050),
              (.017,-.044),(0,-.044)],'Root',k.MTL,segs=12,cz=rz,loop=True)
 # Flat inlet land: the whole hex nut footprint seats on this plane.
 k.carve(kit,head.bm,'Root',k.MTL,boxes=[((.029,-.055,rz),(.020,.040,.070))])
 # Captive metallic seal seats; the elastomer gaskets are inside these shoulders.
 for a,b in [(-.276,-.271),(-.069,-.064)]:
  k.lathe(kit,[(.0205,a),(.0215,a),(.0215,b),(.0205,b)],'Root',k.JNT,segs=12,cz=rz,loop=True)
 # Two bored saddle castings with integral feet. All feet land on the keel's flat.
 for y in (-.256,-.132):
  upper=[(.023*math.cos(math.radians(a)),rz+.023*math.sin(math.radians(a)))
         for a in [i*22.5 for i in range(11)]]
  outline=upper+[(-.026,.190),(-.026,.184),(.026,.184),(.026,.190),(.0163,.1907),(.02125,.1982)]
  holes=[((0,y-.005,rz),(0,y+.005,rz),.02055,12)]
  holes += [((x,y,.181),(x,y,.192),.0017,8) for x in (-.023,.023)]
  kit.plate([(x,y,z) for x,z in outline],.006,k.BACK,'Root',k.FRM,cuts=holes)
  for x in (-.023,.023):
   kit.cyl((x,y,.181),(x,y,.191),.0015,'Root',k.JNT,segs=6,solid=False)
 # One short delivery line. Return/bleed runs inside the fixed rear valve head.
 # Both elbows are properly bent; fittings terminate on machined flat lands.
 kit.cyl((.019,-.057,rz),(.030,-.057,rz),.0080,'Root',k.FRM,segs=6)
 pts=[(.030,-.057,rz),(.054,-.057,rz),(.054,-.057,Z),(.036,-.057,Z)]
 kit.tube(k.fillet(pts,.0105),.0035,'Root',k.JNT,sides=8)
 # A vertical valve spindle and a separately rigged shutoff lever.
 kit.cyl((.027,-.057,.211),(.027,-.057,.220),.0025,'Root',k.JNT,segs=8)
 kit.cyl((.027,-.057,.218),(.027,-.057,.223),.0035,'BioValve',k.JNT,segs=8)
 kit.plate([(.024,-.055,.221),(.030,-.055,.221),(.030,-.079,.221),(.024,-.079,.221)],
           .002,k.UP,'BioValve',k.JNT)
 kit.plate([(.024,-.079,.221),(.030,-.079,.221),(.030,-.088,.221),(.024,-.088,.221)],
           .002,k.UP,'BioValve',k.SEC)
 # Rear valve block has an explicit structural mount, clear of the barrel slide.
 kit.box((0,-.049,.233),(.019,.012,.020),'Root',k.MTL,bevel=.002)


def build_liquid(kit):
 fluid=k.Kit()
 fluid.cyl((0,-.260,.207),(0,-.079,.207),.0172,'Root',LIQUID,segs=16)
 # Exactly half the circular chamber, with a level planar surface through its axis.
 k.carve(kit,fluid.bm,'Root',LIQUID,
         intersect=[(k.rect(.040,.100,.187,cb=-.164),k.UP,.040)])


def build_display(kit):
 # Lower-web pedestal supports the bezel; no text or painted graphics.
 outer=side_poly(.035,.080,.150,.243,.280)
 inner=side_poly(.037,.087,.143,.249,.274,.002)
 kit.plate(outer,.006,k.LEFT,'Root',k.MTL,subtract=[(inner,k.LEFT,.003)],bevel=.0006)
 kit.plate(side_poly(.0358,.088,.142,.250,.273,.002),.0006,k.LEFT,'Root',SCREEN)
 kit.plate(side_poly(.0367,.088,.142,.250,.273,.002),.0006,k.LEFT,'Root',k.GLS)
 for y in (.084,.146):
  k.bolt(kit,(.038,y,.2615),k.LEFT,'Root',r=.0015,head=.0005)

# Keyed cassette with sealed glass bio cartridges behind the two side windows.
# User requested glass and independent half-filled liquid for this pack.
def build_pack(kit):
 (b0,b1),w,(z0,z1)=k.BATTERY
 ym=(b0+b1)/2
 slots=[((sx*w,ym,.117),(.010,.040,.025)) for sx in (-1,1)]
 outline=[(w,z0),(w,z1-.003),(w-.003,z1),(-w+.003,z1),(-w,z1-.003),(-w,z0)]
 kit.plate([(x,ym,z) for x,z in outline],b1-b0,k.BACK,k.MAG,RECEIVER,boxes=slots,bevel=.001)
 kit.box((0,ym,.0775),(.083,.059,.015),k.MAG,k.SEC,bevel=.003)
 for sx in (-1,1):
  for y in (-.002,.014,.030):
   k.revolve(kit,[(.0048,.090),(.0055,.090),(.0055,.144),(.0048,.144)],
             (sx*.031,y,0),k.UP,(1,0,0),k.MAG,k.GLS,segs=12,loop=True)
   for a,b in [(.089,.091),(.143,.145)]:
    kit.cyl((sx*.031,y,a),(sx*.031,y,b),.0055,k.MAG,k.MTL,segs=12)
 for x in k.BLADES[0]:
  kit.box((x,-.001,.1535),(.0015,.010,.008),k.MAG,k.BRZ)
 py,pr,top,(g0,g1),dep=k.POST
 k.revolve(kit,[(0,z1-.001),(pr,z1-.001),(pr,g0),(pr-dep,g0+.0003),(pr-dep,g1-.0003),(pr,g1),(pr,top-.0012),(pr-.0012,top),(0,top)],
           (0,py,0),k.UP,(1,0,0),k.MAG,k.JNT,segs=12)


def build_pack_liquid(kit):
 # Each cartridge holds liquid to its vertical midpoint. The six closed volumes
 # share one separate shader mesh/material, independently of the glass shell.
 for sx in (-1,1):
  for y in (-.002,.014,.030):
   kit.cyl((sx*.031,y,.0915),(sx*.031,y,.117),.0045,k.MAG,AMMO_LIQUID,segs=12)


def build_stock(kit):
 # Raised rifle-length shoulder rest, separate from the firing grip; no cheek riser.
 f,b,e=r.STOCK_Y
 dz=.083  # Buttpad centre .174 + .083 = receiver centre .257 m.
 ring=lambda y:[Vector((x,y,z+dz)) for x,z in r.stock_section(y,max(0,.002-(y-f)))]
 (y0,y1),(tz,bz)=r.STOCK_HOLE
 hole=r.rounded([(y0,r.COMB_Z-tz),(y0,r.stock_bottom(y0)+bz),(y1,r.stock_bottom(y1)+bz),(y1,r.COMB_Z-tz)],[.008]*4,n=2)
 k.carve(kit,k.loft([f,f+.002,b],ring),'Root',k.SEC,
         holes=[[Vector((0,y,z+dz)) for y,z in hole]],bevel_normal=k.LEFT)
 pad=lambda y:[Vector((x,y,z+dz)) for x,z in r.stock_section(b)]
 grooves=[((0,e,z+dz),(.036,.003,.0025)) for z in (.118,.141,.164,.187,.210)]
 k.carve(kit,k.loft([b,e],pad),'Root',k.MTL,boxes=grooves,bevel=.001,bevel_normal=k.BACK)
 for sx in (-1,1):
  kit.cyl((sx*.012,.163,r.BORE_Z+dz),(sx*.012,.191,r.BORE_Z+dz),.004,'Root',k.JNT,segs=8)
  k.bolt(kit,(sx*.020,.187,.209+dz),(sx,0,0),'Root',r=.002,head=.001)


def hand_frame(side):
 if side=='Right': return r.hand_frame(side)
 # Same rifle support wrist orientation and tilt, fitted to the fixed bio dock.
 angle=math.radians(r.LSUP_TILT)
 z=Vector((-1,0,0)); y=Vector((0,-math.cos(angle),-math.sin(angle)))
 x=y.cross(z)
 grip=Vector((k.DOCK[1]+.0003,k.DOCK[0][0]+.004,.145))
 return grip-z*k.PALM[3]-y*k.GRIP_ALONG[side],x,y,z
k.hand_frame=hand_frame
k.GRIP_POSE['Left']=r.GRIP_POSE['Left']

def build_gun(kit,pistons,joints):
 build_shell(kit);build_barrel(kit);build_reservoir(kit);build_display(kit)
 # Service loom: both gland axes normal to the same machined side plane.
 # The centreline stays at z=.218, 9 mm outside x=-.032; bends have 3 mm radius.
 pts=[(-.032,.140,.218),(-.041,.140,.218),(-.041,.062,.218),(-.032,.062,.218)]
 kit.tube(k.fillet(pts,.003),.0012,'Root',k.SEC,sides=6)
 # Bored, screw-fastened clamp blocks land squarely on that receiver plane.
 for y in (.086,.116):
  outline=[(-.032,y,.213),(-.0425,y,.213),(-.044,y,.2145),
           (-.044,y,.2215),(-.0425,y,.223),(-.032,y,.223)]
  kit.plate(outline,.003,k.BACK,'Root',k.MTL,
            cuts=[((-.041,y-.002,.218),(-.041,y+.002,.218),.0013,6)])
  kit.cyl((-.031,y,.2215),(-.0445,y,.2215),.00085,'Root',k.JNT,segs=6,solid=False)
 r.build_grip(kit);k.build_trigger_housing(kit);k.build_trigger(kit);build_stock(kit)
 k.build_dock(kit);k.build_catch(kit)

def gizmo_specs():
 return [('Muzzle',k.BARREL,Vector((0,-.372,Z)),Vector(k.FWD),Vector(k.UP)),
         ('BioFeed','Root',Vector((0,-.048,.207)),Vector(k.FWD),Vector(k.UP))]

def sweep_states(joints):
 return [(f'valve {i}',{'BioValve':i}) for i in range(0,31,5)]+[(f'recoil {i}',{k.BARREL:i*.001}) for i in range(11)]+[(f'trigger {a}',{k.TRIGGER:a}) for a in range(0,13,2)]+[(f'catch {i}',{k.CATCH_BONE:i*.0025}) for i in range(5)]+[(f'pack {i}',{k.CATCH_BONE:k.CATCH_TRAVEL,k.MAG:i*k.MAG_TRAVEL/10}) for i in range(11)]

# Export the rifle-family socket contract and bio-specific mechanical metadata.

def write_metadata(ammo_frame,joints,pistons,tris,ammo_tris,size,dy):
 vec=lambda v:[round(float(c),6) for c in v]
 at=lambda v:Vector(v)+Vector((0,dy,0))
 godot=lambda v:vec((v[0],v[2],-v[1]))
 hands={}
 for side in ('Left','Right'):
  wrist,x,y,z=k.hand_frame(side)
  curls,(mx,mz,tc)=k.GRIP_POSE[side]
  pose={f'{side}{f}{seg}':[round(c*scale,1),0,0] for f,c in curls.items() for seg,scale in [('Proximal',1),('Intermediate',1.1),('Distal',.8)]}
  pose.update({f'{side}ThumbMetacarpal':[mx,0,mz],f'{side}ThumbProximal':[tc,0,0],f'{side}ThumbDistal':[tc,0,0]})
  hands[f'{side}HandSocket']={'hand_bone':f'{side}Hand','wrist_blender':vec(at(wrist)),'wrist_godot':godot(at(wrist)),'grip_pose_deg':pose,
     **{f'bone_{axis}_{space}':fn(v) for axis,v in zip('xyz',(x,y,z)) for space,fn in [('blender',vec),('godot',godot)]}}
 data={'name':k.NAME,'space':'metres; Blender Z up, muzzle -Y; Godot (x,z,-y); origin on bottom plane at length centre',
       'materials':k.SLOTS,'size_m':dict(wide=size.x,long=size.y,high=size.z,max_wide_long_high=list(k.WEAPON_MAX),bore_axis_height=Z),
       'triangles':{'SK_BioRifle':tris,'SM_BioRifleAmmo':ammo_tris},'triangle_budgets':{'SK_BioRifle':k.TRI_BUDGET,'SM_BioRifleAmmo':k.AMMO_BUDGET},
       'joints':[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=vec(at(j.pivot)),axis=vec(j.axis),range=j.limits) for j in joints.values()],
       'pistons':[],'hand_sockets':hands,'ammo_hand_socket':k.ammo_socket_json((at(ammo_frame[0]),*ammo_frame[1:])),
       'ammo':dict(bone=k.MAG,pickup_file='bio_rifle_ammo.glb',axis=[0,0,-1],travel_m=k.MAG_TRAVEL),
       'validation':dict(motion_sweep_states=len(sweep_states(joints)),character_clips='53 rifle-family clips and paired weapon tracks generated by animations/retarget.py')}
 data['liquid']={'mesh':'SK_BioRifleLiquid','material':LIQUID,'fill_fraction':.5,'surface_blender_z':.207,'glass_alpha':.10,'shader':'Game shader deferred; closed half-cylinder surface and volume retained, Root rigid skin, no collider'}
 data['rest']='pressure tube home; trigger released; bio cassette seated'
 data['animations']={name:{'frames':[0,max(f for keys in spec[2].values() for f,_ in keys)],'fps':k.FPS,'loop':spec[0],'joints':sorted(spec[2])} for name,spec in k.ANIMATIONS.items()}
 data['fire']={'concept':'one metered bio charge fragments into multiple acid flakes discharged simultaneously through one broad bore',
               'recoil_m':.010,'timing':'fire_start opens the feed valve; fire is one 30-frame/1-second recoil cycle with a cluster emission at frame 0; fire_end closes the valve'}
 data['gizmos']={'convention':'same exported marker basis as the other weapons',
                 'markers':[{'name':n,'bone':b,'position_blender':[p.x,p.y+dy,p.z],'forward':list(f),'up':list(u)} for n,b,p,f,u in gizmo_specs()]}
 data['usage']='Library asset; own mechanical actions authored. Game registration and liquid shader deferred.'
 data['ammo']['note']='Separate six-cartridge bio cassette; guarded insertion with keyed rails, lock post and cross bolt. mag_release / mag_insert and combined reload actions authored.'
 data['construction']={'pressure_path':'cassette to enclosed metering valve, lined batch cylinder, internal flexible coupling in the fixed sleeve, recoiling pressure tube and replaceable nozzle',
  'parts':'open lofted receiver frame, lathed batch chamber with locking shoulders and bronze seal band, axial service spine, recessed circular plug, black contact keel, pedestal-mounted display console, turned steel barrel, bolted saddle castings, green glass pressure vessel with a separate half-filled liquid volume',
  'materials':'M_Glass cartridge sleeves and separate M_BioAmmoLiquid; M_Glass green vessel at alpha 0.10; separate SK_BioRifleLiquid uses M_BioLiquid; pack glass at alpha 0.10 as requested',
  'extraction':'closed bio-feed system retains spent capsules internally; no external shell ejection port',
  'internals':'metering valve, capsule transfer and fragmentation internals described but not modelled',
  'hand_reference':'rifle firing wrist and support wrist orientation; support palm fitted to bio dock; rifle shoulder stock without raised cheek comb; rifle-family holds and bottom reload retargeted separately'}
 k.RIG_JSON_PATH.write_text(json.dumps(data,indent=2))

k.build_gun,k.build_pack,k.gizmo_specs,k.sweep_states,k.write_rig_json=build_gun,build_pack,gizmo_specs,sweep_states,write_metadata
k.build_preview_markers=lambda rig,dy:None
def export_asset(objects,stem):
 # Keep every baked FBX key: the small valve stroke must survive simplification.
 for obj in objects:
  if obj.type=='ARMATURE':
   for pb in obj.pose.bones:
    for constraint in list(pb.constraints):pb.constraints.remove(constraint)
   for fc in list(obj.animation_data.drivers if obj.animation_data else []):obj.animation_data.drivers.remove(fc)
 k.prepare_export(objects,k.HERE,stem);k.select_only(objects)
 bpy.ops.export_scene.fbx(filepath=str(k.HERE/f'{stem}.fbx'),use_selection=True,
  object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
  apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',bake_space_transform=False,
  use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
  primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
  bake_anim=True,bake_anim_use_all_bones=False,bake_anim_use_nla_strips=False,
  bake_anim_use_all_actions=True,bake_anim_force_startend_keying=True,
  bake_anim_simplify_factor=0,path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(k.HERE/f'{stem}.glb'),export_format='GLB',
  use_selection=True,export_yup=True,export_apply=False,export_skins=True,
  export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
  export_anim_single_armature=True,export_reset_pose_bones=True,export_force_sampling=True,
  export_optimize_animation_size=True,export_optimize_animation_keep_anim_armature=False,
  export_anim_slide_to_zero=True,export_materials='EXPORT')
k.export=export_asset

def export_pack(ammo,liquid,dy):
 P=Matrix.Translation(-Vector((0,k.POST[0]+dy,k.BUMPER[1][0])))
 objs=[]
 for source,name in [(ammo,'SM_BioRifleAmmo'),(liquid,'SM_BioRifleAmmoLiquid')]:
  mesh=source.data.copy();mesh.transform(P)
  obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj);objs.append(obj)
 k.prepare_export(objs,k.HERE,'bio_rifle_ammo');k.select_only(objs)
 bpy.ops.export_scene.fbx(filepath=str(k.HERE/'bio_rifle_ammo.fbx'),use_selection=True,
  object_types={'MESH'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',
  axis_forward='-Z',axis_up='Y',bake_space_transform=False,use_mesh_modifiers=False,
  mesh_smooth_type='OFF',add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(k.HERE/'bio_rifle_ammo.glb'),export_format='GLB',
  use_selection=True,export_yup=True,export_apply=False,export_skins=False,
  export_animations=False,export_materials='EXPORT')
 bpy.data.libraries.write(str(k.HERE/'bio_rifle_ammo.blend'),set(objs),fake_user=True)
 for obj in objs:
  mesh=obj.data;bpy.data.objects.remove(obj);bpy.data.meshes.remove(mesh)
 return P

def all_action_states(actions,joints):
 # Sample every authored frame, including loops, for clearance and visibility.
 states=[]
 for name,action in actions.items():
  curves=k.action_fcurves(action)
  for f in range(int(action.frame_range[0]),int(action.frame_range[1])+1):
   state={}
   for fc in curves:
    bone=fc.data_path.split('"')[1]
    if bone in joints:
     v=fc.evaluate(f);state[bone]=math.degrees(v) if joints[bone].kind=='hinge' else v
   states.append((f'{name} frame {f}',state))
 return states
k.action_states=all_action_states

def main():
 k.reset_scene();k.build_materials()
 joints=k.resolve_joints();pistons=k.resolve_pistons(joints)
 k.check_states(joints)
 rig=k.build_rig(joints,pistons);k.check_rig_fk(rig,joints)
 actions=k.build_actions(rig,joints,pistons)
 kit=k.Kit();build_gun(kit,pistons,joints);build_pack(kit)
 size,dy=k.check_envelope(kit)
 k.check_connectivity(kit,joints,pistons);k.check_joint_alignment(kit,joints)
 k.check_piston_clearance(pistons,joints,kit.solids,k.all_parts(kit))
 k.check_hand_sockets(kit);ammo_frame=k.check_ammo_socket(kit,joints)
 states=k.action_states(actions,joints)+sweep_states(joints)
 k.check_motion(kit,joints,states)
 print(f'[bio_rifle] checks passed ({len(states)} motion states)')
 gun,pack,fluid,pack_fluid=k.Kit(),k.Kit(),k.Kit(),k.Kit()
 build_gun(gun,pistons,joints);build_pack(pack);build_liquid(fluid);build_pack_liquid(pack_fluid)
 body=gun.to_object('SK_BioRifle',joints=k.rotary_joints(joints))
 ammo=pack.to_object('SK_BioRifleAmmo')
 liquid=fluid.to_object('SK_BioRifleLiquid')
 pack_liquid=pack_fluid.to_object('SK_BioRifleAmmoLiquid')
 k.check_coplanar(pack_liquid)
 pack_liquid_tris=k.triangles(pack_liquid)
 tris=k.finish(body,rig,joints,k.TRI_BUDGET,states)
 ammo_tris=k.finish(ammo,rig,joints,k.AMMO_BUDGET,[])
 # Preserve the closed liquid volume for a later shader, including submerged faces.
 k.check_coplanar(liquid);k.skin(liquid,rig);k.unwrap(liquid)
 liquid_tris=k.triangles(liquid)
 if tris+liquid_tris>k.TRI_BUDGET and '--no-cull' not in sys.argv:
  raise SystemExit(f'[bio_rifle] combined weapon budget exceeded: {tris+liquid_tris}')
 gizmos=k.build_gizmos(rig,gizmo_specs(),ammo_frame=ammo_frame)
 k.shift_gun(rig,[body,ammo,liquid,pack_liquid],dy)
 pack_frame=export_pack(ammo,pack_liquid,dy);mounts=k.build_mounts(rig,pack_frame)
 k.export([rig,body,liquid,*gizmos,*mounts],k.NAME)
 bpy.data.objects.remove(ammo);bpy.data.objects.remove(pack_liquid)
 k.constrain(rig,joints,pistons)
 write_metadata(ammo_frame,joints,pistons,tris,ammo_tris,size,dy)
 data=json.loads(k.RIG_JSON_PATH.read_text())
 if ammo_tris+pack_liquid_tris>k.AMMO_BUDGET:raise SystemExit('combined pack budget exceeded')
 data['ammo_liquid']={'mesh':'SM_BioRifleAmmoLiquid','material':AMMO_LIQUID,'fill_fraction':.5,'surface_pickup_z':.117-k.BUMPER[1][0],'radius_m':.0045,'cartridges':6,'shader':'independent liquid shader; no collider'}
 data['triangles']['SM_BioRifleAmmoLiquid']=pack_liquid_tris
 data['triangles']['ammo_total']=ammo_tris+pack_liquid_tris
 data['triangle_budgets']['SM_BioRifleAmmoLiquid']=500
 data['triangles']['SK_BioRifleLiquid']=liquid_tris
 data['triangles']['weapon_total']=tris+liquid_tris
 data['triangle_budgets']['SK_BioRifleLiquid']=500
 data['liquid']['centre_y_blender']=-.164+dy
 k.RIG_JSON_PATH.write_text(json.dumps(data,indent=2))
 k.add_mounts_json(pack_frame)
 def pose_entry(j,v):
  return {'rot':[v,0,0]} if joints[j].kind=='hinge' else {'loc':[0,v,0]}
 rig['preview_poses']=json.dumps({s:{j:pose_entry(j,v) for j,v in k.expand(st).items()} for s,st in k.PREVIEW_STATES.items()})
 rig['preview_pose_views']=json.dumps(k.PREVIEW_VIEWS)
 bpy.context.scene['preview_actions']=json.dumps(k.SHOWCASE)
 bpy.context.preferences.filepaths.save_version=0
 bpy.ops.wm.save_as_mainfile(filepath=str(k.BLEND_PATH),compress=True)
 print(f'[bio_rifle] saved; weapon {tris} + liquid {liquid_tris} = {tris+liquid_tris} triangles')

k.main=main
if __name__=='__main__': main()
