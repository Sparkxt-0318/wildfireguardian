# Sitting 2 checklist

The final evening before the booth: about 40 minutes, then the booth runs by itself overnight under the soak, then about 30 minutes in the morning for the report and the rehearsal. Four parts, in order: update, booth, overnight soak, rehearsal.

Every command runs in Terminal, in the folder `~/wfglink-run/wfglink` with the environment on:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
```

## Before the evening

- Sitting 1 is done, so `~/wfglink-run` exists with its `.venv`, Terminal may use the camera, the A4 calibration is in `configs/booth_local.yaml`, and the ember page is on GitHub Pages.
- Mac settings, once: System Settings > Lock Screen: "Start Screen Saver when inactive" Never and "Turn display off on power adapter when inactive" Never. Focus on. Automatic updates off (System Settings > General > Software Update > Automatic updates).
- Displays: if you use the external monitor, set it to extend the desktop, not mirror it (System Settings > Displays). The booth picks the external monitor by itself.

## Parts on the table

- The MacBook and its charger, on a power strip.
- The external monitor and its cable, if you use one (without it the booth runs on the MacBook's screen).
- The booth camera: the USB webcam if you use one, else the MacBook's own camera, facing open floor.
- Your phone with the ember page open, and a second phone if you have one.
- Masking tape and the tape measure for the floor mark at 2.0 m, the A4 calibration target on its card, and the ember page's QR card (`booth/placards/ember_page_ko.pdf` and `_en.pdf`, made in sitting 1 Part 3).
- The dashcam on its stand, for the rehearsal.
- A printer with A5 paper, or A4 printed at actual size and cut.

## Part 1: Update (about 10 minutes)

```
cd ~/wfglink-run/wfglink
git -C ~/wfglink-run fetch origin
git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u
./scripts/setup_mac.sh
source .venv/bin/activate
python -m wfglink doctor
```

1. The two `git` lines bring the worktree to the latest build.
2. `./scripts/setup_mac.sh` again installs anything new and downloads a booth clip that is still missing. It is safe to repeat.
3. `python -m wfglink doctor`: every line (eight of them) must end in OK. With the monitor connected, the screens line lists it; the clips line says the booth's two clips are there.

Then print the placards: `open booth/placards` shows them in Finder. Print each one on A5 at actual size (100 percent): "This is the sensor" for the dashcam stand, the limits card, and the ember page's QR card for the standing spot, each in Korean and English. (No QR card there? Make it as in `booth/BOOTH_RUNBOOK.md`, "Making the ember page's QR card".)

## Part 2: Booth (about 25 minutes)

Connect the external monitor if you use one and the USB webcam if you use one. Put a tape mark on the floor 2.0 m straight in front of the camera lens (the standing spot: the phone is held over it). If the camera is not where it was in sitting 1, calibrate again first: `python -m wfglink calibrate`, standing just behind the mark and holding the A4 target out over it, flat at chest height, facing the camera, until the command ends by itself. Then:

```
./booth/booth.sh
```

Check, in this order:

1. The booth opens fullscreen on the external monitor (on the MacBook without one) within a few seconds, in fire mode.
2. The clips of the playlist play one after another at their own speed, with orange ember tracks, and the status line names each clip and its credit line. Numbers fade in after a few seconds of each clip; every clip starts its counts from zero.
3. Press each key once and see it work: L (Korean or English), T (tracks), F (wind arrows), G (gate line), Space (pause; Space again resumes), I (limits card; I again closes it), A (the raw clip fades in over about half a second; A again fades the analysed view back).
4. Press M: ember mode, with the camera picture (mirrored), the header "당신이 불티입니다 / You are an ember" in both languages and, bottom right, the page's QR code and address. Stand just behind the floor mark with the page open on your phone, hold it out over the mark and move it: it gets a trail, an ID and a speed in m/s, measured at 2.0 m; the number of embers counts it. With a second phone, both are tracked and the wind arrows come from both. Check that the room's lights are not taken for embers. Move the pointer to the top of the screen, click the green camera icon in the menu bar and check that Center Stage, Portrait, Studio Light, Background and Reactions are all off.
5. Press M again: back to fire mode.
6. Unplug the monitor's cable: the booth moves to the MacBook's screen. Plug it back in: the booth moves back to the monitor.
7. Press Esc, then Esc again: the booth quits and `booth.sh` ends.

Double-clicking `booth/booth.command` in Finder starts the same booth in a Terminal window.

## Part 3: Overnight soak (2 minutes, then overnight)

The MacBook on its charger with the lid open, the monitor on (if you use one). Then:

```
python scripts/mac_soak.py --hours 8
```

It runs the booth screen in fire mode with the playlist for 8 hours, logs fps and memory, and prints a PASS or FAIL report at the end. The booth appears fullscreen as in Part 2, and the Mac stays awake while it runs. Leave it alone: do not press keys on the booth (M would switch it to the camera), do not close the Terminal window, and do not start `booth.sh` at the same time. Start it before you go to bed; the report is waiting in the morning.

Optional, if there are two hours to spare before the overnight soak: `python scripts/mac_soak.py --hours 2 -- --ember` soaks ember mode (2 h: memory growth is judged only from 2 h on) with the real camera under the same rules (point the camera at the room; nobody needs to stand there). Paste its report too.

## Part 4: The morning

1. The report: the Terminal window shows it, ending in PASS or FAIL. Copy the whole report into the chat with Claude. On FAIL, it names the check that failed.
2. The rehearsal, about 20 minutes, following `booth/BOOTH_RUNBOOK.md` from a cold start:
   - the setup checklist, timed;
   - the floor mark at 2.0 m and the page's address card next to it;
   - start the booth with `./booth/booth.sh`;
   - press L, T, F, G, Space, I and A once each in fire mode;
   - press M, guide one "visitor" through ember mode as the runbook says (open the page, brightness up, stand on the mark, move the phone), then M back to fire mode;
   - unplug and replug the monitor once;
   - the dashcam on its stand with the "This is the sensor" placard, and the limits card next to the screen;
   - press Esc twice to quit.

Tell Claude anything that was slow, unclear or surprising; the runbook gets fixed the same day.

## Files

| File | Content |
|---|---|
| `logs/booth.log` | The booth supervisor's and the app's log (restarts are written here); rotated at 10 MB |
| `logs/heartbeat.json` | Rewritten every 2 s by the app: status, fps, the clip playing, the mode (fire or ember), raw or analysed, the camera state, memory |
| `logs/soak/` | One folder per soak, named by its start time, with the samples and the report |

Send the logs to Claude when you report a problem.

## If something goes wrong

| Problem | What to do |
|---|---|
| `git checkout` says your local changes, or untracked files, would be overwritten | Files that wfglink wrote in the worktree (the clip list after a direct `fetch_clips.py` run, an earlier report, regenerated placards) are in the way. Run `git -C ~/wfglink-run checkout --detach --force origin/claude/practical-rubin-5vu12u`. It resets only wfglink's tracked files; `data/raw`, `.venv`, `logs` and `configs/booth_local.yaml` (and the QR card you made) stay as they are. |
| `booth.sh` says the Python in `.venv` is not found | Run `./scripts/setup_mac.sh`, then start the booth again. |
| The booth shows "합성 영상 · 실측 아님" ("Synthetic video · not measured") instead of clips | The playlist's clips are not in `data/raw`. Run `./scripts/setup_mac.sh` while online (it downloads them), then start the booth again. A missing clip is skipped, and synthetic video plays only when no clip can play. |
| The booth opens on the MacBook although the monitor is connected | Esc twice, check the cable, start again. If it keeps happening, start it with `./booth/booth.sh --screen external`, or with the screen's name from the `doctor` screens line. |
| The picture stands still and the numbers stop | If the tag "일시정지" ("Paused") shows, press Space. Otherwise wait: the supervisor restarts a frozen app by itself within about 2 minutes. |
| The app restarted by itself | Nothing to do; the restart is in `logs/booth.log`. If it keeps happening, send the log to Claude. |
| Ember mode shows "No camera found", "Camera access is off", "Waiting for camera permission" or "Ember mode could not start" instead of the camera picture | The camera is missing, Terminal may not use it, or it does not open. Follow "Ember mode shows no camera picture" in `booth/BOOTH_RUNBOOK.md`: quit other camera apps, `python -m wfglink cameras --request`, and System Settings > Privacy & Security > Camera > Terminal on if needed. M returns to the fire footage meanwhile. |
| Your phone gets no trail, or the speed looks wrong | Brightness to maximum, the screen towards the camera, the phone held over the mark. If the speed still looks wrong, check the mark is 2.0 m from the lens and calibrate again (Part 2), holding the target over the mark too. |
| The soak report says FAIL | Paste the whole report to Claude, with `logs/booth.log`. |
| The Mac slept or restarted in the night | Tell Claude; if there is time, run the soak again. |
| You need to stop the soak early | Press Control-C in its Terminal window. It stops the booth and prints the report for the hours so far; paste that to Claude. |
| You need to stop the booth | Esc, then Esc again, quits it. Control-C in its Terminal window stops `booth.sh` too. |
