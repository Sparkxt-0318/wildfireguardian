# Sitting 1 tonight: MacBook camera and iPhone

For one block to forward, with the exact commands and all manual differences, use
[`SITTING1_FORWARDABLE.txt`](SITTING1_FORWARDABLE.txt).

No new camera or LED rig is needed. The MacBook's built-in camera tracks the
iPhone's screen; the iPhone is never the camera. A4 printing is needed for the
calibration. This is a smoke check, not a measurement-accuracy validation.

## Before starting

- Install Python 3.12 from python.org if it is missing. The setup script explains
  the installer it needs. Internet is needed for the first install and downloads.
- Connect the MacBook charger. Quit FaceTime, Photo Booth, Zoom and other camera
  apps. Put Mac and iPhone on the same Wi-Fi. A guest network may block devices
  from reaching each other; use a network that allows that connection.
- Print `booth/ember/calibration_target_A4.pdf` on A4 at actual size, Scale 100%,
  with Fit to page off. Check its 100 mm line with a ruler. Keep the sheet flat on
  card. Mark the standing spot 2.0 m from the camera lens; target and phone are
  held over the same mark, facing the camera.

## Exact commands

If `~/wfglink-run` does not exist, create the separate worktree from your existing
repository. Change only the first path if your main clone is elsewhere:

```sh
wfglink_first_run() {
  cd ~/wildfireguardian || return
  git fetch origin claude/practical-rubin-5vu12u || return
  git worktree add --detach ~/wfglink-run origin/claude/practical-rubin-5vu12u || return
  cd ~/wfglink-run/wfglink || return
  open booth/ember/calibration_target_A4.pdf
  ./scripts/sitting1_tonight.sh
}
wfglink_first_run
```

If the worktree already exists, update it safely and start the script:

```sh
wfglink_tonight() {
  cd ~/wfglink-run/wfglink || return
  git -C .. fetch origin claude/practical-rubin-5vu12u || return
  git -C .. merge --ff-only origin/claude/practical-rubin-5vu12u || return
  open booth/ember/calibration_target_A4.pdf
  ./scripts/sitting1_tonight.sh
}
wfglink_tonight
```

If the update stops, keep the files and send the error with
`git -C ~/wfglink-run status --short`. Do not force a checkout or reset. The script
uses `.venv/bin/python` directly, so you do not have to activate the environment.

## One checklist, in script order

1. **Setup.** Press Enter. Packages and the approved booth clips install. Click
   Allow if macOS asks for camera permission. A setup failure is recorded.
2. **Doctor.** Read its lines and fix any FAIL before relying on the booth. Doctor
   checks your normal booth settings. A failure caused by an old camera setting
   stays visible even if tonight's separate built-in check succeeds.
3. **Built-in camera.** The script finds a usable built-in camera and pins it by
   name in this run's `tonight.yaml`. It requests permission and opens it for a
   short check. It never substitutes a USB camera or the iPhone. Existing
   `configs/booth_local.yaml`, calibration and other settings are preserved.
4. **Approved fire clip.** Press Enter for C5, the approved NIST emberometer clip,
   for 60 seconds. Try A twice for raw/analysed and L twice for language. Note
   whether the trails and counters look right. Esc twice exits early.
5. **Local phone page and ember mode.** Press Enter. The script displays the local
   Wi-Fi address and a QR code before waiting. Allow incoming connections if
   macOS asks. Open that address on the iPhone, turn brightness to maximum, turn
   Low Power Mode off and tap once. Confirm the glowing page appears. Press
   Enter for 60 seconds of ember mode. Hold the phone over the 2.0 m mark; move
   slowly and quickly, hold still and turn away. Note missing tracks or false
   lamps/windows. Turn off all camera video effects in the menu bar. Speeds
   before step 6 use the nominal field of view.
6. **A4 calibration.** Confirm that the print line measures 100 mm. Press Enter
   and hold the target flat over the 2.0 m mark with all four markers in view.
   Calibration finishes when stable, or reports that it could not finish. It
   saves into this run's `tonight.yaml`, not your normal booth config.
7. **Send the report.** The script prints `report.txt` to paste back and the exact
   path to the combined `report.json`. Send either the complete text or the JSON,
   including failed or skipped steps. Every run gets its own directory under
   `results/runs/sitting1/`; earlier results cannot be reused accidentally.

Control-C stops the script, closes its local server and writes an interrupted
report. Skipped steps produce an incomplete report. A completed checklist means
the commands and app health checks ran; the human notes still need review. A live
command's zero exit cannot hide missing frames, worker errors, a synthetic fire
fallback or a missing ember camera. No real recordings or validation suites run
in this short sitting.

The local page server stops when the script ends. To open it again:

```sh
cd ~/wfglink-run/wfglink
.venv/bin/python -u scripts/serve_page.py
```

Keep that Terminal window open. The address is for this Wi-Fi and may change
later. Plain HTTP can limit the browser's wake lock; tap once to start the page's
video fallback and check that the phone stays awake.

To check the calibrated speeds afterwards, copy the exact command printed at
the end of the script. It is `.venv/bin/python -m wfglink live --ember --config`
followed by the full path of this run's `tonight.yaml`. That explicit override is
required because tonight deliberately preserves your normal booth config.

## Publish the phone page and set the QR address

Publication is a separate manual step and is not performed by the sitting script.
The simplest destination is a small separate public repository, avoiding changes
to the WildfireGuardian repository's existing hosting:

1. On GitHub, create a public repository named `ember` under your account.
2. Upload only `wfglink/booth/ember/index.html` at that repository's root and commit
   it on `main`. Do not upload private clips, recordings or local configuration.
3. Open Settings > Pages > Build and deployment. Choose Deploy from a branch,
   branch `main`, folder `/ (root)`, then Save.
4. Wait for GitHub's deployment to finish. Open the address shown in Settings,
   usually `https://YOUR-NAME.github.io/ember/`, on the iPhone and check it.
5. In the booth worktree, run `touch configs/booth_local.yaml` and
   `open -e configs/booth_local.yaml`. Keep all existing settings. Add the URL
   under the existing `booth:` mapping, or add that mapping if absent:

```yaml
booth:
  ember_page_url: https://YOUR-NAME.github.io/ember/
```

6. Run `.venv/bin/python scripts/make_placards.py --card ember_page`. Print
   `booth/placards/ember_page_ko.pdf` and `ember_page_en.pdf` on A5 at 100%. Scan the
   printed QR code to check it. Normal ember mode now shows the same address and
   QR code. Tonight's isolated config continues to use its temporary local URL.

The page works on any static host. Reusing this repository would need a Pages
workflow that publishes `wfglink/booth/ember/` as its artifact, or a dedicated
publishing branch; branch-based Pages cannot select that nested folder directly.
The separate repository avoids that extra setup. No account or deployment state
has been assumed or changed here.

## Differences from the earlier manual

- Tonight replaces the parts-dependent long sitting with setup, doctor, an
  approved clip, built-in camera, local phone page and A4 calibration in one script.
- The LED suite, turntable, `led_notes.yaml`, iPad filming and Continuity Camera
  steps were removed by your later decisions. The iPhone only displays the page.
- Keys A and M are added. Ember mode tracks at most three phones; extra phones
  are ignored. A affects fire mode only.
- `doctor` has additional video, camera, data and clip checks beyond the manual's
  original four. The script records all checks and command failures.
- Tonight saves calibration in its isolated override to protect existing booth
  settings; use the printed `--config` command to reuse it. The longer sitting
  still records `ember_free`/`ember_ruler` and runs `validate --suite ember` later.
- Updates use a fast-forward merge and stop on conflict. Forced checkout/reset
  instructions were unsafe because they can discard files across the repository.
- Hosting the page is optional for tonight; local Wi-Fi works while its server
  runs. Publication and setting the permanent QR URL remain explicit manual steps.
- UVC dashcams are optional future hardware: select USB PC-camera mode, choose
  the listed device name in `camera.name`, then recalibrate that camera.
