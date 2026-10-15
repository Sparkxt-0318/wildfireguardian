# Booth demo: two ESP32 boards and a live signal-strength chart

This is a principle demo, not a fire sensor. It shows the idea behind the study: anything that enters the first Fresnel zone of a radio link changes the received level, and a jump in signal variance can be detected even when the mean barely moves. Nothing here has been tested on hardware yet.

## Parts

- Two ESP32 dev boards (any ESP32 with a PCB or external antenna), two USB cables, one laptop.
- Optional: two small 2.4 GHz directional antennas (ESP32 boards with a U.FL connector) to narrow the beam and reduce multipath from visitors.

## Setup

1. Flash `esp32_tx/esp32_tx.ino` to board A and `esp32_rx/esp32_rx.ino` to board B (Arduino IDE, ESP32 core 3.x).
2. Mount the boards facing each other 1.5 to 3 m apart at the same height. Over 2 m at 2.4 GHz the first Fresnel zone radius at mid-path is about 0.25 m.
3. Connect board B to the laptop and run `pip install pyserial matplotlib numpy`, then `python live_chart.py <serial port>`.

## What to show

- Baseline: the RSSI sits at a level with 1 dB steps and some multipath noise (expect 1 to 3 dB indoors).
- Mean attenuation: put a hand, a bottle of water or a person in the middle of the path. The level drops by several dB and the "drop" detector fires. Then hold the object just below the line of sight and show that a partial Fresnel-zone blockage still matters.
- Variance (the plume effect): move a hand or a sheet of wet cardboard quickly through the edge of the Fresnel zone. The rolling std rises while the mean barely changes, as the study predicts for hot turbulent plumes above a fire.
- Heat alone: a hair dryer or heat gun across the path is a fair test of refractive effects. Expect little or nothing at 2.4 GHz over 2 m. This is consistent with the model, which needs tens of metres of hot plume over a kilometre-scale link.

## Flames

Real flame attenuation comes from potassium ionized in the flame (about 1e16 electrons per cubic metre in pine litter flames). A clean butane or alcohol flame is ionized far less. A potassium-seeded flame, for example an alcohol burner with potassium chloride, is closer to vegetation fire, but an open flame at a booth needs the venue's permission, a fire blanket and a supervisor. Without that, use the hand, water and variance demonstrations and show the study figures for the flame physics.

## Honest caveats to tell visitors

- The study is simulation only. No real link has yet been observed crossing a wildfire.
- Commercial links are built to keep the Fresnel zone clear of terrain and trees. In the model, a fire usually changes the signal only where the link passes low over a ridge, and mostly through scintillation from the hot plume.
