# Weather-night input pins

## us2024_input_manifest_night1.json

- 347 pins for the 6 US2024 held-out fires, after the night-1 weather step (finished 2026-11-13T00:15:22Z).
- The pins include 36 weather files and 6 `baseline-terrain/<event>/elevation_m_375m.tif`.
- sha256 286f4c47d1c21d12485b4ec2079ce09c698c21af73d64037921b34284e6592c2

Regenerate with:

    python3 -I research/harness-2026-11/data-fetch/make_input_manifest.py <US2024_WORKSPACE>/data/environment OUT.json \
      ID-BOF-000683_Wapiti_Wapiti ID-BOF-000904_Goat ID-BOF-001080_Lava ID-SCF-240202_RedRock WA-SES-000173_Pioneer WY-BTF-002416_FishCreek
