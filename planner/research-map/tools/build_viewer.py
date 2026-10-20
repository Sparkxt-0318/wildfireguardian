#!/usr/bin/env python3
"""Assemble the 3D layer map page from src/ (style.css, body.html, loader.js, core.js, ui.js).

usage: python tools/build_viewer.py            -> site/index.html (+ site/logger.html), offline: site/vendor scripts, system fonts, works from file://
       python tools/build_viewer.py --cdn OUT  -> a page fragment that loads three.js from cdnjs/jsdelivr and Noto Sans KR
                                                  from Google Fonts (for hosting where the page gets its own document shell)
The region data is loaded at run time from regions/<id>.js next to the page (tools/build_regions.py).
"""
import argparse, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
LIBS = ['three.min.js', 'OrbitControls.js', 'CopyShader.js', 'LuminosityHighPassShader.js', 'GammaCorrectionShader.js',
        'EffectComposer.js', 'RenderPass.js', 'ShaderPass.js', 'UnrealBloomPass.js']
CDN = {'three.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
       'OrbitControls.js': 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js'}
CDN.update({n: f'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/{n}' for n in LIBS[2:5]})
CDN.update({n: f'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/{n}' for n in LIBS[5:]})
# MapLibre (navigation view's real 3D map) loads only when that view opens: from site/vendor, or the same release on the CDN
MAPLIBRE = {False: 'vendor/maplibre-gl.', True: 'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.'}
META = ['<title>산불 레이어 지도</title>',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        '<meta name="claude:viewport-fit-sides" content="cover">',
        '<meta name="description" content="한국 산불 5개 연구 지역의 기록·모델 출력·경로 점검 결과를 한 지도 위에서 시간에 따라 보는 3D/2D 뷰어">']
FONTS = ['<link rel="preconnect" href="https://fonts.googleapis.com">', '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap">']


def inline_tex(text: str, site: Path) -> str:
    """A tex.js with its image paths turned into data URLs. Pages opened from file:// cannot read the pixels of image
    files (Chrome treats each file as its own origin), so offline builds carry the terrain images inside the script."""
    import base64
    for path in re.findall(r'"(regions/[^"]+\.(?:jpg|png|webp))"', text):
        mime = {'png': 'image/png', 'webp': 'image/webp'}.get(path.rsplit('.', 1)[1], 'image/jpeg')
        text = text.replace(f'"{path}"', '"data:' + mime + ';base64,' + base64.b64encode((site / path).read_bytes()).decode() + '"')
    return text


def build_offline(out: Path):
    """A folder to unzip and open from disk (index.html): the same files as the site, loaded one region at a time, with
    each region's terrain images inside its tex.js (see inline_tex)."""
    import shutil
    site = ROOT / 'site'
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(site, out, ignore=shutil.ignore_patterns('vercel.json'))
    for t in sorted((out / 'regions').glob('*.tex.js')):
        t.write_text(inline_tex(t.read_text(), site)); shutil.rmtree(out / 'regions' / t.name[:-len('.tex.js')])
    (out / 'README.txt').write_text(OFFLINE_NOTE)     # ASCII name: zip tools on other systems garble non-ASCII file names
    for f in (ROOT / 'tools' / 'offline').iterdir():     # local server start scripts (localhost:8840 is registered for road view)
        shutil.copy2(f, out / f.name)


OFFLINE_NOTE = '''WildfireGuardian — 오프라인 판 (offline copy)

[가장 좋은 방법] 이 폴더에서 시작 파일을 더블클릭하세요. 이 컴퓨터 안에서만 작은 서버가 켜지고 브라우저가 열립니다.
  Windows: start-windows.bat      Mac: start-mac.command  (처음 한 번: 오른쪽 클릭 → 열기)
  주소는 http://localhost:8840 입니다. 창을 닫으면 끝납니다.
  - 인터넷이 없어도: 5개 산불 지도, 3D 지형, 타임라인, 2D 길 안내, 경로 점검이 모두 됩니다.
  - 휴대폰 핫스폿을 켜면: 로드뷰(카카오)와 3D 위성도 켜집니다 (이 주소는 카카오에 등록되어 있습니다).
[예비] 시작 파일이 막히면 index.html 을 Chrome/Edge 로 바로 여세요 (인터넷 없이 되는 부분은 같고, 로드뷰는 안 됩니다).

[Best] Double-click the start file in this folder: a small server runs on this computer only and the browser opens.
  Windows: start-windows.bat      Mac: start-mac.command  (first time: right-click → Open)
  Address: http://localhost:8840 . Close the window to stop.
  - With no internet: all five fire maps, 3D terrain, the timeline, 2D navigation and route checks work.
  - With a phone hotspot: road view (Kakao) and 3D satellite work too (this address is registered with Kakao).
[Fallback] If the start file is blocked, open index.html in Chrome or Edge directly (same offline features; no road view).
'''


def build_single() -> str:
    """One self-contained HTML file. Libraries are inline; each region's data, terrain and hourly file sit in inert
    <script type="text/plain"> blocks that the loader runs only for the region being viewed."""
    import base64
    page = build(False, single=True)     # one file has no vendor folder beside it: MapLibre from the CDN
    site = ROOT / 'site'
    inline = lambda p: '<script>\n' + p.read_text().replace('</script', '<\\/script') + '\n</script>'
    block = lambda name, text: f'<script type="text/plain" id="wfg:{name}">' + text.replace('</script', '<\\/script') + '</script>'
    for n in LIBS:
        page = page.replace(f'<script src="vendor/{n}"></script>', inline(site / 'vendor' / n))
    blocks = []
    for p in sorted((site / 'regions').glob('*.js')):
        if p.name == 'index.js': continue
        text = p.read_text()
        blocks.append(block(p.name, inline_tex(text, site) if p.name.endswith('.tex.js') else text))
    figs = {p.stem: 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode() for p in sorted((site / 'logger').glob('fig*.png'))}
    page = page.replace('<script src="kakao-keys.js"></script>', inline(site / 'kakao-keys.js'))
    page = page.replace('<script src="regions/index.js"></script>', inline(site / 'regions' / 'index.js') + ''.join(blocks)
                        + '<script>window.WFG_FIG=' + __import__('json').dumps(figs) + ';</script>')
    return page


def build(cdn: bool, single: bool = False) -> str:
    read = lambda n: (SRC / n).read_text()
    js = read('loader.js').replace('__MAIN__', read('core.js') + '\n' + read('ui.js') + '\n' + read('nav.js').replace('__MAPLIBRE__', MAPLIBRE[cdn or single]))
    libs = '\n'.join(f'<script src="{CDN[n] if cdn else "vendor/" + n}"></script>' for n in LIBS)
    style = '<style>\n' + read('style.css') + '</style>'
    tail = libs + '\n<script src="regions/index.js"></script>\n<script src="kakao-keys.js"></script>\n<script>\n' + js + '</script>\n'
    if cdn:
        return '\n'.join(META + FONTS + [style]) + '\n' + read('body.html') + tail
    return '\n'.join(['<!doctype html>', '<html lang="ko">', '<head>', '<meta charset="utf-8">'] + META + [style, '</head>', '<body>']) + '\n' + read('body.html') + tail + '</body>\n</html>\n'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cdn', metavar='OUT', help='write the CDN fragment to OUT instead of the offline site/index.html')
    ap.add_argument('--single', metavar='OUT', help='also write one self-contained HTML file (everything inline) to OUT')
    ap.add_argument('--offline', metavar='DIR', help='also write a folder to open from disk (fastest offline) to DIR')
    a = ap.parse_args()
    out = Path(a.cdn) if a.cdn else ROOT / 'site' / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(bool(a.cdn)))
    if not a.cdn:   # the route logger page (data from tools/build_logger.py) is a plain copy
        (ROOT / 'site' / 'logger.html').write_text((SRC / 'logger.html').read_text())
    if a.offline:
        build_offline(Path(a.offline)); print(f'wrote {a.offline}/ (offline folder, open index.html)')
    if a.single:
        Path(a.single).write_text(build_single())
        print(f'wrote {a.single} ({Path(a.single).stat().st_size / 1e6:.1f} MB, single file)')
    print(f'wrote {out} ({out.stat().st_size / 1e3:.0f} kB, {"CDN" if a.cdn else "offline"})')
