#!/usr/bin/env python3
"""Route logger page data: site/logger/ from the Route Logger website export (Case v2, firmware 0.3.0).

usage: python tools/build_logger.py <WildfireGuardian_Route_Logger export dir> <stand-in glb>

The stand-in GLB is route_logger_assembled_web.glb passed through tools/logger_standin.mjs (FireBeetle vendor model
replaced by plain boxes). Writes site/logger/model.js (the GLB, base64), site/logger/data.js (part list, exploded and per-step
offsets, manual text as exported) and web-size copies of the manual pictures in site/logger/img/. Nothing is added
to the exported text; the page labels renders, simulated screens and estimates."""
import base64, json, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'site' / 'logger'
WIDTH = 1280           # renders and diagrams on the page; the export has 1600 px+ originals


def web_image(src: Path, dst_dir: Path) -> str:
    im = Image.open(src)
    pixel_art = src.parent.name == '3_screen_pictures'      # 240 px screen art scaled up pixel for pixel
    w = 720 if pixel_art else WIDTH
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.NEAREST if pixel_art else Image.LANCZOS)
    has_alpha = im.mode in ('RGBA', 'LA') and im.getextrema()[-1][0] < 255
    if pixel_art or src.parent.name == '4_wiring_diagrams':
        name = src.stem + '.png'; im.save(dst_dir / name, optimize=True)
    elif has_alpha:              # renders on a transparent background
        name = src.stem + '.webp'; im.save(dst_dir / name, quality=84, method=6)
    else:
        name = src.stem + '.jpg'; im.convert('RGB').save(dst_dir / name, quality=84, optimize=True, progressive=True)
    return 'logger/img/' + name


def main(export: Path, glb: Path):
    (OUT / 'img').mkdir(parents=True, exist_ok=True)
    # base64 in a script, not a .glb fetch: pages opened from file:// cannot fetch files
    (OUT / 'model.js').write_text('window.RL_GLB="' + base64.b64encode(glb.read_bytes()).decode() + '";\n')
    (OUT / 'route_logger.glb').unlink(missing_ok=True)
    manual = json.loads((export / '04_manual_text/manual_en.json').read_text())
    parts = json.loads((export / '03_parts_list/parts.json').read_text())
    pos = json.loads((export / '01_3D_models/exploded_positions.json').read_text())
    missing, done = [], {}
    for s in manual['slides']:
        for im in s['images']:
            src = (export / '04_manual_text' / im['file']).resolve()
            if src not in done:
                done[src] = web_image(src, OUT / 'img') if src.is_file() else None
                if not src.is_file(): missing.append(im['file'])
            im['file'], im['kind'] = done[src], src.parent.name     # kind: export folder, e.g. 2_part_pictures
    for p in parts['parts']:
        if p['node'] == 'firebeetle2_esp32e':        # the web model carries the stand-in, not the vendor mesh
            p['model_source'] = 'Plain stand-in of the board outline, RF module can and USB-C socket (tools/logger_standin.mjs); the vendor model is not published'
            p['children'] = ['firebeetle2_esp32e__standin_pcb', 'firebeetle2_esp32e__standin_can', 'firebeetle2_esp32e__standin_usb']
    cover = export / '05_images/5_cover_and_beauty_renders/cover.png'
    extra = {'cover': web_image(cover, OUT / 'img'),
             'exploded': web_image(export / '05_images/5_cover_and_beauty_renders/cad_design_renders/cad_03_exploded.png', OUT / 'img')}
    # exploded offset None: hidden in the exploded render (the wires)
    data = {'manual': manual, 'parts': parts['parts'], 'exploded': {k: v.get('offset_gltf_mm') for k, v in pos['exploded_view'].items()},
            'steps': [{k: r[k] for k in ('step', 'nodes', 'offset_gltf_mm', 'note')} for r in pos['manual_step_render_positions']],
            'img': extra}
    (OUT / 'data.js').write_text('window.RL=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
    used = set(done.values()) | set(extra.values())
    for f in (OUT / 'img').iterdir():
        if 'logger/img/' + f.name not in used: f.unlink()
    print(f'{len(used)} images, {sum(f.stat().st_size for f in (OUT / "img").iterdir()) / 1e6:.1f} MB; missing {len(missing)}')
    for m in missing: print('  missing', m)


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
