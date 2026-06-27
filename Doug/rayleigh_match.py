#!/usr/bin/env python3
"""
rayleigh_match.py — run a Rayleigh match on Doug's Arduino anomaloscope.

Talks to anomaloscope_leonardo.ino over USB serial. Two modes:

  adjust  — free method-of-adjustment: the subject turns the knobs (keys) until
            the red/green field matches the yellow, then locks it. Good for
            warm-up and for finding a subject's center match.

  limits  — method of LIMITS (the tetrachromacy protocol): the program steps the
            red/green mixture and the subject only judges match / too-red /
            too-green. It brackets both edges of the MATCHING RANGE, several
            reps, and reports midpoint + range. The range width is the signal:
            a true tetrachromat accepts a NARROWER band than a trichromat.

Everything logs to a per-session CSV. Only dependency: pyserial.
    ~/venv/bin/pip install pyserial
    ~/venv/bin/python rayleigh_match.py --subject S01 limits

Color math (red/green mixture + per-channel calibration) lives HERE now, not in
the firmware. The firmware is a dumb actuator; tune the CALIBRATION block below,
or run `calibrate` to set the green gain by eye:
    ~/venv/bin/python rayleigh_match.py calibrate

Serial protocol (firmware side, each command + newline):
    R<0-255>   set red level
    G<0-255>   set green level
    Y<0-255>   set yellow level
    ?          -> "STATE,<r>,<g>,<y>"
"""
import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed:  ~/venv/bin/pip install pyserial")

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# ---- tunables -------------------------------------------------------------
START_YLUM = 90          # initial yellow level each presentation
STEP = 0.02              # R/G ratio step for the limits search (firmware res = 0.001)
REPS = 2                 # reps per edge, alternating approach direction
OUTSIDE = 0.30           # how far past center to start an "approach from outside" run
YLUM_STEP = 8            # yellow nudge per keypress

# ---- LED calibration (Python owns the color math now) ---------------------
# The green channel is over-bright (100R vs the red's 150R, plus a more efficient
# green die), so it dominates a linear mix. Attenuate it here. Tune by eye with:
#     ~/venv/bin/python rayleigh_match.py calibrate
R_GAIN    = 1.00         # red channel gain
G_GAIN    = 0.45         # green channel gain (start low; adjust in `calibrate`)
RGB_SCALE = 130          # overall RGB ceiling, kept matchable to the yellow LED
GAMMA     = 1.00         # per-channel gamma (1.0 = linear)


def mix_levels(ratio):
    """R/G ratio (0 = all green, 1 = all red) -> calibrated (R, G) PWM, 0..255."""
    rf = max(0.0, min(1.0, ratio))
    gf = 1.0 - rf
    if GAMMA != 1.0:
        rf, gf = rf ** GAMMA, gf ** GAMMA
    R = int(round(rf * R_GAIN * RGB_SCALE))
    G = int(round(gf * G_GAIN * RGB_SCALE))
    return max(0, min(255, R)), max(0, min(255, G))


# ---- single-keypress input (macOS / Linux) --------------------------------
def getch():
    import termios, tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


# ---- serial link to the firmware ------------------------------------------
class Scope:
    def __init__(self, port, baud=9600):
        self.ser = serial.Serial(port, baud, timeout=0.4)
        time.sleep(1.5)                 # Leonardo settle
        self.ser.reset_input_buffer()
        self.ratio = 0.25
        self.ylum = START_YLUM

    def _send(self, line):
        self.ser.write((line + "\n").encode())
        self.ser.flush()

    def _drain(self):
        # firmware echoes STATE,<r>,<g>,<y> after each command; consume the latest
        deadline = time.time() + 0.4
        while time.time() < deadline:
            if self.ser.readline().decode(errors="ignore").startswith("STATE,"):
                break

    def set_levels(self, R, G, Y=None):
        """Push raw channel levels straight to the firmware."""
        self._send(f"R{int(R)}")
        self._send(f"G{int(G)}")
        if Y is not None:
            self._send(f"Y{int(Y)}")
        self._drain()

    def set_ratio(self, r):
        self.ratio = max(0.0, min(1.0, r))
        R, G = mix_levels(self.ratio)
        self.set_levels(R, G, self.ylum)

    def set_ylum(self, y):
        self.ylum = max(0, min(255, int(y)))
        R, G = mix_levels(self.ratio)
        self.set_levels(R, G, self.ylum)

    def close(self):
        try:
            self.set_ylum(0)
            self.ser.close()
        except Exception:
            pass


def find_port(explicit):
    if explicit:
        return explicit
    cands = []
    for p in list_ports.comports():
        blob = f"{p.device} {p.description} {p.manufacturer}".lower()
        if "usbmodem" in p.device.lower() or "arduino" in blob or "leonardo" in blob:
            cands.append(p.device)
    if not cands:
        sys.exit("no Arduino found. Plug in the Leonardo, or pass --port /dev/cu.usbmodemXXXX\n"
                 "list ports:  ~/venv/bin/python -m serial.tools.list_ports -v")
    if len(cands) > 1:
        print(f"multiple ports {cands}; using {cands[0]} (override with --port)")
    return cands[0]


# ---- CSV logging ----------------------------------------------------------
class Log:
    def __init__(self, subject):
        DATA.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = DATA / f"rayleigh_{subject}_{stamp}.csv"
        self.f = self.path.open("w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(["timestamp", "subject", "mode", "phase", "direction",
                         "rep", "rg_ratio", "ylum", "response", "note"])
        self.subject = subject

    def row(self, **k):
        self.w.writerow([datetime.now().isoformat(timespec="seconds"), self.subject,
                         k.get("mode", ""), k.get("phase", ""), k.get("direction", ""),
                         k.get("rep", ""), k.get("rg_ratio", ""), k.get("ylum", ""),
                         k.get("response", ""), k.get("note", "")])
        self.f.flush()

    def close(self):
        self.f.close()


# ---- one judged presentation: subject tweaks yellow, then judges ----------
def present(scope, prompt):
    """Show the current field; let the subject adjust yellow (w/s) and judge.
    Returns one of: 'm' (match), 'r' (too red), 'g' (too green), 'q' (quit)."""
    print(prompt)
    print("   w/s = yellow brighter/dimmer   m = matches   r = too red   "
          "g = too green   q = quit")
    while True:
        c = getch().lower()
        if c == "w":
            scope.set_ylum(scope.ylum + YLUM_STEP); print(f"   yellow {scope.ylum}")
        elif c == "s":
            scope.set_ylum(scope.ylum - YLUM_STEP); print(f"   yellow {scope.ylum}")
        elif c in ("m", "r", "g", "q"):
            return c
        # ignore anything else


# ---- ADJUST mode ----------------------------------------------------------
def mode_adjust(scope, log):
    print("\n=== ADJUST: turn the field until it matches the yellow, then lock ===")
    print("a/d = redder/greener   w/s = yellow brighter/dimmer   "
          "RET = lock this match   n = new start   q = done\n")
    scope.set_ratio(0.25); scope.set_ylum(START_YLUM)
    while True:
        sys.stdout.write(f"\r  R/G={scope.ratio:.3f}  Y={scope.ylum}      ")
        sys.stdout.flush()
        c = getch().lower()
        if c == "a":
            scope.set_ratio(scope.ratio - 0.02)
        elif c == "d":
            scope.set_ratio(scope.ratio + 0.02)
        elif c == "w":
            scope.set_ylum(scope.ylum + YLUM_STEP)
        elif c == "s":
            scope.set_ylum(scope.ylum - YLUM_STEP)
        elif c in ("\r", "\n", " "):
            log.row(mode="adjust", phase="match", rg_ratio=f"{scope.ratio:.3f}",
                    ylum=scope.ylum, response="locked")
            print(f"\n  locked: R/G={scope.ratio:.3f}  Y={scope.ylum}\n")
        elif c == "n":
            scope.set_ratio(0.25); scope.set_ylum(START_YLUM)
        elif c == "q":
            print()
            return


# ---- LIMITS mode: bracket one edge -----------------------------------------
def find_edge(scope, log, edge, center, direction, rep):
    """Step from `center` toward `edge` ('red' or 'green') until the judgment
    crosses out of 'match'. `direction` 'out' starts at center stepping toward the
    edge; 'in' starts outside and steps back toward center. Returns the ratio at
    the transition, or None if no crossing."""
    sign = +1 if edge == "red" else -1        # red = higher ratio, green = lower
    boundary = "r" if edge == "red" else "g"
    if direction == "out":
        ratio = center
        step = sign * STEP
    else:  # approach from outside
        ratio = max(0.0, min(1.0, center + sign * OUTSIDE))
        step = -sign * STEP

    prev_ratio, prev_resp = None, None
    while 0.0 <= ratio <= 1.0:
        scope.set_ratio(ratio); scope.set_ylum(START_YLUM)
        resp = present(scope, f"\n[{edge} edge, rep {rep}, {direction}]  R/G={scope.ratio:.3f}")
        log.row(mode="limits", phase=f"{edge}_edge", direction=direction, rep=rep,
                rg_ratio=f"{scope.ratio:.3f}", ylum=scope.ylum, response=resp)
        if resp == "q":
            return None
        # crossing detection
        if direction == "out" and resp == boundary and prev_resp == "m":
            return (ratio + prev_ratio) / 2.0       # left match -> hit boundary
        if direction == "in" and resp == "m" and prev_resp in (boundary, None):
            return (ratio + prev_ratio) / 2.0 if prev_ratio is not None else ratio
        prev_ratio, prev_resp = ratio, resp
        ratio += step
    return None


def mode_limits(scope, log):
    print("\n=== LIMITS: find the matching range ===")
    print("First set a comfortable center match (adjust), then the program will "
          "step toward each edge.\n")
    # 1) quick center via adjustment
    scope.set_ratio(0.30); scope.set_ylum(START_YLUM)
    print("Center match — a/d redder/greener, w/s yellow, RET when it matches:")
    while True:
        sys.stdout.write(f"\r  R/G={scope.ratio:.3f}  Y={scope.ylum}      ")
        sys.stdout.flush()
        c = getch().lower()
        if c == "a": scope.set_ratio(scope.ratio - 0.02)
        elif c == "d": scope.set_ratio(scope.ratio + 0.02)
        elif c == "w": scope.set_ylum(scope.ylum + YLUM_STEP)
        elif c == "s": scope.set_ylum(scope.ylum - YLUM_STEP)
        elif c in ("\r", "\n", " "): break
        elif c == "q": return
    center = scope.ratio
    log.row(mode="limits", phase="center", rg_ratio=f"{center:.3f}",
            ylum=scope.ylum, response="locked")
    print(f"\n  center R/G = {center:.3f}\n")

    reds, greens = [], []
    for rep in range(1, REPS + 1):
        for edge, bucket in (("red", reds), ("green", greens)):
            direction = "out" if rep % 2 else "in"
            e = find_edge(scope, log, edge, center, direction, rep)
            if e is None:
                print(f"  ({edge} edge rep {rep}: no crossing / quit)")
            else:
                bucket.append(e)
                print(f"  {edge} edge rep {rep} ({direction}): {e:.3f}")

    summarize(log, center, reds, greens)


def summarize(log, center, reds, greens):
    def ms(xs):
        if not xs:
            return None, None
        m = sum(xs) / len(xs)
        sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
        return m, sd

    rm, rsd = ms(reds)
    gm, gsd = ms(greens)
    print("\n" + "=" * 56 + "\nRESULT")
    print(f"  center match     R/G = {center:.3f}")
    if rm is not None:
        print(f"  red edge         R/G = {rm:.3f}  (sd {rsd:.3f}, n={len(reds)})")
    if gm is not None:
        print(f"  green edge       R/G = {gm:.3f}  (sd {gsd:.3f}, n={len(greens)})")
    if rm is not None and gm is not None:
        mid = (rm + gm) / 2
        width = rm - gm
        print(f"  matching midpt   R/G = {mid:.3f}")
        print(f"  MATCHING RANGE   width = {width:.3f}  "
              f"(narrow => fewer mixtures accepted; the tetrachromacy signal)")
        log.row(mode="limits", phase="summary",
                rg_ratio=f"{mid:.3f}", note=f"red={rm:.3f};green={gm:.3f};width={width:.3f}")
    print("=" * 56)
    print(f"\nlogged to {log.path}")


# ---- CALIBRATE mode: balance the LEDs by eye -------------------------------
def mode_calibrate(scope):
    """Two calibrations: (1) red vs green brightness -> G_GAIN; (2) the RGB mix's
    overall brightness vs the dimmer yellow -> RGB_SCALE. Prints values to bake in."""
    global G_GAIN, RGB_SCALE
    print("\n=== CALIBRATE ===")
    print("  red vs green:  1 = red only   2 = green only      j/k = green gain down/up")
    print("  vs yellow:     4 = mix + yellow                   [ / ] = RGB level down/up")
    print("                                                    w/s = yellow ref up/down")
    print("  3 = mix only (no yellow)     q = done\n")
    print("  step 1 — flip 1<->2, set j/k until red and green are equally bright")
    print("  step 2 — view 4, press [ to dim the RGB mix until it matches the yellow\n")
    view = "1"; yref = 200

    def show():
        if   view == "1": R, G, Y = int(R_GAIN * RGB_SCALE), 0, 0
        elif view == "2": R, G, Y = 0, int(G_GAIN * RGB_SCALE), 0
        elif view == "4": (R, G), Y = mix_levels(0.5), yref
        else:             (R, G), Y = mix_levels(0.5), 0
        scope.set_levels(R, G, Y)
        sys.stdout.write(f"\r  view {view}   G_GAIN={G_GAIN:.2f}   RGB_SCALE={RGB_SCALE}   "
                         f"yellow={Y}   (R={R} G={G})        ")
        sys.stdout.flush()

    show()
    while True:
        c = getch().lower()
        if c in ("1", "2", "3", "4"):  view = c
        elif c == "k":                 G_GAIN = min(2.0, G_GAIN + 0.02)
        elif c == "j":                 G_GAIN = max(0.0, G_GAIN - 0.02)
        elif c == "]":                 RGB_SCALE = min(255, RGB_SCALE + 5)
        elif c == "[":                 RGB_SCALE = max(5, RGB_SCALE - 5)
        elif c == "w":                 yref = min(255, yref + 8)
        elif c == "s":                 yref = max(0, yref - 8)
        elif c == "q":                 break
        else:                          continue
        show()
    scope.set_levels(0, 0, 0)
    print("\n\n  bake these into the CALIBRATION block:\n"
          f"    G_GAIN    = {G_GAIN:.2f}\n"
          f"    RGB_SCALE = {RGB_SCALE}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["adjust", "limits", "calibrate"])
    ap.add_argument("--subject", default="anon")
    ap.add_argument("--port", default=None, help="serial port (auto-detect if omitted)")
    args = ap.parse_args()

    port = find_port(args.port)
    print(f"connecting to {port} ...")
    scope = Scope(port)
    log = None
    try:
        if args.mode == "calibrate":
            mode_calibrate(scope)
        else:
            log = Log(args.subject)
            scope.set_ratio(0.25); scope.set_ylum(START_YLUM)
            (mode_adjust if args.mode == "adjust" else mode_limits)(scope, log)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        scope.close()
        if log:
            log.close()


if __name__ == "__main__":
    main()
