# Doug's anomaloscope — firmware + Python harness

Custom layer over the BrainardLab Penn Anomaloscope for testing tetrachromats
**without MATLAB**. The firmware is a dumb actuator; Python (and, soon, a Web
Serial browser UI) owns the color math, calibration, and logging.

## Hardware (this build)

- **Board:** Arduino Leonardo (native USB-C).
- **LEDs: common-anode / active-low** — anode to +5V, cathode through a resistor
  to the pin, so a pin pulled **LOW** lights the LED. PWM is inverted in firmware.

| LED        | resistor | pin |
|------------|----------|-----|
| Yellow     | 100 Ω    | D9  |
| RGB red    | 150 Ω    | D6  |
| RGB green  | 100 Ω    | D5  |
| RGB blue   | 100 Ω    | D3  (unused in the match) |

**Brightness:** the yellow is on **100 Ω** (~30 mA) so it matches the RGB channels
(green 100 Ω ≈ 28 mA, red 150 Ω ≈ 21 mA). It started at 330 Ω, which starved it far
below the RGB — and PWM can only *attenuate*, never push a LED past full-on, so the
dim yellow was a hardware fix, not a software one. Note: 30 mA is above a standard
5 mm LED's ~20 mA continuous rating — fine for intermittent test use, but cap the
yellow in software (max ~200) or use 150 Ω if you'll run it bright for long
stretches. After the swap, re-run `calibrate` and raise `RGB_SCALE` to the now
brighter yellow. See *Calibration*.

## 1. Firmware — `anomaloscope_leonardo.ino`

A **dumb actuator**: it holds three LED channels at the levels it's told, steady
field, no flicker. All color math lives upstream. Upload with the Arduino IDE
(Board: Arduino Leonardo). Serial, 9600 baud, newline line-ending:

- `R<0-255>` set red · `G<0-255>` set green · `Y<0-255>` set yellow · `?` report
- State echo: `STATE,<r>,<g>,<y>` (each 0–255, intended brightness)

Polarity check after upload: `Y200` should **light** the yellow. If a channel is
inverted, the LEDs are common-cathode — remove the `255 -` in `writeChannel()`
and re-upload.

## 2. Harness — `rayleigh_match.py`

```sh
~/venv/bin/pip install pyserial                            # one-time
~/venv/bin/python rayleigh_match.py calibrate              # FIRST — balance the LEDs
~/venv/bin/python rayleigh_match.py --subject S01 adjust   # warm-up
~/venv/bin/python rayleigh_match.py --subject S01 limits   # the real protocol
```

Auto-detects the Leonardo (override with `--port /dev/cu.usbmodemXXXX`).

- **calibrate** — balance the LEDs by eye and bake the result into the CALIBRATION
  block. Run this first (see *Calibration*).
- **adjust** — subject turns the field to a match and locks it (method of
  adjustment). Practice + finding a subject's center.
- **limits** — method of limits: the program steps the red/green mixture toward
  each edge; the subject judges *matches / too red / too green* (nudging yellow
  with `w`/`s`). Brackets both edges over reps; reports **midpoint + matching
  range**.

### Why the range, not the midpoint

A normal trichromat accepts a wide band of red/green mixtures as "the same
yellow." A genuine tetrachromat's fourth cone breaks that metamer, so they accept
a **narrower** band (or reject a match a trichromat is happy with). The **range
width** is the tetrachromacy signal; the midpoint mostly indexes red/green
anomaly. Run several subjects with known status to calibrate what "narrow" means
on this device.

## 3. Calibration

Two independent problems, both handled in software (Python owns the color math;
the firmware only actuates):

**(a) Red vs green balance → `G_GAIN`.** Green is over-bright (100 Ω vs the red's
150 Ω, plus a more efficient die), so a linear mix is swamped by green.
`mix_levels()` attenuates green by `G_GAIN`. Run `calibrate`, flip **1** (red
only) / **2** (green only), and use `j`/`k` until red and green look equally
bright. Paste the printed value into the CALIBRATION block.

**(b) RGB mix vs yellow brightness → `RGB_SCALE` (+ resistor + filter).** The
yellow is much dimmer than the RGB, so the mix has to be brought down to meet it.
In `calibrate`, view **4** shows the 50/50 mix with the yellow on; press `[` to
dim `RGB_SCALE` until they match (`w`/`s` adjusts the yellow reference). If the
yellow still can't keep up, brighten it in hardware (yellow resistor 330 → 150 Ω).
The color filter (below) also narrows this gap, since it cuts the RGB more than
the yellow.

Always **calibrate with the filter + diffuser in the optical path** — they change
the numbers.

**Free spectral check (a DVD scrap).** A DVD is a ~1350 lines/mm diffraction
grating: view the lit device through a piece and the RGB splits into separate
red/green bands (the yellow stays one band). Use it to balance the bands by eye
(→ `G_GAIN`) and to confirm the orange filter drops the green band below the red.
Tell: a matched *mix* shows two bands while the real yellow shows one — the
metamer pulled apart. For peak wavelengths, photograph and measure (the
spectral-calibration path).

## 4. Color filter (required for a real match)

A bare-LED match doesn't work: the LEDs are too broadband and green dominates. The
fix, from the Penn build, is an **orange long-pass gel over both fields**, plus a
**diffuser** (Scotch tape over the LEDs) to mix red + green into one field. The
filter:

1. cuts blue and the short side of green, confining all channels to the long-wave
   band where red + green is metameric to yellow (the Rayleigh condition);
2. attenuates the 546 nm green relative to the 670 nm red, so the channels balance;
3. passes the 589 nm yellow and 670 nm red nearly intact.

**The one thing that matters is the cut-on wavelength: it must fall between the
green (546) and the yellow (589), roughly 560–575 nm.** Check any candidate by its
published transmission curve at 546 / 589 / 670 — green low, yellow and red high.

| filter | notes |
|---|---|
| **Rosco Roscolux #23** (orange) | Penn default; won Dana Turner's spectral bake-off for balanced R/G |
| **Kodak/Tiffen Wratten 23A** (light red) | cut-on ~560; closest Kodak equivalent |
| **Wratten 22 / 21** (orange) | shorter cut-on → more green through → use a lower `G_GAIN` |
| **Lee 780 Golden Amber** | cut-on ~565, deep orange; verified by curve |
| *avoid* Wratten 24/25, Rosco #24 (red) | cut-on too long — eats the yellow, collapses the green side |
| *avoid* Wratten 85, yellow gels | wrong shape — won't cut the green |

The filter and `G_GAIN` do the same job (tame green), so a lighter filter just
means a lower `G_GAIN`.

## 5. Data

Each session writes `data/rayleigh_<subject>_<timestamp>.csv` — one row per judged
presentation plus a summary row (raw enough to re-analyze the edges yourself).
`data/` is gitignored.

## Tunables (top of `rayleigh_match.py`)

- **Calibration:** `R_GAIN`, `G_GAIN`, `RGB_SCALE`, `GAMMA` (set via `calibrate`).
- **Protocol:** `STEP` (ratio step, 0.02), `REPS` (per edge, 2), `OUTSIDE`,
  `START_YLUM`, `YLUM_STEP`.

## Not done yet / caveats

- **Eye-calibrated, not spectrally calibrated.** `calibrate` balances by eye; for
  publishable numbers, measure the LED spectra *through the filter* with a
  spectrometer. `PlotRayleighMeas.m` and the upstream `ICVS2025/` MATLAB are
  reference only (their devices); `.mat` files read in Python via
  `scipy.io.loadmat`.
- **Front end (planned):** a Web Serial browser UI that talks to the Leonardo
  directly — no Python, no Electron, no server (Chrome/Edge, served over
  https/localhost). The Python harness stays for headless runs and CSV analysis.
