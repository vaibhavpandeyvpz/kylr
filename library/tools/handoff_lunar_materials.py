"""Hand off regenerated lunar PBR materials while preserving runtime geometry.

Run with library/.venv/Scripts/python.exe. Shared image URIs avoid uploading a
separate copy of the same regolith textures for every imported model.
"""
from pathlib import Path
import copy,hashlib,json,os,struct
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT.parent/'game'
ROLES={'M_Regolith','M_RegolithLight','M_RegolithDark'}

def role(name):return name.split('.')[0].removesuffix('_Diffuse')

def read(path):
    data=path.read_bytes()
    magic,version,length=struct.unpack_from('<III',data)
    assert magic==0x46546c67 and version==2 and length==len(data),path
    size,kind=struct.unpack_from('<II',data,12)
    document=json.loads(data[20:20+size])
    start=20+size
    binary=b''
    if start<len(data):
        size,kind=struct.unpack_from('<II',data,start)
        assert kind==0x004e4942,path
        binary=data[start+8:start+8+size]
    return document,binary

def texture_infos(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key.endswith('Texture') and isinstance(item,dict) and 'index' in item:yield item
            else:yield from texture_infos(item)
    elif isinstance(value,list):
        for item in value:yield from texture_infos(item)

def visit_views(value,found=None,remap=None):
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='bufferViews':continue
            if key=='bufferView':
                if found is not None:found.add(item)
                if remap is not None:value[key]=remap[item]
            else:visit_views(item,found,remap)
    elif isinstance(value,list):
        for item in value:visit_views(item,found,remap)

def geometry(document,binary):
    digest=hashlib.sha256()
    for key in ('nodes','meshes','skins','animations','scenes','scene'):
        digest.update(json.dumps(document.get(key),sort_keys=True).encode())
    for accessor in document.get('accessors',[]):
        metadata=copy.deepcopy(accessor)
        views=set();visit_views(metadata,views)
        visit_views(metadata,remap={index:0 for index in views})
        digest.update(json.dumps(metadata,sort_keys=True).encode())
        for index in sorted(views):
            view=document['bufferViews'][index]
            start=view.get('byteOffset',0)
            digest.update(binary[start:start+view['byteLength']])
    return digest.hexdigest()

def compact(document,binary):
    used_textures={item['index'] for item in texture_infos(document.get('materials',[]))}
    mapping={old:new for new,old in enumerate(sorted(used_textures))}
    for item in texture_infos(document.get('materials',[])):item['index']=mapping[item['index']]
    document['textures']=[document['textures'][old] for old in sorted(used_textures)]
    # Repeated handoffs must not retain the old embedded-image samplers or
    # append another identical sampler for each canonical texture.
    samplers=document.get('samplers',[])
    used_samplers=sorted({texture['sampler'] for texture in document['textures'] if 'sampler' in texture})
    sampler_mapping={};unique_samplers=[];sampler_keys={}
    for index in used_samplers:
        assert 0<=index<len(samplers),'Invalid texture sampler'
        key=json.dumps(samplers[index],sort_keys=True)
        if key not in sampler_keys:
            sampler_keys[key]=len(unique_samplers);unique_samplers.append(samplers[index])
        sampler_mapping[index]=sampler_keys[key]
    for texture in document['textures']:
        if 'sampler' in texture:texture['sampler']=sampler_mapping[texture['sampler']]
    document['samplers']=unique_samplers
    used_images={item['source'] for item in document['textures']}
    mapping={old:new for new,old in enumerate(sorted(used_images))}
    for item in document['textures']:item['source']=mapping[item['source']]
    document['images']=[document['images'][old] for old in sorted(used_images)]
    used=set();visit_views(document,used)
    mapping={old:new for new,old in enumerate(sorted(used))}
    blocks=bytearray();views=[]
    for index in sorted(used):
        view=copy.deepcopy(document['bufferViews'][index])
        assert view.get('buffer',0)==0,'Only GLB-local buffers are supported'
        blocks.extend(b'\0'*(-len(blocks)%4))
        start=view.get('byteOffset',0)
        data=binary[start:start+view['byteLength']]
        view['byteOffset']=len(blocks);blocks.extend(data);views.append(view)
    visit_views(document,remap=mapping)
    document['bufferViews']=views
    document['buffers']=[{'byteLength':len(blocks)}]
    return bytes(blocks)

def encode(document,binary):
    encoded=json.dumps(document,separators=(',',':'),ensure_ascii=False).encode()
    encoded+=b' '*(-len(encoded)%4)
    binary+=b'\0'*(-len(binary)%4)
    chunks=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    return struct.pack('<III',0x46546c67,2,12+len(chunks))+chunks

def handoff(path):
    document,binary=read(path)
    lunar=[i for i,m in enumerate(document.get('materials',[])) if role(m.get('name','')) in ROLES]
    if not lunar:return None
    source=ROOT/'models'/path.relative_to(GAME/'assets/models')
    authored,_=read(source)
    materials={role(m.get('name','')):m for m in authored['materials']}
    before=geometry(document,binary)
    textures={}
    for index in lunar:
        original=document['materials'][index]
        material=copy.deepcopy(materials[role(original['name'])])
        material['name']=original['name']
        for info in texture_infos(material):
            source_texture=authored['textures'][info['index']]
            image=authored['images'][source_texture['source']]
            name=image.get('name','').split('.')[0]
            assert name in {'regolith_albedo','regolith_normal','regolith_orm'},(source,name)
            if name not in textures:
                image_index=len(document.setdefault('images',[]))
                uri=os.path.relpath(GAME/'assets/textures/lunar_surface'/(name+'.png'),path.parent).replace('\\','/')
                document['images'].append({'name':name,'uri':uri})
                texture={'source':image_index}
                if 'sampler' in source_texture:
                    texture['sampler']=len(document.setdefault('samplers',[]))
                    document['samplers'].append(copy.deepcopy(authored['samplers'][source_texture['sampler']]))
                textures[name]=len(document.setdefault('textures',[]))
                document['textures'].append(texture)
            info['index']=textures[name]
        document['materials'][index]=material
    binary=compact(document,binary)
    assert geometry(document,binary)==before,(path,'Geometry, skinning, placement or animation changed')
    return encode(document,binary),{'path':str(path.relative_to(GAME)),'geometry_sha256':before,'materials':len(lunar),'textures':sorted(textures)}

if __name__=='__main__':
    pending=[]
    for path in sorted((GAME/'assets/models').rglob('*.glb')):
        result=handoff(path)
        if result:pending.append((path,*result))
    assert len(pending)==32,('Unexpected regolith export coverage',len(pending))
    for path,data,report in pending:
        temporary=path.with_suffix('.glb.tmp');temporary.write_bytes(data);temporary.replace(path)
        print('LUNAR_HANDOFF',report['path'],'geometry preserved',flush=True)
    destination=GAME/'reports/performance/lunar-material-handoff.json'
    destination.write_text(json.dumps([row[2] for row in pending],indent=2)+'\n')
