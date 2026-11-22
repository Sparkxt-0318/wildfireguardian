# Weather-night input pins

## us2024_input_manifest_night1.json

- 347 pins for the 6 US2024 held-out fires, after the night-1 weather step (finished 2026-11-13T00:15:22Z).
- The pins include 36 weather files and 6 `baseline-terrain/<event>/elevation_m_375m.tif`.
- sha256 286f4c47d1c21d12485b4ec2079ce09c698c21af73d64037921b34284e6592c2

Regenerate with:

    python3 -I research/harness-2026-11/data-fetch/make_input_manifest.py <US2024_WORKSPACE>/data/environment OUT.json \
      ID-BOF-000683_Wapiti_Wapiti ID-BOF-000904_Goat ID-BOF-001080_Lava ID-SCF-240202_RedRock WA-SES-000173_Pioneer WY-BTF-002416_FishCreek

## parta_input_manifest_night1.json (part-a, 490 events)

- 16,664 pins, covering every event in the part-a workspace's events.json: 2,940 weather files (6 per region) and 490 `baseline-terrain/<event>/elevation_m_375m.tif`.
- sha256 f70e52b00bfd8eaf12743cd60599238e72abefca80cbc0802c51a52a8ea2005a
- Made after the night-1 run finished (part-a STEP DONE 2026-11-13T01:27:33Z; ALL DONE).
  - The run made 591 requests, all HTTP 200, totalling 6,985.9 weighted calls (part-a: 574 requests, 6,149.69).
  - There were no restarts.

## parta_weather_completeness_night1.json

- One record per event: band count, first and last band UTC, `complete_hours`, nodes, whether every value is finite (finite node-hours equal total node-hours for all 3 variables), the number of responses, and the sha256 of `ecmwf_ifs_complete.json`.
- sha256 09af55fa8a65b1711f7bc64b8a64810d83b985db46ed47bb24a23ab3e7c3846a
- All 490 events: every value finite, and bands == complete_hours.

Regenerate with:

    python3 -I research/harness-2026-11/data-fetch/make_input_manifest.py <PARTA_WORKSPACE>/data/environment OUT.json
