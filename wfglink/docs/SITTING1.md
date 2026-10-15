# Sitting 1 checklist

For tonight with the MacBook's built-in camera and an iPhone, use
[`SITTING1_TONIGHT.md`](SITTING1_TONIGHT.md). Its one script produces a combined JSON
and a pasteable report, uses the phone page over local Wi-Fi, and keeps tonight's
camera settings and calibration separate from existing booth settings. The longer
recording session below remains available for later validation.

As soon as your parts arrive. About 90 minutes. Seven parts, in order: setup, camera and permission, the page, the standing spot and the A4 calibration, recordings, validate, send files. You can stop between parts; nothing is lost.

Every command runs in Terminal. In each new Terminal window, first go to the folder and turn on the environment:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
```

The prompt then starts with `(.venv)`.

## Before the day

- Install Python 3.12 from https://www.python.org/downloads/macos/ : the macOS 64-bit universal2 installer of Python 3.12.10, the last 3.12 release with a macOS installer (later 3.12 releases are source only). The setup script uses this Python. You do not need to run its "Install Certificates" step: setup installs the certificates the clip download uses.
- Internet for the setup (the first install downloads a few hundred MB).
- A GitHub account, for putting the ember page on GitHub Pages (Part 3).
- Decide which camera the booth uses: the MacBook's own camera (the default), or a USB webcam. An iPhone is never used as the camera.
- A room with about 4 m of free floor in front of the camera: the camera, 2.0 m to the standing spot, and room to move behind it. Normal indoor light, as at the booth.

## Parts on the table

- The MacBook and its charger. The external monitor is optional today.
- The USB webcam, if you use one.
- Your phone, charged. A second phone helps but is not needed.
- A printer with A4 paper, a piece of stiff card, and glue or tape, to keep the printed target flat.
- Masking tape for the floor mark and for the two marks of the 1 m path, a tape measure, and a ruler.
- For the 1 m path: a table (or a bench or a long box) at least 1.2 m long, which you can put at the standing spot.

## Part 1: Setup (about 15 minutes)

In Terminal:

```
cd ~/wildfireguardian            # your main checkout of the repository (only used to fetch)
git fetch origin claude/practical-rubin-5vu12u
git worktree add --detach ~/wfglink-run origin/claude/practical-rubin-5vu12u
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh
source .venv/bin/activate
python -m wfglink doctor
python -m wfglink live --synthetic
```

What each step does:

1. The worktree is a separate copy of wfglink at `~/wfglink-run`, so your other sessions' checkout is never switched. Use your own path in the first line if your clone is somewhere else.
2. `./scripts/setup_mac.sh` creates `.venv` with Python 3.12 from python.org, installs everything wfglink needs and creates `data/raw`. It also downloads the two clips the booth plays (about 50 MB) and, near the end, macOS asks whether Terminal may use the camera: click Allow (the booth's ember mode needs it). It ends by running the doctor. The first run takes 5 to 10 minutes. Running it again is safe: it only adds what is missing.
3. `source .venv/bin/activate` turns the environment on for this Terminal window.
4. `python -m wfglink doctor` prints one line per check: python, packages, fonts and screens (the four of the build manual), then video, camera, data and clips. Every line must end in OK. A line that ends in FAIL carries its fix after "fix:" on the same line; do that and run `doctor` again. The screens line lists the screens the Mac sees; the camera line says which camera the booth picks and whether Terminal may use it; the clips line says whether the booth's two clips are there.
5. `python -m wfglink live --synthetic` opens the full booth screen on generated video, fullscreen on the external monitor if one is connected, otherwise on the MacBook. Within a few seconds you should see orange ember tracks on the left, four cards of green numbers on the right, and the tag "합성 영상 · 실측 아님" ("Synthetic video · not measured" in English). Press L (language), T (tracks), F (field), G (gate), Space (pause, then Space again), I (limits card, then I again) and A (the raw video, then A again for the analysed view) once each. Press Esc, then Esc again, to quit.

The booth's two clips came with setup. The other approved clips (about 1 GB, for file-mode work, not for the booth) are optional: `python scripts/fetch_clips.py` in a second Terminal window downloads them one at a time and may pause for 10 minutes when Wikimedia limits the rate. Skip it unless Claude asks for it.

## Part 2: Camera and permission (about 10 minutes)

1. If you use the USB webcam, plug it into the MacBook now (directly, not through a long hub chain if you can).
2. Check the camera permission, list the cameras and open the picked one for 5 seconds:

```
python -m wfglink cameras --request
python -m wfglink cameras --open 5
```

3. If you clicked Allow during setup, no dialog shows now; otherwise macOS shows one saying that Terminal would like to access the camera: click Allow. The first command prints the answer (it should be `authorized`), every camera with its kind and whether it is usable, and the camera the config picks. The second opens that camera and prints how it was opened (the backend, the picture size and the frames per second); it should end without an error.
   - Continuity Camera (an iPhone) and Desk View are listed as not usable. That is intended.
   - The config's choice is auto: the USB webcam when one is connected, else the MacBook's camera. If it picks the wrong one, see "The wrong camera is picked" at the end.
4. Look at the camera picture and switch off the video effects:

```
python -m wfglink live --ember
```

   The booth opens in ember mode: the camera picture, mirrored, with the header "당신이 불티입니다 / You are an ember" in both languages (Korean on top, large; L puts English on top). Move the pointer to the top of the screen so the menu bar shows, click the green camera icon (the Video menu), and turn off Center Stage, Portrait, Studio Light, Background and Reactions, every one that is listed. They crop, blur or draw on the picture, and Center Stage changes the scale of the speeds. Press Esc, then Esc again, to quit.

## Part 3: The page (about 10 minutes)

The ember page is one file, `booth/ember/index.html`, with no external requests, so any static web host serves it. With GitHub Pages:

1. On github.com, create a new public repository, for example `ember`.
2. The new, empty repository shows its Quick setup page: click the "uploading an existing file" link there, and drop in `index.html` from the folder that `open booth/ember` shows in Finder. Commit.
3. Settings > Pages: under "Build and deployment", Source "Deploy from a branch", Branch `main` and folder `/ (root)`; Save.
4. After a minute or two the page shows its address there, for example `https://YOUR-NAME.github.io/ember/`. Open it on your phone.
5. Check on the phone: a black screen with a glowing orange ember that flickers slightly, and a short Korean and English instruction that fades out after 3 s. The screen should stay on while the page is open (the browser decides; GitHub Pages serves HTTPS, which this needs).
6. Put the address into the booth's settings and make its QR card. Open the settings file with `open -e configs/booth_local.yaml` (if it does not exist, `touch configs/booth_local.yaml` first), write these two lines (if a `booth:` line is there already, only the second line under it) and save:

```
booth:
  ember_page_url: https://YOUR-NAME.github.io/ember/
```

   Then run `python scripts/make_placards.py --card ember_page`: it writes only the A5 QR card `booth/placards/ember_page_ko.pdf` and `ember_page_en.pdf` for the standing spot. Scan its QR code with your phone to check. Ember mode's screen now shows the same QR code and address bottom right.

If you already published the page, just open it on your phone and check step 5.

## Part 4: The standing spot and the A4 calibration (about 15 minutes)

1. Put the camera where it will stand at the booth: the MacBook on the table, or the webcam on top of the monitor, facing open floor. Keep windows and bright lamps out of its view.
2. Measure 2.0 m straight out from the camera lens along the floor with the tape measure, and put a tape mark there. This is the standing spot: the phone is held over this mark (the visitor stands just behind it, arms out), and the speeds in ember mode are measured at this distance. The target, the phones and the 1 m path must all be over this same mark.
3. Print the target:

```
open booth/ember/calibration_target_A4.pdf
```

   Print it on A4 at 100 percent: in the print dialog choose Scale 100 % (actual size), not "Fit to page". Check the 100 mm line on the sheet with the ruler: it must measure 100 mm. If not, print again at 100 percent. Glue or tape the sheet flat onto the stiff card.
4. Run the calibration:

```
python -m wfglink calibrate
```

   The camera picture shows fullscreen. Stand just behind the mark and hold the target out over it, flat at chest height, facing the camera, with all four corner markers in the picture, and keep still. Once the measurement is stable the command ends by itself, prints the focal length in pixels and the equivalent horizontal field of view, and writes them, with a calibration record, into `configs/booth_local.yaml`. If it is not stable within 90 seconds it writes nothing and says "not stable": run it again. Esc cancels. A warning about the field of view means the distance or the print scale is off: check both.

Use 2.0 m unless the booth space cannot give it. If it must be another distance, put the mark there, run `python -m wfglink calibrate --distance-m D` with that distance in metres, and tell Claude the distance.

## Part 5: Recordings (about 10 minutes)

Both recordings are made at the standing spot with the page open on your phone and the phone's brightness at maximum. The record command shows the camera with a countdown, records for the seconds given and saves the file as `data/raw/<name>.mp4`.

`ember_free`, about a minute of free motion:

```
python -m wfglink record ember_free --seconds 60
```

After the countdown, stand just behind the mark and move the phone over it for the whole minute, with its screen towards the camera: slowly and quickly, left and right, up and down, in curves and circles. Keep any other phone or shiny moving thing out of the picture.

`ember_ruler`, the known motion over a 1 m path. Set it up first:

1. Put the table at the standing spot, its long front edge 2.0 m from the camera lens and square to the camera (both ends of the edge the same distance from the lens).
2. With the tape measure, put two small tape marks on the front edge exactly 100 cm apart, centred in front of the camera. Write 0 on one and 100 on the other.

Then record:

```
python -m wfglink record ember_ruler --seconds 15
```

After the countdown: hold the phone upright, screen to the camera, its bottom edge resting on the table edge and its centre at the 0 mark. Keep still for about 3 seconds. Slide it along the edge to the 100 cm mark in about 1 second, and keep still there until the recording ends. No stopwatch is needed: the move time comes from the video.

If a recording went wrong (the phone left the picture, someone walked through), record it again with the same command plus `--force`, which replaces the earlier file, for example `python -m wfglink record ember_free --seconds 60 --force`. Without `--force` the command refuses to replace a recording. A recording stopped with Esc is not kept, so the same command makes it again.

## Part 6: Validate and try the booth (about 10 minutes)

```
python -m wfglink validate --suite ember
```

It runs the synthetic phone scenes first, then your two recordings, prints a short summary (detection, tracking and the speed error on the 1 m path) and writes `results/validation/ember_report.json`. A missed goal is a result, not a failure. Send the files either way.

Then try ember mode as visitors will see it:

```
python -m wfglink live --ember
```

Stand just behind the mark and hold the phone with the page open over it: your phone gets a glowing trail, an ID and a speed in m/s, measured at 2.0 m. Press M to switch to fire mode (the clips), A twice (raw, then analysed; A works on the fire footage only), M again to come back, then Esc and Esc again to quit.

## Part 7: Send files (about 10 minutes)

Upload these to one new folder in Google Drive, Dropbox or iCloud Drive:

- `results/validation/ember_report.json`;
- `data/raw/ember_free.mp4` and `data/raw/ember_ruler.mp4` (they show you, so share them only through this link);
- `configs/booth_local.yaml` (the calibration record).

`open results/validation`, `open data/raw` and `open configs` show the folders in Finder, so you can drag the files. Share the folder as "anyone with the link can view", then paste into the chat with Claude: the link, the page's address, the lines `validate` printed, the `cameras` lines (both commands) from Part 2 and the `doctor` lines from Part 1.

## If something goes wrong

| Problem | What to do |
|---|---|
| `git worktree add` says `~/wfglink-run` already exists | Keep it. Run `git -C ~/wfglink-run fetch origin claude/practical-rubin-5vu12u`, then `git -C ~/wfglink-run merge --ff-only origin/claude/practical-rubin-5vu12u`. Proceed only if both succeed. This preserves local files and refuses a conflicting or divergent update. If it stops, send `git -C ~/wfglink-run status --short` and the error; do not force a checkout or reset. |
| `setup_mac.sh` says Python 3.12 from python.org is missing | Install it (Before the day), then run `./scripts/setup_mac.sh` again. |
| A `doctor` line ends in FAIL | Do what its "fix:" says and run `python -m wfglink doctor` again. The clips line FAILs until the two clips are downloaded (setup does it when online). If unsure, paste the line to Claude. |
| Setup or `fetch_clips.py` says CERTIFICATE_VERIFY_FAILED, or "no HTTPS certificates" | Run `./scripts/setup_mac.sh` again (it installs the certificates the download uses). If it stays, double-click "Install Certificates.command" in the "Python 3.12" folder of Applications, then run setup again. |
| `command not found: python`, or `No module named wfglink` | The environment is off in this window: `cd ~/wfglink-run/wfglink` and `source .venv/bin/activate`. |
| The synthetic screen opened on the MacBook although a monitor is connected | Fine for today. Paste the `doctor` screens line to Claude. |
| `cameras --open 5` ends in an error, or says it uses opencv | Paste its lines to Claude. The booth still works: it falls back to the second way of opening the camera. |
| `cameras --request` shows no dialog and the answer is `denied` or `not_determined` | System Settings > Privacy & Security > Camera: turn Terminal on. Quit Terminal completely (Command-Q), open it again, turn the environment on and run `python -m wfglink cameras --request` again. If Terminal is not in that list, run `tccutil reset Camera com.apple.Terminal` first; the next `cameras --request` then shows the dialog. |
| `cameras` says `unsupported` | The camera helper packages are missing: run `./scripts/setup_mac.sh` again. If it stays, paste the lines to Claude. |
| The USB webcam is not in the list | Plug it into another port, directly into the MacBook, and run `python -m wfglink cameras` again. If it still is missing, tell Claude its brand and model. |
| The wrong camera is picked | Open `configs/booth_local.yaml` with `open -e configs/booth_local.yaml` (create it if it does not exist: `touch configs/booth_local.yaml` first). Under a `camera:` line (add one if there is none) write `  name: "part of the name"`, with the name as `cameras` shows it, and save. Keep any other lines. Run `python -m wfglink cameras` again to check. If you change the camera after Part 4, calibrate again. |
| The camera picture is black in `live --ember`, `calibrate` or `record` | Another app is using the camera: quit FaceTime, Zoom, Photo Booth and the like, then run the command again. |
| `calibrate` says "not stable" or stops after 90 seconds | All four corner markers must be in the picture. Hold the target flat and still, and tilt it a little if a lamp reflects in it. Check that it was printed at 100 percent. Run it again; nothing was written. |
| Your phone gets no trail in ember mode | Brightness to maximum, low power mode off, the screen towards the camera, held over the mark. Reload the page if the screen went dark. |
| Ember mode shows "No camera found" or "Camera access is off" instead of the picture | Follow "Ember mode shows no camera picture" in `booth/BOOTH_RUNBOOK.md`. |
| You need to stop | Stop between parts. When you come back, open Terminal, `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, and carry on. |
