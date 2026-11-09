"""Independent verifier for exported remaster manifest v1 (no game writes)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def contained_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('File reference must be a nonempty POSIX relative path')
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts or ':' in relative:
        raise ValueError('Invalid relative file reference: ' + relative)
    result = (root / part).resolve()
    if not result.is_relative_to(root.resolve()) or not result.is_file():
        raise ValueError('Missing file or file outside root: ' + relative)
    return result


def integer(value, name: str, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError('Invalid integer: ' + name)
    return value


def verify(manifest: Path, game_root: Path | None = None) -> dict:
    from PIL import Image

    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('game_id'), str):
        raise ValueError('Expected manifest schema_version 1 and game_id')
    if not data['game_id']:
        raise ValueError('Missing game ID')
    assets = {}
    files = set()
    kinds = {}
    for item in data['assets']:
        ident = item['id']
        if not isinstance(ident, str) or not ident or ident in assets:
            raise ValueError('Invalid or duplicate asset ID')
        image_path = contained_file(manifest.parent, item['file'])
        if image_path in files:
            raise ValueError('Multiple asset IDs point to the same file')
        files.add(image_path)
        if digest(image_path) != item['sha256']:
            raise ValueError('Asset hash mismatch: ' + ident)
        width = integer(item['width'], ident + '.width', 1)
        height = integer(item['height'], ident + '.height', 1)
        with Image.open(image_path) as image:
            if image.format != 'PNG' or image.size != (width, height) or image.mode != 'RGBA':
                raise ValueError('Expected matching RGBA PNG: ' + ident)
            image.verify()
        integer(item['anchor_x'], ident + '.anchor_x')
        integer(item['anchor_y'], ident + '.anchor_y')
        if item['kind'] not in ('tile', 'object', 'hero'):
            raise ValueError('Unknown asset kind: ' + ident)
        assets[ident] = item
        kinds[item['kind']] = kinds.get(item['kind'], 0) + 1

    def reference(ident, kind):
        if ident not in assets or assets[ident]['kind'] != kind:
            raise ValueError('Missing/wrong asset reference: ' + str(ident))

    world = data['world']
    for field in ('columns', 'rows', 'tile_size'):
        integer(world[field], 'world.' + field, 1)
    cells = set()
    for tile in world['tiles']:
        reference(tile['asset_id'], 'tile')
        x = integer(tile['x'], 'tile.x', 0)
        y = integer(tile['y'], 'tile.y', 0)
        layer = integer(tile['layer'], 'tile.layer', 0)
        if x >= world['columns'] * world['tile_size'] or y >= world['rows'] * world['tile_size']:
            raise ValueError('Tile outside exported chunk')
        key = (x, y, layer)
        if key in cells:
            raise ValueError('Duplicate tile placement')
        cells.add(key)
    for obj in world['objects']:
        reference(obj['asset_id'], 'object')
        for field in ('x', 'y', 'z'):
            integer(obj[field], 'object.' + field)
        if not isinstance(obj.get('placement_status'), str) or not obj['placement_status']:
            raise ValueError('Object placement provenance required')

    hero = data['hero']
    directions = integer(hero['direction_count'], 'hero.direction_count', 1)
    frames = integer(hero['frames_per_direction'], 'hero.frames_per_direction', 1)
    if not isinstance(hero['fps'], (int, float)) or not 0 < hero['fps'] <= 240:
        raise ValueError('Invalid animation rate')
    order = hero['draw_order']
    if not isinstance(order, str) or not order or len(set(order)) != len(order):
        raise ValueError('Invalid hero layer order')
    parts = set()
    for part in hero['parts']:
        reference(part['asset_id'], 'hero')
        direction = integer(part['direction'], 'part.direction', 0)
        frame = integer(part['frame'], 'part.frame', 0)
        layer = part['layer']
        if layer not in order or len(layer) != 1 or direction >= directions or frame >= frames:
            raise ValueError('Hero part outside clip bounds')
        key = (layer, direction, frame)
        if key in parts:
            raise ValueError('Duplicate hero part')
        parts.add(key)
        integer(part['x'], 'part.x')
        integer(part['y'], 'part.y')
    if len(parts) != len(order) * directions * frames:
        raise ValueError('Hero clip has missing layers/frames/directions')
    sources = set()
    for source in data['sources']:
        relative = source['path']
        if relative in sources:
            raise ValueError('Duplicate source')
        sources.add(relative)
        sha = source['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid source hash')
        if game_root is not None and digest(contained_file(game_root, relative)) != sha:
            raise ValueError('Source hash mismatch: ' + relative)
    if not isinstance(data.get('limitations'), list) or not data['limitations']:
        raise ValueError('Export verification limits must be explicit')
    return {'status': 'PASS', 'schema_version': 1, 'game_id': data['game_id'],
            'assets': len(assets), 'kinds': kinds, 'tiles': len(cells),
            'objects': len(world['objects']), 'hero_parts': len(parts),
            'sources': len(sources), 'source_hashes_verified': game_root is not None,
            'limitations': data['limitations']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--game-root', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.manifest, args.game_root)
    except (KeyError, TypeError, ValueError, OSError) as error:
        result = {'status': 'FAIL', 'error': str(error)}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
