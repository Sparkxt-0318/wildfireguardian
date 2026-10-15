# Sitting 1 checklist

As soon as your parts arrive. About 90 minutes, plus an optional night drive that can wait for another evening. Six parts, in order: setup, dashcam, LED rig, recordings, validate, send files. You can stop between parts; nothing is lost.

Every command runs in Terminal. In each new Terminal window, first go to the folder and turn on the environment:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
```

The prompt then starts with `(.venv)`.

## Before the day

- Install Python 3.12 from https://www.python.org/downloads/ (the macOS 64-bit universal2 installer, any 3.12.x). The setup script uses only this Python.
- Internet for the setup (the first install downloads a few hundred MB).
- Charge the dashcam if it has a battery, and find a way to power it on the table (most dashcams run from a USB charger; see its manual).
- Back up anything you want to keep from the dashcam's SD card, then format the card in the dashcam's menu, so only today's files are on it.
- Set the dashcam's clock to the right time. It makes the files easy to find.

## Parts on the table

- The MacBook and its charger. The external monitor is optional today.
- The 블랙박스 dashcam, its SD card, a card reader and its power cable.
- A record turntable with 33 and 45 rpm. Any motorized rotating platform also works: record its slower speed as `led_33rpm` and its faster speed as `led_45rpm` (the check then warns that the speeds are not 33 and 45 rpm, which is expected; the stopwatch time is the truth).
- Three small battery orange LEDs, tracing paper and tape.
- Something that holds the dashcam lens straight down above the turntable, about 30 to 40 cm up: a tripod with a side arm, a clamp, or the dashcam's own mount fixed under a shelf.
- A ruler (30 cm) and a tape measure.
- A stopwatch (a phone's clock app is fine).
- A room you can make dark, and a small lamp you can dim.

## Part 1: Setup (about 15 minutes)

In Terminal:

```
cd ~/wildfireguardian            # your main checkout of the repository (only used to fetch)
git fetch origin claude/practical-rubin-5vu12u
git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh
source .venv/bin/activate
python -m wfglink doctor
python -m wfglink live --synthetic
```

What each step does:

1. The worktree is a separate copy of wfglink at `~/wfglink-run`, so your other sessions' checkout is never switched. Use your own path in the first line if your clone is somewhere else.
2. `./scripts/setup_mac.sh` creates `.venv` with Python 3.12 from python.org, installs everything wfglink needs and creates `data/raw`. The first run takes 5 to 10 minutes. Running it again is safe: it only adds what is missing.
3. `source .venv/bin/activate` turns the environment on for this Terminal window.
4. `python -m wfglink doctor` prints one line per check (Python, packages, fonts, screens). Every line must end in OK. A line that ends in FAIL says how to fix it; do that and run `doctor` again. The screens line lists the screens the Mac sees.
5. `python -m wfglink live --synthetic` opens the full booth screen on generated video, fullscreen on the external monitor if one is connected, otherwise on the MacBook. Within a few seconds you should see orange ember tracks on the left, four cards of green numbers on the right, and the tag "합성 영상 · 실측 아님" ("Synthetic video · not measured" in English). Press L (language), T (tracks), F (field), G (gate), Space (pause, then Space again), and I (limits card, then I again) once each. Press Esc, then Esc again, to quit.

Then start downloading the approved public clips for the booth in a second Terminal window (Command-N):

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
python scripts/fetch_clips.py
```

It downloads about 1 GB, one file at a time, and may pause for 10 minutes when Wikimedia limits the rate. Leave the window open and carry on; it may finish after the sitting. Running it again resumes it and skips what is already there.

## Part 2: Dashcam (about 10 minutes)

In the dashcam's menu:

- Resolution and frame rate: the setting you would use in a car (for example 1920x1080 at 30 fps).
- Date and time stamp: off if the menu allows it. If not, leave it on and note where it sits in the picture.
- WDR or HDR: leave it at the setting you would use in a car, and note it.
- Loop recording length: the longest it offers, so fewer recordings are split into several files.
- Impact sensor (G-sensor) at its lowest, so handling the dashcam does not move files to an event folder. Parking mode off.

Copy the notes template and open it:

```
cp data/led_notes_template.yaml data/raw/led_notes.yaml
open -e data/raw/led_notes.yaml
```

It opens in TextEdit. Fill in the dashcam keys now and the others as you go; save with Command-S. Keep the key names exactly as they are. Every key:

| Key | What to write | Example |
|---|---|---|
| `dashcam_model` | Brand and model from its label, in quotes | "brand model" |
| `file_type` | The file type it writes: mp4, mov, ts or avi (look at a file on the card) | mp4 |
| `resolution` | Recording resolution from the menu, width x height | 1920x1080 |
| `fps` | Frame rate from the menu | 30 |
| `date_stamp` | off, or where the date and time sit in the picture: top-left, top-right, bottom-left, bottom-right, top or bottom. That region is masked in every clip. | bottom-left |
| `wdr_hdr` | The WDR or HDR setting: on, off or auto | off |
| `camera_height_cm` | Height of the dashcam lens above the LEDs, in cm (Part 3) | 35 |
| `led_radius_mm` | Distance of each LED from the turntable centre, in mm, smallest first, as a list of three (Part 3) | [30, 80, 140] |
| `turns_timed` | How many turns you timed at each speed (Part 4) | 30 |
| `time_33rpm_s` | Stopwatch seconds for those turns at 33 rpm (Part 4) | 54.0 |
| `time_45rpm_s` | Stopwatch seconds for those turns at 45 rpm (Part 4) | 40.0 |

`date_stamp` also takes a box in fractions of the frame (the template shows how), for a stamp that sits somewhere else. The true LED speed comes from your notes: 2π × radius × turns_timed / time.

## Part 3: LED rig (about 15 minutes)

1. Tape the three LEDs flat on the platter, facing up, at about 3, 8 and 14 cm from the centre. Put a small square of tracing paper over each one as a diffuser.
2. Measure each LED's distance from the centre of the spindle to the centre of the LED, in mm, and write the three values into `led_radius_mm`.
3. Fix the dashcam with its lens straight down above the spindle, about 30 to 40 cm up, with the turntable in the middle of the picture (the lens is wide, and its edges bend straight lines).
4. Measure the height from the LEDs up to the lens, in cm, and write it into `camera_height_cm`.
5. Check the picture on the dashcam's screen or in its phone app: the platter must look round, not oval, and centred. If the dashcam has neither, record 10 s, copy the file to the Mac and look at it there.
6. Put a small piece of tape on the table next to the platter's edge as a mark for the stopwatch.

## Part 4: Recordings (about 25 minutes)

Start and stop each recording with the dashcam's record button if it has one; otherwise by plugging its power in and out (it finishes the file when the power goes). Write down the clock time of each recording, so you can find its files on the card.

| Name | What to record | Length |
|---|---|---|
| `room_test` | The room as it is, lights on, the dashcam on its stand. Record it first: it checks that the files decode. | about 1 min |
| `led_33rpm` | Room dark, LEDs on, turntable at 33 rpm. Start recording once it is up to speed. Time 30 turns with the stopwatch while it records. | about 90 s |
| `led_45rpm` | The same at 45 rpm, timing 30 turns again. | about 90 s |
| `led_ruler` | Turntable stopped, a ruler lying flat across the centre at the height of the LEDs, a dim lamp on so its marks show. | about 30 s |
| `night_drive` | Optional now: the dashcam in the car on a night drive, no fire. It is the hard negative. | 2 to 5 min |

Timing 30 turns: start the stopwatch when one chosen LED passes the tape mark, count the passes, and stop on the 30th. Write `turns_timed: 30` and the two times into `led_notes.yaml`, then save it.

Copying the files:

1. Put the SD card into the card reader. It appears in Finder. The videos are in a folder such as DCIM, Movie, Normal or Video; their names usually contain the date and time.
2. Open the target folder in Finder with `open data/raw` in Terminal.
3. Copy (do not move) each recording into it, then rename it to its name from the table, keeping its extension: for example `led_33rpm.mp4`. Upper or lower case extensions are both fine. Finder may hide extensions; to see them, choose Finder > Settings > Advanced > Show all filename extensions.
4. A recording the dashcam split into several files is named `_a`, `_b` and so on, in time order: `led_33rpm_a.mp4`, `led_33rpm_b.mp4`. Never keep a plain `led_33rpm.mp4` next to its parts.
5. Do not trim, convert or re-save the videos in any app. The check needs the dashcam's original files.

The accepted extensions are .mp4, .mov, .ts and .avi.

## Part 5: Validate (about 5 minutes)

```
python -m wfglink validate --suite led
```

It reads the recordings and `led_notes.yaml` in `data/raw`, masks the date stamp, and prints one line per clip: the LEDs tracked and the median speed error for the LED clips, and counts per minute for `room_test` and `night_drive` (false counts, since there is no fire). A summary line gives the median speed error against the goal of at most 5 percent. It writes `results/validation/led_report.json`, with stills of each clip next to it that show the masked date stamp and the LED rings.

- If it says a file name or a key in `led_notes.yaml` is missing or wrong, it says what to write. Fix it and run the same command again.
- Look at the stills (`open results/validation`): the date stamp must sit inside the masked box, and no LED ring should pass under it.
- A missed goal is a result, not a failure. Send the files either way.

## Part 6: Send files (about 10 minutes)

Upload these to one new folder in Google Drive, Dropbox or iCloud Drive:

- `results/validation/led_report.json`, and the stills folder next to it;
- `data/raw/led_notes.yaml`;
- the recordings in `data/raw` (`led_33rpm`, `led_45rpm`, `led_ruler`, `room_test`, `night_drive` and their parts), as they are. The public clips (names starting with C) are not needed.

`open results/validation` and `open data/raw` show the folders in Finder, so you can drag the files. Share the folder as "anyone with the link can view", then paste into the chat with Claude: the link, the lines `validate` printed, and the `doctor` lines from Part 1.

## Later: the night drive

Record it on any evening, copy it into `data/raw` as `night_drive` (or `night_drive_a`, `night_drive_b`), run `python -m wfglink validate --suite led` again, and upload the new `led_report.json` and the clip to the same shared folder.

## If something goes wrong

| Problem | What to do |
|---|---|
| `git worktree add` says `~/wfglink-run` already exists | It is there from before. Update it instead with `git -C ~/wfglink-run fetch origin` and `git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u`, then carry on from `cd ~/wfglink-run/wfglink`. |
| `setup_mac.sh` says Python 3.12 from python.org is missing | Install it (Before the day), then run `./scripts/setup_mac.sh` again. |
| A `doctor` line ends in FAIL | Do what its hint says and run `python -m wfglink doctor` again. If unsure, paste the line to Claude. |
| `command not found: python`, or `No module named wfglink` | The environment is off in this window: `cd ~/wfglink-run/wfglink` and `source .venv/bin/activate`. |
| The synthetic screen opened on the MacBook although a monitor is connected | Fine for today. Paste the `doctor` screens line to Claude. |
| `validate` says a file name is wrong or a file is missing | Rename the file as the message says, then run it again. |
| `validate` says a key in `led_notes.yaml` is missing or malformed | Write it as the message shows, save, run it again. |
| A ring is flagged as passing under the date stamp | Move the turntable or the dashcam so no LED passes under the stamp, then record that clip again. |
| The camera is flagged as tilted (an oval ring) | Level the dashcam so it looks straight down, then record the LED clips again. |
| The dashcam writes another file type (for example .mkv) | Tell Claude the file type; do not convert the files. |
| You need to stop | Stop between parts. When you come back, open Terminal, `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, and carry on. |
