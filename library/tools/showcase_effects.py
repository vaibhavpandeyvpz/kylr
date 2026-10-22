"""Cycles presentation of the generated combat gas meshes and materials."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

MATERIALS = Path(__file__).resolve().parents[1]/'models/effects/combat_effects'


def flame_material(name, energy, core=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    mix = nodes.new('ShaderNodeMixShader')
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    hot = nodes.new('ShaderNodeEmission')
    hot.inputs['Color'].default_value = (1, .88, .4, 1) if core else (1, .24, .018, 1)
    hot.inputs['Strength'].default_value = energy
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(MATERIALS/'muzzle_albedo_density.png'),check_existing=True)
    tex.image.colorspace_settings.name = 'Non-Color'
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .22
    ramp.color_ramp.elements[1].position = .8
    links.new(tex.outputs['Alpha'],ramp.inputs[0])
    links.new(ramp.outputs['Color'],mix.inputs[0])
    links.new(transparent.outputs[0],mix.inputs[1])
    links.new(hot.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],out.inputs['Surface'])
    return mat


def muzzle_flash(matrix, effect_piece):
    outer = flame_material('M_MuzzleOuter',5.5)
    core = flame_material('M_MuzzleJet',9.0,True)
    # Four runtime surfaces sampled at full growth with the short profile.
    for index,name in enumerate(('FlameEnvelope','Nozzle','PressureRing','VortexSheets')):
        obj = effect_piece('SK_'+name,matrix.translation,(1,1,1),core if index==1 else outer)
        uv = {}
        for loop in obj.data.loops:
            uv.setdefault(loop.vertex_index,obj.data.uv_layers.active.data[loop.index].uv.copy())
        for vertex in obj.data.vertices:
            u,v = uv[vertex.index]
            angle = u*math.tau
            along = .94+.025*math.sin(angle*3) if index==2 else v
            lobes = 1+.18*math.sin(angle*3+along*2)+.11*math.sin(angle*5-along*4)+.07*math.sin(angle*9)
            body = max(math.sin(math.pi*along),0)**.7*(1-along*.65) if index==1 else along**.7
            radius = (.004+(.018 if index==1 else .055)*body)*lobes
            if index==2: radius=.055*(.8+v*.2)*lobes
            vertex.co = (math.cos(angle)*radius,-along*(.29 if index==1 else .0725),math.sin(angle)*radius)
        obj.rotation_euler = matrix.to_euler()
        obj.visible_shadow = False


def cloud_material(name, burning):
    """Closed spatial gas with wrapped billow density and 3D turbulence."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    n,links=mat.node_tree.nodes,mat.node_tree.links
    n.clear()
    out=n.new('ShaderNodeOutputMaterial')
    volume=n.new('ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value=(.16,.12,.09,1)
    volume.inputs['Anisotropy'].default_value=.15
    coord=n.new('ShaderNodeTexCoord')
    noise=n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=5.2
    noise.inputs['Detail'].default_value=4
    links.new(coord.outputs['Generated'],noise.inputs['Vector'])
    tex=n.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(MATERIALS/'rocket_cloud_albedo_height.png'),check_existing=True)
    tex.image.colorspace_settings.name='Non-Color'
    links.new(coord.outputs['UV'],tex.inputs['Vector'])
    multiply=n.new('ShaderNodeMath');multiply.operation='MULTIPLY'
    links.new(noise.outputs['Fac'],multiply.inputs[0]);links.new(tex.outputs['Alpha'],multiply.inputs[1])
    density=n.new('ShaderNodeMapRange')
    density.inputs['From Min'].default_value=.21
    density.inputs['From Max'].default_value=.42
    links.new(multiply.outputs[0],density.inputs['Value'])
    distance=n.new('ShaderNodeVectorMath');distance.operation='DISTANCE'
    distance.inputs[1].default_value=(.5,.5,.5)
    links.new(coord.outputs['Generated'],distance.inputs[0])
    edge=n.new('ShaderNodeMapRange')
    edge.inputs['From Min'].default_value=.27
    edge.inputs['From Max'].default_value=.5
    edge.inputs['To Min'].default_value=1
    edge.inputs['To Max'].default_value=0
    links.new(distance.outputs['Value'],edge.inputs['Value'])
    field=n.new('ShaderNodeMath');field.operation='MULTIPLY'
    links.new(density.outputs[0],field.inputs[0]);links.new(edge.outputs[0],field.inputs[1])
    extinction=n.new('ShaderNodeMath');extinction.operation='MULTIPLY'
    extinction.inputs[1].default_value=2 if burning else 4
    links.new(field.outputs[0],extinction.inputs[0])
    links.new(extinction.outputs[0],volume.inputs['Density'])
    if burning:
        heat=n.new('ShaderNodeValToRGB')
        heat.color_ramp.elements[0].position=.28
        heat.color_ramp.elements[0].color=(.025,.0007,0,1)
        heat.color_ramp.elements[1].position=.62
        heat.color_ramp.elements[1].color=(1,.48,.03,1)
        links.new(noise.outputs['Fac'],heat.inputs[0])
        links.new(heat.outputs['Color'],volume.inputs['Emission Color'])
        energy=n.new('ShaderNodeMath');energy.operation='MULTIPLY'
        energy.inputs[1].default_value=14
        links.new(field.outputs[0],energy.inputs[0])
        links.new(energy.outputs[0],volume.inputs['Emission Strength'])
    links.new(volume.outputs[0],out.inputs['Volume'])
    return mat


def rocket_burst(location, effect_piece):
    origin=Vector(location)
    fire=cloud_material('M_RocketBurningGas',True)
    soot=cloud_material('M_RocketCoolingGas',False)
    # A sampled early expansion of the runtime three fuel / five soot lobes.
    for index,offset in enumerate([(-.45,.25,.2),(.4,-.15,.35),(0,0,.8)]):
        effect_piece('SK_ThermalShell',origin+Vector(offset),(1.7,1.7,1.7),fire,(index*.2,index*.4,index*.7))
    for index,offset in enumerate([(-.7,-.15,.45),(.65,.15,.6),(.05,-.55,1),(.15,.65,.3),(-.25,-.7,.25)]):
        effect_piece('SK_ThermalShell',origin+Vector(offset),(1.55,1.55,1.55),soot,(index*.3,index*.5,index*.2))
