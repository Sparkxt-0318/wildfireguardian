# Sitting 2 checklist

The final evening: about 30 minutes hands-on, then the booth runs by itself overnight, then about 25 minutes in the morning for the finish and the rehearsal. One command guides the evening and writes one combined report. You can stop at any time; running the same command again continues where you left off.

## Before the evening

- Sitting 1 is done, so the Mac already has Python 3.12, the wfglink environment, the downloaded clips in `wfglink/data/raw/` and `configs/booth_local.yaml` with the camera settings. Sitting 2 keeps those settings and adds its own.
- Refresh the worktree to the latest demo build:

```
cd ~/wildfireguardian            # your main checkout (only used to fetch)
git fetch origin claude/practical-rubin-5vu12u
git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u
```

- On the iPad, install VLC for Mobile (its player has Repeat One) and check once that a video restarts by itself at its end. The Photos app cannot repeat a video.
- Charge the iPhone 13 and the iPad Air. Both stay on their chargers all night.
- iPhone and Mac signed in to the same Apple Account.
- Optional: try the whole flow without hardware first with `bash ~/wfglink-run/wfglink/scripts/sitting2.sh --dry-run` (about 4 minutes, nothing to do). It writes to `~/wfglink-sitting2-dry`, never to your real report or settings.

## Parts on the table

- iPhone 13 with its Lightning to USB-C cable, and the tripod with the phone clamp.
- iPad Air on its rigid stand, with its charger and its USB-C cable (also used to copy the clip into VLC).
- The black cloth for the hood.
- The external monitor connected to the MacBook, and the MacBook charger.
- The USB webcam, if you have it.
- A power strip.

## Run it

In Terminal:

```
bash ~/wfglink-run/wfglink/scripts/sitting2.sh
```

The script prepares the booth video files first (a few minutes the first time), then guides you through check B, writes the chosen settings and starts the overnight soak.

## What the script will ask you to do

| Step | What | Minutes |
|---|---|---|
| 1 | Confirm the parts. Versions, free disk, sitting 1 settings, screens and cameras are checked automatically. | 3 |
| 2 | The booth clip is prepared at hold factor 2 and 3. Copy both files from the folder it names into VLC on the iPad: connect the iPad with its USB-C cable, select it in the Finder sidebar, open the Files tab and drag both files onto VLC. (AirDrop also works, but the files land in Photos: there, select both, Share, Save to Files, On My iPad, VLC.) Play the hold-2 file full screen in VLC with Repeat One, controls hidden, all four corner patterns visible. iPad brightness about 80 percent; Auto-Brightness, True Tone and Night Shift off; Auto-Lock Never. iPhone on the tripod in landscape, 30 to 50 cm away, the iPad filling about two thirds of the picture, slightly off square. Hood over both. | 7 |
| 3 | Check B, for hold 2. First a 30 s booth run on the external monitor; meanwhile click the green camera icon in the Mac menu bar (Video) and check that Reactions, Center Stage, Portrait and Studio Light are off (that menu only exists while an app uses the camera). Answer whether the picture filled the external monitor. Then about a minute of coverage windows without the booth picture (the camera restarts between them; leave everything as it is). If hold 2 is not safe by the rule below, the script asks you to play the hold-3 file and measures that too. | 8 |
| 4 | Unplug test. A 60 s run: unplug the iPhone cable from the Mac when the console says UNPLUG (at 15 s) and plug it back when it says PLUG IN (at 35 s). The booth must switch to the webcam or the REPLAY band, come back to the iPhone by itself within 20 s, and stay on it. | 3 |
| 5 | Only if a USB webcam is plugged in: aim it at the iPad under the hood; 30 s run from the webcam alone. | 3 |
| 6 | Worker mode. Two 30 s runs (thread and process); nothing to do. Thread mode is kept unless process mode paints at least 10 percent more frames per second (or thread mode failed). | 2 |
| 7 | The settings are saved to `configs/booth_local.yaml` (hold factor, booth clip, worker mode, screen). Automatic. | 1 |
| 8 | Overnight soak. Check that the iPad, iPhone and MacBook are on their chargers and the lid is open, then press Enter. The booth starts fullscreen and runs all night. Leave Terminal running: you may minimise the window, but do not quit Terminal, because the booth was started from it and macOS ties the camera permission to it. | 2 |

About 29 minutes, plus the overnight run.

## How the hold factor is chosen

The booth analyses only camera frames whose four corner codes are clean, and it analyses each source frame once (a second clean view of the same source frame is skipped). So the question is not how many camera frames are clean (the clean-frame yield) but whether every source frame the iPad showed was read clean at least once (the source coverage).

The rule (`sitting2.hold_rule: coverage`, the default) keeps hold factor 2 when all three hold:

- in every coverage window, at least 98 percent (`sitting2.coverage_min`) of the source frames shown were read clean at least once;
- in at least one window, most source frames (`sitting2.spare_views_min`) were read clean twice. Two clean views of one source frame mean that the unclean time around a picture change is shorter than one camera frame, and then no moment can lose a source frame, so the margin is real and not one lucky moment;
- at least half of the windows gave a measurement (`sitting2.coverage_windows_used_min`); a window in which the camera did not open, or too few codes were read, does not count.

Otherwise the script asks for the hold-3 file, measures it the same way and takes hold 3 when it passes, or when it does at least as well as hold 2. When neither passes, the better one is kept and the console says so. The clean-frame yield is still measured in the booth runs and reported for both hold factors; the plan's earlier rule (hold 2 when the yield reaches 0.80) is still available as `sitting2.hold_rule: yield`.

Why not the yield: the iPad does not change its whole picture at once. It rewrites the screen line by line over most of each 16.7 ms refresh, so a camera frame taken while that sweep runs from one edge's codes to the other's sees two pictures and is dropped, whatever the camera does. At hold 2 a new source frame comes every 67 ms and the iPhone takes two frames of each. Often one of the two falls into the sweep: the yield is then close to 0.5, yet every source frame still has its clean frame. The coverage stays complete as long as the unclean time around each picture change is shorter than one camera frame (33 ms); a long iPhone exposure, or a rolling shutter that runs across the sweep, can make it longer, and then hold 3 (three camera frames per source frame) is needed.

Why several windows: the iPhone and the iPad run on separate clocks that differ by a tiny amount, so the moment within each picture at which the iPhone takes its frames drifts only over many minutes. One 60 s run sees one such moment and can be lucky. The script therefore measures 8 windows of 7.5 s (`sitting2.coverage_windows`, `sitting2.coverage_seconds`) and restarts the camera between them, which starts each window at a new moment; the worst window counts. The report keeps every window's yield and coverage, so the spread between windows is visible to Claude.

## The morning

1. In Terminal:

```
bash ~/wfglink-run/wfglink/scripts/sitting2.sh --finish
```

It stops the booth and the sampler, analyses the night (hours, frames per second, memory growth, restarts, camera switches, errors, and whether the booth kept measuring), asks whether the iPhone was uncomfortably hot, and prints one line. "Kept measuring" uses the frame counters in the booth's heartbeat: the soak fails if, on one camera, frames kept arriving but none was analysed (or none arrived) for 3 minutes (`sitting2.analysis_stall_s`), because a paused or hidden iPad should make the booth switch source within seconds. The report also gives the share of camera frames read clean and the source coverage through the night. Paste that line to Claude. The full report is `~/wfglink-sitting2/report_sitting2.json`; Claude may ask for it.

If you already pressed Esc twice on the booth, the soak ended then; `--finish` still works and counts the night up to that moment. It only stops processes the soak itself started, so a booth you started by hand is left alone, and it never reinstalls the environment the booth runs from. Running `--finish` a second time shows the same result again.

2. The rehearsal, about 20 minutes, following `booth/BOOTH_RUNBOOK.md` from a cold start:
   - the 10 minute setup checklist, timed;
   - start the booth with the one command;
   - press L, I, T, F and G once each and check what changes;
   - unplug the iPhone cable once and watch the booth fall back and come back;
   - press Esc twice to quit.

Tell Claude anything that was slow, unclear or surprising; the runbook gets fixed the same day.

## Files

| File | Content |
|---|---|
| report_sitting2.json | Every step's results (with each coverage window) and the summary |
| soak.csv | One heartbeat sample per minute through the night |
| soak_supervisor.out, soak_sampler.log | Output of the background processes |
| wfglink/logs/booth.log | The booth supervisor and app log (restarts are counted from it) |

## If something goes wrong

| Problem | What to do |
|---|---|
| The video on the iPad does not repeat | It is playing in Photos. Copy it into VLC (step 2) and use Repeat One. |
| "No frame codes were read" | The iPad is not fully in the picture, the player controls cover a corner, the video is paused, or the screen is too dim. Fix it and rerun with `--from check_b_yield`. |
| Many frames "without readable markers" | Move the iPhone so all four corner patterns are inside the picture, with a margin. |
| Hold 3 is not safe either | The script keeps the better hold factor and says so. A long iPhone exposure is the usual cause: a brighter iPad picture shortens it. Claude reads the window numbers from the report. |
| The picture appeared on the laptop screen | Answer no to the question; then type the number of the monitor visitors will see. |
| The camera did not come back after the replug | Check the cable at both ends and that the iPhone is still on the same Apple Account, then rerun with `--from unplug_test`. |
| The process worker run failed | Nothing to do: thread mode is kept. The report keeps the error for Claude. |
| "A booth is already running" when the soak starts | Quit that booth (Esc twice, or Control-C in its Terminal window), then rerun with `--from soak_start`. |
| "No heartbeat yet" when the soak starts | Look at the monitor. If the booth is not showing, open `wfglink/logs/booth.log` and send Claude the last lines. |
| The Mac restarted or slept in the night | Run `--finish` anyway; it analyses what was recorded and reports the gaps. |
| You need to stop | Press Control-C. Run the same command again to continue. |
| A step failed with an error | The report keeps the error text; carry on. Claude reads it from the report. |
