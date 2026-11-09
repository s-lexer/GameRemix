"""Mutation tests for the independent remaster export verifier."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

spec = importlib.util.spec_from_file_location('verify_remaster_manifest', Path(__file__).with_name('verify_remaster_manifest.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        assets = []
        for kind in ('tile', 'object', 'hero'):
            p = self.root / (kind + '.png')
            Image.new('RGBA', (2, 3), (12, 34, 56, 255)).save(p)
            assets.append(dict(id=kind, kind=kind, file=p.name, sha256=module.digest(p),
                               width=2, height=3, anchor_x=0, anchor_y=0))
        self.data = dict(schema_version=1, game_id='fixture', sources=[], assets=assets,
            world=dict(columns=1, rows=1, tile_size=64,
                       tiles=[dict(asset_id='tile', x=0, y=0, layer=0)],
                       objects=[dict(asset_id='object', x=0, y=0, z=0, placement_status='synthetic_gallery')]),
            hero=dict(direction_count=1, frames_per_direction=1, fps=12, draw_order='A',
                      parts=[dict(asset_id='hero', layer='A', direction=0, frame=0, x=0, y=0)]),
            limitations=['Synthetic fixture, no game assets.'])

    def verify(self, data=None, game_root=None):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.data if data is None else data), encoding='utf-8')
        return module.verify(manifest, game_root)

    def test_valid_and_pixel_corruption(self):
        self.assertEqual(self.verify()['assets'], 3)
        Image.new('RGBA', (2, 3), (56, 34, 12, 255)).save(self.root / 'tile.png')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.verify()

    def test_completeness_and_references(self):
        for mutation in ('missing_layer', 'duplicate_part', 'wrong_kind', 'duplicate_tile', 'duplicate_id'):
            data = copy.deepcopy(self.data)
            if mutation == 'missing_layer': data['hero']['draw_order'] = 'AB'
            if mutation == 'duplicate_part': data['hero']['parts'] *= 2
            if mutation == 'wrong_kind': data['world']['tiles'][0]['asset_id'] = 'hero'
            if mutation == 'duplicate_tile': data['world']['tiles'] *= 2
            if mutation == 'duplicate_id': data['assets'].append(data['assets'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.verify(data)

    def test_dimensions_and_path_escape(self):
        for field, value in [('width', 99), ('file', '../tile.png'), ('file', str(self.root / 'tile.png'))]:
            data = copy.deepcopy(self.data)
            data['assets'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.verify(data)

    def test_source_hash_checks(self):
        source = self.root / 'source.bin'
        source.write_bytes(b'original')
        self.data['sources'] = [dict(path=source.name, sha256=module.digest(source))]
        self.assertTrue(self.verify(game_root=self.root)['source_hashes_verified'])
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.verify(game_root=self.root)


if __name__ == '__main__':
    unittest.main()
