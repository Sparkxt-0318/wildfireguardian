# The ember page (Become an ember)

`index.html` turns a visitor's phone into a glowing ember. The visitor opens it, holds the screen toward the booth camera and moves it; the booth tracks every phone like an ember and shows its trail, ID and speed.

It is one self-contained file: the styles, the script, the icon and a tiny keep-awake video are all inside it. It makes no network request, stores nothing, asks for no permission and loads no fonts, so it works from any static host, at any path, and when opened straight from disk.

## What the page does

- A black screen with a soft orange ember in the middle that flickers slightly. It is the same size in portrait and landscape.
- A short instruction in Korean and English for the first 3 s: "휴대폰 화면을 카메라 쪽으로 들고 움직여 보세요", "Hold your screen toward the camera and move it" and "화면 밝기를 최대로 · Turn brightness up". It then fades out and no text comes back.
- A tap anywhere hides the instruction at once and asks for full screen where the browser allows it (Android browsers; iPhone Safari has no full screen for pages, and its bars stay black).
- It keeps the screen awake where the browser allows it (see below).
- No scrolling, zoom, pull-to-refresh, text selection or long-press menu.

## Publish it on GitHub Pages

GitHub Pages publishes a repository's root or its `docs/` folder, not `booth/ember/`. So the page goes into a small public repository of its own; the main repository does not change.

In the browser:

1. On github.com, make a new repository named `ember`, set to Public.
2. Choose "uploading an existing file", drag in `booth/ember/index.html` and commit.
3. In the repository: Settings > Pages > Build and deployment > Source "Deploy from a branch", branch `main`, folder `/ (root)`, Save.
4. After a minute or two the page is at `https://YOUR-NAME.github.io/ember/`.

Or in Terminal on the Mac (with `gh` signed in):

```
mkdir -p ~/ember-page
cp ~/wfglink-run/wfglink/booth/ember/index.html ~/ember-page/
cd ~/ember-page
git init -b main
git add index.html
git commit -m "Ember page"
gh repo create ember --public --source . --push
gh api -X POST "repos/{owner}/ember/pages" -f "source[branch]=main" -f "source[path]=/"
```

To update it later, copy the new `index.html` into `~/ember-page`, then `git commit -am "Update ember page"` and `git push`.

Any other static host works the same way: upload `index.html` anywhere, under any folder name.

## Where the URL goes

The page's address goes into the config key `booth.ember_page_url`. On the booth Mac, add it to `configs/booth_local.yaml` (make the file if it is not there):

```
booth:
  ember_page_url: https://YOUR-NAME.github.io/ember/
```

The booth will read it to show a QR code that visitors scan (coming later). Send the address to Claude as well, so it can go into `configs/default.yaml` for every checkout.

## How to test it

1. Without a browser, from `wfglink/`: `python -m pytest -q tests/test_ember_page.py`. It checks that the page has no network address in it, the overlay text in both languages and its 3 s fade, the wake lock code and its video fallback (the embedded video is decoded), and the ember's look against the shared booth contract.
2. On the Mac: double-click `booth/ember/index.html`. In Chrome, View > Developer > Developer Tools, then the device toolbar, shows phone sizes in portrait and landscape.
3. On a phone, from the published address:
   - the instruction shows over a dim ember and fades out after 3 s; the ember then glows at full brightness and flickers slightly;
   - a tap hides the instruction at once; Android goes full screen;
   - left alone for longer than the phone's auto-lock time, the screen stays on;
   - turned sideways, the ember stays centred and the same size;
   - turn the brightness up by hand: a web page cannot do it.
4. On a phone before publishing, over the booth Wi-Fi: on the Mac run `cd ~/wfglink-run/wfglink/booth/ember` and `python3 -m http.server 8000`, then open `http://MAC-ADDRESS:8000/` on the phone (System Settings > Wi-Fi > Details shows the Mac's address). Plain `http` on a local network is not a secure context, so the browser hides the Wake Lock API there and the page keeps the screen awake with its video instead. The published `https` address uses the Wake Lock API.

## Keeping the screen awake

- The Screen Wake Lock API (Chrome and Android browsers, Safari 16.4 and later, Firefox 126 and later) is asked for when the page opens and on every tap. The browser drops the lock whenever the page is hidden, so the page asks again each time it is shown.
- Where the API is missing or refuses, the page plays a 1 s silent black video in a loop, 1 px in a corner (the NoSleep technique). Where autoplay is blocked (iPhone Low Power Mode, for example) the video starts on the first tap.

## The look is shared with the booth

The booth's synthetic phones (`src/wfglink/ember/`) copy this page, so the tracker is tuned on what visitors will really show. The shared look:

- black background;
- a centred disc of radius 0.36 times the shorter side of the screen, with a radial gradient: 0% #FFF1D6, 18% #FFC266, 45% #FF8A1F, 70% rgba(255,90,0,0.35), 100% transparent;
- a slight flicker: overall brightness between 0.85 and 1.0 and scale between 0.97 and 1.0, changing smoothly at about 3 Hz. Each phone starts its flicker at a random point, so phones never flicker in step.

When the phone asks for reduced motion, the flicker is gentler (brightness between 0.95 and 1.0, no change in size). If the look changes here, the synthetic phones must change with it.

## Remaking the keep-awake video

The two videos (MP4 with H.264 and AAC for Safari, WebM with VP8 and Opus for the rest) were made with FFmpeg and pasted into the `MP4` and `WEBM` constants as base64:

```
ffmpeg -f lavfi -i "color=c=black:s=64x64:r=10:d=1" -f lavfi -i "anullsrc=r=22050:cl=mono" -t 1 \
  -map 0:v -map 1:a -c:v libx264 -profile:v baseline -level 3.0 -pix_fmt yuv420p -g 10 -crf 51 \
  -bsf:v filter_units=remove_types=6 -c:a aac -b:a 16k -ac 1 -shortest -map_metadata -1 \
  -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -movflags +faststart awake.mp4
ffmpeg -f lavfi -i "color=c=black:s=64x64:r=10:d=1" -f lavfi -i "anullsrc=r=48000:cl=mono" -t 1 \
  -map 0:v -map 1:a -c:v libvpx -b:v 20k -g 10 -c:a libopus -b:a 8k -ac 1 -shortest -map_metadata -1 \
  -fflags +bitexact -flags:v +bitexact -flags:a +bitexact awake.webm
base64 -i awake.mp4 | tr -d '\n'
```
