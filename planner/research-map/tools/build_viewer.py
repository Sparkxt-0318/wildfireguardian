#!/usr/bin/env python3
"""Assemble the 3D layer map page from src/ (style.css, body.html, loader.js, core.js, ui.js).

usage: python tools/build_viewer.py            -> site/index.html, offline: site/vendor scripts, system fonts, works from file://
       python tools/build_viewer.py --cdn OUT  -> a page fragment that loads three.js from cdnjs/jsdelivr and Noto Sans KR
                                                  from Google Fonts (for hosting where the page gets its own document shell)
The region data is loaded at run time from regions/<id>.js next to the page (tools/build_regions.py).
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
LIBS = ['three.min.js', 'OrbitControls.js', 'CopyShader.js', 'LuminosityHighPassShader.js', 'GammaCorrectionShader.js',
        'EffectComposer.js', 'RenderPass.js', 'ShaderPass.js', 'UnrealBloomPass.js']
CDN = {'three.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
       'OrbitControls.js': 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js'}
CDN.update({n: f'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/{n}' for n in LIBS[2:5]})
CDN.update({n: f'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/{n}' for n in LIBS[5:]})
META = ['<title>산불 레이어 지도</title>',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        '<meta name="claude:viewport-fit-sides" content="cover">',
        '<meta name="description" content="한국 산불 5개 연구 지역의 기록·모델 출력·경로 점검 결과를 한 지도 위에서 시간에 따라 보는 3D/2D 뷰어">']
FONTS = ['<link rel="preconnect" href="https://fonts.googleapis.com">', '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap">']


def build_single() -> str:
    """One self-contained HTML file: libraries, every region and the logger figures inline (open it on its own)."""
    import base64
    page = build(False)
    site = ROOT / 'site'
    inline = lambda p: '<script>\n' + p.read_text().replace('</script', '<\\/script') + '\n</script>'
    for n in LIBS:
        page = page.replace(f'<script src="vendor/{n}"></script>', inline(site / 'vendor' / n))
    figs = {p.stem: 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode() for p in sorted((site / 'logger').glob('fig*.png'))}
    data = ''.join(inline(p) for p in sorted((site / 'regions').glob('*.js')) if p.name != 'index.js')
    page = page.replace('<script src="regions/index.js"></script>', inline(site / 'regions' / 'index.js') + data
                        + '<script>window.WFG_FIG=' + __import__('json').dumps(figs) + ';</script>')
    return page


def build(cdn: bool) -> str:
    read = lambda n: (SRC / n).read_text()
    js = read('loader.js').replace('__MAIN__', read('core.js') + '\n' + read('ui.js'))
    libs = '\n'.join(f'<script src="{CDN[n] if cdn else "vendor/" + n}"></script>' for n in LIBS)
    style = '<style>\n' + read('style.css') + '</style>'
    tail = libs + '\n<script src="regions/index.js"></script>\n<script>\n' + js + '</script>\n'
    if cdn:
        return '\n'.join(META + FONTS + [style]) + '\n' + read('body.html') + tail
    return '\n'.join(['<!doctype html>', '<html lang="ko">', '<head>', '<meta charset="utf-8">'] + META + [style, '</head>', '<body>']) + '\n' + read('body.html') + tail + '</body>\n</html>\n'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cdn', metavar='OUT', help='write the CDN fragment to OUT instead of the offline site/index.html')
    ap.add_argument('--single', metavar='OUT', help='also write one self-contained HTML file (everything inline) to OUT')
    a = ap.parse_args()
    out = Path(a.cdn) if a.cdn else ROOT / 'site' / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(bool(a.cdn)))
    if a.single:
        Path(a.single).write_text(build_single())
        print(f'wrote {a.single} ({Path(a.single).stat().st_size / 1e6:.1f} MB, single file)')
    print(f'wrote {out} ({out.stat().st_size / 1e3:.0f} kB, {"CDN" if a.cdn else "offline"})')
