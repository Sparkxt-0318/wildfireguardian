# Sitting 2 checklist

The final evening: about 30 minutes hands-on, then the booth runs by itself overnight, then about 25 minutes in the morning for the finish and the rehearsal. One command guides the evening and writes one combined report. You can stop at any time; running the same command again continues where you left off.

## Before the evening

- Sitting 1 is done, so the Mac already has Python 3.12, the wfglink environment and `configs/booth_local.yaml` with the camera settings. Sitting 2 keeps those settings and adds its own.
- Refresh the worktree to the latest demo build:

```
cd ~/wildfireguardian            # your main checkout (only used to fetch)
git fetch origin claude/practical-rubin-5vu12u
git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u
```

- On the iPad, install a video player that can repeat one video (VLC for Mobile has Repeat One) and check once that a video restarts by itself at its end.
- Charge the iPhone 13 and the iPad Air. Both stay on their chargers all night.
- iPhone and Mac signed in to the same Apple Account, AirDrop on for the Mac and the iPad.
- Optional: try the whole flow without hardware first with `bash ~/wfglink-run/wfglink/scripts/sitting2.sh --dry-run` (about 4 minutes, nothing to do). It writes to `~/wfglink-sitting2-dry`, never to your real report or settings.

## Parts on the table

- iPhone 13 with its Lightning to USB-C cable, and the tripod with the phone clamp.
- iPad Air on its rigid stand, with its charger.
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
| 2 | The booth clip is prepared at hold factor 2 and 3. AirDrop both files from the folder it names to the iPad and play the hold-2 file full screen with Repeat One, controls hidden, all four corner patterns visible. iPad brightness about 80 percent; Auto-Brightness, True Tone and Night Shift off; Auto-Lock Never. iPhone on the tripod in landscape, 30 to 50 cm away, the iPad filling about two thirds of the picture, slightly off square. Hood over both. Mac menu bar Video menu: Reactions, Center Stage, Portrait and Studio Light off. | 7 |
| 3 | Check B. A 60 s booth run on the external monitor measures the clean-frame yield. Answer whether the picture filled the external monitor. If the yield is below 0.80, the script asks you to play the hold-3 file and runs again. | 6 |
| 4 | Unplug test. A 60 s run: unplug the iPhone cable from the Mac when the console says UNPLUG (at 15 s) and plug it back when it says PLUG IN (at 35 s). The booth must switch to the webcam or the REPLAY band and come back to the iPhone by itself within 15 s. | 3 |
| 5 | Only if a USB webcam is plugged in: aim it at the iPad under the hood; 30 s run from the webcam alone. | 3 |
| 6 | Worker mode. Two 30 s runs (thread and process); nothing to do. The faster one is kept. | 2 |
| 7 | The settings are saved to `configs/booth_local.yaml` (hold factor, booth clip, worker mode, screen). Automatic. | 1 |
| 8 | Overnight soak. Check that the iPad, iPhone and MacBook are on their chargers and the lid is open, then press Enter. The booth starts fullscreen and runs all night. You can close the Terminal window. | 2 |

About 27 minutes, plus the overnight run.

## The morning

1. In Terminal:

```
bash ~/wfglink-run/wfglink/scripts/sitting2.sh --finish
```

It stops the booth and the sampler, analyses the night (hours, frames per second, memory growth, restarts, camera switches, errors), asks whether the iPhone was uncomfortably hot, and prints one line. Paste that line to Claude. The full report is `~/wfglink-sitting2/report_sitting2.json`; Claude may ask for it.

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
| report_sitting2.json | Every step's results and the summary |
| soak.csv | One heartbeat sample per minute through the night |
| soak_supervisor.out, soak_sampler.log | Output of the background processes |
| wfglink/logs/booth.log | The booth supervisor and app log (restarts are counted from it) |

## If something goes wrong

| Problem | What to do |
|---|---|
| "No frame codes were read" | The iPad is not fully in the picture, the player controls cover a corner, the video is paused, or the screen is too dim. Fix it and rerun with `--from check_b_yield`. |
| Many frames "without readable markers" | Move the iPhone so all four corner patterns are inside the picture, with a margin. |
| The yield stays below 0.80 at hold 3 too | The script keeps hold 3 and says so. Brighter iPad and less glare help (a shorter iPhone exposure blends fewer frames). Claude reads the numbers from the report. |
| The picture appeared on the laptop screen | Answer no to the question; then type the number of the monitor visitors will see. |
| The camera did not come back after the replug | Check the cable at both ends and that the iPhone is still on the same Apple Account, then rerun with `--from unplug_test`. |
| The process worker run failed | Nothing to do: thread mode is kept. The report keeps the error for Claude. |
| "No heartbeat yet" when the soak starts | Look at the monitor. If the booth is not showing, open `wfglink/logs/booth.log` and send Claude the last lines. |
| The Mac restarted or slept in the night | Run `--finish` anyway; it analyses what was recorded. |
| You need to stop | Press Control-C. Run the same command again to continue. |
| A step failed with an error | The report keeps the error text; carry on. Claude reads it from the report. |
