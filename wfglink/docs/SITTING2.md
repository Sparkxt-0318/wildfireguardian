# Sitting 2 checklist

The final evening before the booth: about 30 minutes, then the booth runs by itself overnight under the soak, then about 30 minutes in the morning for the report and the rehearsal. Four parts, in order: update, booth, overnight soak, rehearsal.

Every command runs in Terminal, in the folder `~/wfglink-run/wfglink` with the environment on:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
```

## Before the evening

- Sitting 1 is done, so `~/wfglink-run` exists with its `.venv`.
- Mac settings, once: System Settings > Lock Screen: "Start Screen Saver when inactive" Never and "Turn display off on power adapter when inactive" Never. Focus on. Automatic updates off (System Settings > General > Software Update > Automatic updates).
- Displays: if you use the external monitor, set it to extend the desktop, not mirror it (System Settings > Displays). The booth picks the external monitor by itself.

## Parts on the table

- The MacBook and its charger, on a power strip.
- The external monitor and its cable, if you use one (without it the booth runs on the MacBook's screen).
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
python scripts/fetch_clips.py
```

1. The two `git` lines bring the worktree to the latest build.
2. `./scripts/setup_mac.sh` again installs anything new. It is safe to repeat.
3. `python -m wfglink doctor`: every line must end in OK. With the monitor connected, the screens line lists it.
4. `python scripts/fetch_clips.py` downloads any approved clip that is still missing and skips the rest. `ls data/raw` shows what is there. If it is slow (Wikimedia makes it pause), stop it with Control-C, run it again in a second Terminal window, and go on: a clip that is not there yet is skipped by the booth.

Then print the placards: `open booth/placards` shows them in Finder. Print each one on A5 at actual size (100 percent): "This is the sensor" for the dashcam stand, and the limits card, each in Korean and English.

## Part 2: Booth (about 15 minutes)

Connect the external monitor if you use one, then:

```
./booth/booth.sh
```

Check, in this order:

1. The booth opens fullscreen on the external monitor (on the MacBook without one) within a few seconds.
2. The clips of the playlist play one after another at their own speed, with orange ember tracks, and the status line names each clip and its credit line. Numbers fade in after a few seconds of each clip; every clip starts its counts from zero.
3. Press each key once and see it work: L (Korean or English), T (tracks), F (wind arrows), G (gate line), Space (pause; Space again resumes), I (limits card; I again closes it).
4. Unplug the monitor's cable: the booth moves to the MacBook's screen. Plug it back in: the booth moves back to the monitor.
5. Press Esc, then Esc again: the booth quits and `booth.sh` ends.

Double-clicking `booth/booth.command` in Finder starts the same booth in a Terminal window.

## Part 3: Overnight soak (2 minutes, then overnight)

The MacBook on its charger with the lid open, the monitor on (if you use one). Then:

```
python scripts/mac_soak.py --hours 8
```

It runs the booth screen with the playlist for 8 hours, logs fps and memory, and prints a PASS or FAIL report at the end. The booth appears fullscreen as in Part 2, and the Mac stays awake while it runs. Leave it alone: do not press keys on the booth, do not close the Terminal window, and do not start `booth.sh` at the same time. Start it before you go to bed; the report is waiting in the morning.

## Part 4: The morning

1. The report: the Terminal window shows it, ending in PASS or FAIL. Copy the whole report into the chat with Claude. On FAIL, it names the check that failed.
2. The rehearsal, about 20 minutes, following `booth/BOOTH_RUNBOOK.md` from a cold start:
   - the setup checklist, timed;
   - start the booth with `./booth/booth.sh`;
   - press L, T, F, G, Space and I once each;
   - unplug and replug the monitor once;
   - the dashcam on its stand with the "This is the sensor" placard, and the limits card next to the screen;
   - press Esc twice to quit.

Tell Claude anything that was slow, unclear or surprising; the runbook gets fixed the same day.

## Files

| File | Content |
|---|---|
| `logs/booth.log` | The booth supervisor's and the app's log (restarts are written here); rotated at 10 MB |
| `logs/heartbeat.json` | Rewritten every 2 s by the app: status, fps, the clip playing, memory |
| `logs/soak/` | One folder per soak, named by its start time, with the samples and the report |

Send the logs to Claude when you report a problem.

## If something goes wrong

| Problem | What to do |
|---|---|
| `git checkout` says your local changes, or untracked files, would be overwritten | Files that wfglink wrote in the worktree (the clip list after a download, an earlier report) are in the way. Run `git -C ~/wfglink-run checkout --detach --force origin/claude/practical-rubin-5vu12u`. It resets only wfglink's tracked files; `data/raw`, `.venv` and `logs` stay as they are. |
| `booth.sh` says the Python in `.venv` is not found | Run `./scripts/setup_mac.sh`, then start the booth again. |
| The booth shows "합성 영상 · 실측 아님" ("Synthetic video · not measured") instead of clips | The playlist's clips are not in `data/raw`. Run `python scripts/fetch_clips.py`, then start the booth again. A missing clip is skipped, and synthetic video plays only when no clip can play. |
| The booth opens on the MacBook although the monitor is connected | Esc twice, check the cable, start again. If it keeps happening, start it with `./booth/booth.sh --screen external`, or with the screen's name from the `doctor` screens line. |
| The picture stands still and the numbers stop | If the tag "일시정지" ("Paused") shows, press Space. Otherwise wait: the supervisor restarts a frozen app by itself within about 2 minutes. |
| The app restarted by itself | Nothing to do; the restart is in `logs/booth.log`. If it keeps happening, send the log to Claude. |
| The soak report says FAIL | Paste the whole report to Claude, with `logs/booth.log`. |
| The Mac slept or restarted in the night | Tell Claude; if there is time, run the soak again. |
| You need to stop the soak early | Press Control-C in its Terminal window. It stops the booth and prints the report for the hours so far; paste that to Claude. |
| You need to stop the booth | Esc, then Esc again, quits it. Control-C in its Terminal window stops `booth.sh` too. |
