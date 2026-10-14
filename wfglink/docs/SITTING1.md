# Sitting 1 checklist

About 60 to 75 minutes, plus an optional night drive. One command runs everything in order, tells you exactly what to record, checks each file as soon as you hand it over, and writes one combined report. You can stop at any time; running the same command again continues where you left off.

## Before the day

- Install Python 3.12 from https://www.python.org/downloads/ (macOS 64-bit universal2 installer, 3.12.x).
- Charge the iPhone 13, the iPad Air and the dashcam if it has a battery.
- iPhone and Mac signed in to the same Apple Account. AirDrop on for both.
- On the iPad, keep Files or Photos ready to receive PANEL_TEST.mp4 by AirDrop.

## Parts on the table

- iPhone 13 with its Lightning to USB-C cable, and the tripod with a phone clamp.
- iPad Air.
- Turntable or any motorized rotating platform, and three small orange LEDs with tracing paper over each. Tape them at about 3, 8 and 14 cm from the center.
- The 블랙박스 dashcam with its SD card, a card reader and USB power.
- A ruler or tape measure, and a stopwatch (the iPhone Clock app works, but use a second phone if the iPhone is recording).
- The external monitor connected to the MacBook.
- A room you can make dark.

## Run it

In Terminal:

```
cd ~/wildfireguardian            # your main checkout (only used to fetch)
git fetch origin claude/practical-rubin-5vu12u
git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u     # first time only
git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u  # later times
bash ~/wfglink-run/wfglink/scripts/sitting1.sh
```

The worktree keeps your other sessions' checkout untouched. The script installs everything the first time (5 to 10 minutes, needs internet), keeps the Mac awake, then guides you.

It also downloads the approved public clips (about 1 GB, one file at a time) in the background, because Wikimedia rate-limits Claude's network. They land in `wfglink/data/raw/` for the booth, and the upload folder links them in a `clips` folder so they upload with your recordings. The download keeps going after the sitting; running the script again resumes it.

## What the script will ask you to do

| Step | What | Minutes |
|---|---|---|
| 1 | Confirm the parts | 5 |
| 2 | AirDrop PANEL_TEST.mp4 (it appears in ~/wfglink-sitting1) to the iPad | 2 |
| 3 | Environment check (automatic) | 1 |
| 4 | Check A. iPhone on the cable, locked, landscape on the tripod, pointing at the spinning LEDs. Plug in the USB webcam if you have it. Allow camera access if macOS asks. | 10 |
| 5 | Live view: 20 s fullscreen on the external monitor. Press L once. While the picture shows, open the green camera icon (Video) in the Mac menu bar and turn off Reactions, Center Stage, Portrait and Studio Light (the menu exists only while an app uses the camera). Answer two yes or no questions. | 3 |
| 6 | Speed benchmark (automatic) | 1 |
| 7 to 9 | iPhone LED clips: speed 1, speed 2, ruler. Camera app, 1080p 30 fps, HDR Video off, AE/AF lock. AirDrop each clip to the Mac. Type the stopwatch time for 30 revolutions at each speed. | 10 |
| 10 to 12 | Dashcam LED clips: same three, with the dashcam pointing straight down. Then the SD card into the reader; pick the segments the script suggests. Stopwatch times again. | 12 |
| 13 | iPhone slow motion (240 fps) of the iPad playing PANEL_TEST.mp4, 5 s | 5 |
| 14 | Optional night drive with the dashcam (2 to 5 min, no fire). Say no to do it later. | 15 |
| 15 | Analysis (automatic) | 4 |
| 16 | Upload the folder and paste the summary to Claude | 8 |

After each recording the script checks it at once: LEDs visible, camera straight above the turntable (circle axis ratio at least 0.99), no HDR, right frame rate and length. If something is off it says what and offers to record again.

## File names

The script copies your originals unchanged under these names, so you never rename anything yourself.

| File | Device | Content |
|---|---|---|
| S1_IPH_LED_SPEED1 | iPhone | LED turntable, slower speed, 20 s |
| S1_IPH_LED_SPEED2 | iPhone | LED turntable, faster speed, 20 s |
| S1_IPH_LED_RULER | iPhone | Ruler in the LED plane, 10 s |
| S1_DC_LED_SPEED1 | Dashcam | LED turntable, slower speed, 90 s |
| S1_DC_LED_SPEED2 | Dashcam | LED turntable, faster speed, 90 s |
| S1_DC_LED_RULER | Dashcam | Ruler in the LED plane, 30 s |
| S1_IPH_PANEL_240FPS | iPhone | Slow motion of the iPad playing the test video, 5 s |
| S1_DC_NIGHT_DRIVE | Dashcam | Night drive without fire, 2 to 5 min (optional) |

Several dashcam segments get _01, _02 and so on.

## Upload

At the end the script prints the upload folder (~/wfglink-sitting1) and a one-line summary.

1. Upload the whole folder to Google Drive, Dropbox or iCloud Drive.
2. Share it as "anyone with the link can view".
3. Paste the link and the summary into the chat with Claude.

Do not re-encode or rename the videos; their SHA-256 hashes are in report_sitting1.json.

## Later: the night drive

```
bash ~/wfglink-run/wfglink/scripts/sitting1.sh --add night_drive
```

Then upload the folder again (only the new file changes).

## If something goes wrong

| Problem | What to do |
|---|---|
| macOS says Terminal may not use the camera | System Settings > Privacy & Security > Camera > allow Terminal, then rerun with `--from check_a` |
| No Continuity Camera found | Cable connected, same Apple Account, iPhone locked, landscape and still, Wi-Fi and Bluetooth on. Rerun with `--from check_a` |
| iPhone found but no frames | Nothing to do: the script builds the WFGLink app and retries inside it automatically. Allow camera access for WFGLink when asked. |
| Live view appears on the laptop screen | Answer no to the question; the report records it and sitting 2 picks the screen by name |
| You need to stop | Press Control-C. Run the same command again to continue. |
| A step failed with an error | The report keeps the error text; carry on. Claude reads it from the report. |
