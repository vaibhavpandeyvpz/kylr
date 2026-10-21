"""CPU checks for terrain source contracts; rendered and physical QA are separate."""
from pathlib import Path
import importlib.util
import hashlib
import json
import sys
import unittest
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'models/maps/common'))
from planetary_field import field,foundations


class PlanetaryFieldTests(unittest.TestCase):
    def test_geological_layers_have_distinct_dominant_interiors(self):
        for map_id in ('faceoff','skyfall'):
            metadata=json.loads((ROOT/'.local/planetary'/f'{map_id}.json').read_text(encoding='utf-8'))
            x,z=np.meshgrid(np.arange(-36,37),np.arange(-36,37))
            _,weights=field(map_id,x,z,metadata['foundations'])
            self.assertTrue(np.isfinite(weights).all())
            self.assertTrue(np.allclose(weights.sum(axis=-1),1.0))
            for index in (0,1,2,3):
                self.assertGreater(float((weights[...,index]>.65).mean()),.04,
                    f'{map_id} layer {index} retains visible patches rather than a uniform blend')
            if map_id=='faceoff':
                self.assertGreater(float((weights[...,4]>.65).mean()),.1,'Compacted ground remains readable near fixtures')
            self.assertLess(float((weights.argmax(axis=-1)==0).mean()),.5,'Dust does not dominate the whole arena')

    def test_deployed_lander_footprint_is_supported_between_baked_grid_samples(self):
        folder=ROOT/'models/maps/faceoff'
        spec=importlib.util.spec_from_file_location('lander_terrain_layout',folder/'layout.py')
        layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
        markers=layout.data()[0]
        lander=next(marker for marker in markers if marker['asset']=='lunar_lander')
        bounds=json.loads((ROOT/'models/environments/lunar_lander/lunar_lander_rig.json').read_text(encoding='utf-8'))['bounds_m']
        x,z=np.meshgrid(np.arange(-40,41),np.arange(-40,41))
        height,_=field('faceoff',x,z,foundations(markers))
        yaw=lander['rotation_blender'][2];c=np.cos(yaw);s=np.sin(yaw)
        for lx in np.linspace(bounds['lo'][0],bounds['hi'][0],9):
            for ly in np.linspace(bounds['lo'][1],bounds['hi'][1],9):
                wx=lander['position_blender'][0]+c*lx-s*ly
                wz=-lander['position_blender'][1]-s*lx-c*ly
                for gx in {int(np.floor(wx)),int(np.ceil(wx))}:
                    for gz in {int(np.floor(wz)),int(np.ceil(wz))}:
                        self.assertAlmostEqual(float(height[gz+40,gx+40]),0.0,places=6,
                            msg='Every triangle beneath the deployed feet and ladder remains level')

    def test_native_foundations_keep_a_level_seating_plane(self):
        folder=ROOT/'models/maps/faceoff'
        spec=importlib.util.spec_from_file_location('terrain_layout',folder/'layout.py')
        layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
        seats=foundations(layout.data()[0])
        for seat in seats:
            x=np.array([[seat['x']]]);z=np.array([[seat['z']]])
            height,_=field('faceoff',x,z,seats)
            self.assertEqual(float(height[0,0]),0.0)

    def test_play_area_grades_are_finite_and_walkable(self):
        metadata=json.loads((ROOT/'.local/planetary/faceoff.json').read_text(encoding='utf-8'))
        x,z=np.meshgrid(np.arange(-37,38),np.arange(-37,38))
        height,weights=field('faceoff',x,z,metadata['foundations'])
        self.assertTrue(np.isfinite(height).all())
        self.assertLess(float(np.hypot(*np.gradient(height)).max()),float(np.tan(np.deg2rad(40))))
        catalog=json.loads((ROOT.parent/'game/data/maps/catalog.json').read_text(encoding='utf-8'))
        scan=next(item for item in catalog['maps'] if item['id']=='faceoff')['navigation']['terrain_scan']
        self.assertGreater(float(height.min()),scan[0])
        self.assertLess(float(height.max()),scan[1])
        self.assertLess(float(height.min()),-.5)
        self.assertGreater(float(height.max()),1.0)
        self.assertTrue(np.allclose(weights.sum(axis=-1),1.0))

    def test_skyfall_ground_retains_clearance_below_platforms(self):
        x,z=np.meshgrid(np.arange(-38,39),np.arange(-38,39))
        height,_=field('skyfall',x,z)
        self.assertLess(float(height.max()),15.0)
        self.assertGreater(float(height.min()),-20.0)

    def test_packed_pbr_keeps_roughness_alpha_and_unit_normals(self):
        folder=ROOT.parent/'game/assets/textures/planetary'
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for layer in manifest['layers']:
            with Image.open(folder/(layer+'_normal_roughness.png')) as image:
                self.assertEqual(image.mode,'RGBA')
                data=np.asarray(image,dtype=np.float32)/255
            normal=data[...,:3]*2-1
            self.assertLess(float(np.abs(np.linalg.norm(normal,axis=-1)-1).max()),.015)
            self.assertGreater(float(data[...,3].min()),.65)
            sidecar=(folder/(layer+'_normal_roughness.png.import')).read_text(encoding='utf-8')
            self.assertIn('compress/normal_map=2',sidecar)

    def test_imagegen_sources_and_runtime_tiles_match_manifest_without_repeat_seams(self):
        folder=ROOT.parent/'game/assets/textures/planetary'
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for name,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),digest)
        for layer in manifest['layers']:
            source=ROOT/'textures/planetary/sources'/f'{layer}_albedo.png'
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),manifest['source_sha256'][layer])
            with Image.open(folder/f'{layer}_albedo_height.png') as image:
                self.assertEqual(image.size,(2048,2048))
                self.assertEqual(image.mode,'RGBA')
                data=np.asarray(image,dtype=np.float32)
            interior=(np.abs(np.diff(data,axis=0)).mean()+np.abs(np.diff(data,axis=1)).mean())/2
            seam=max(np.abs(data[0]-data[-1]).mean(),np.abs(data[:,0]-data[:,-1]).mean())
            self.assertLess(float(seam/interior),1.5,layer+' repeat boundary remains continuous')


if __name__=='__main__':unittest.main()
