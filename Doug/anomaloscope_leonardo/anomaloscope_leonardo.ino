/*
 * anomaloscope_leonardo.ino — Rayleigh-match firmware for Doug's build.
 *
 * This is a DUMB ACTUATOR: it just holds three LED channels at the levels it is
 * told. All the color math (the red/green mixture, per-channel calibration,
 * gamma) now lives in the Python harness (rayleigh_match.py), so it can be tuned
 * in seconds without reflashing. There is NO software flicker/strobe here — the
 * field is steady, which is what the Rayleigh match wants.
 *
 * Board:    Arduino Leonardo (native USB; enumerates as /dev/cu.usbmodemXXXX).
 * Wiring:   COMMON-ANODE LEDs (anode -> +5V, cathode -> resistor -> pin), so the
 *           pins SINK current and PWM is ACTIVE-LOW: pin LOW = bright, HIGH = off.
 *           Every analogWrite is therefore inverted (255 - value).
 *
 *   Yellow LED : anode +5V, cathode -> 100R -> D9   (~30 mA; brightened to match the RGB)
 *   RGB LED    : common anode +5V
 *                red   cathode -> 150R -> D6
 *                green cathode -> 100R -> D5   (brighter: lower R + efficient die)
 *                blue  cathode -> 100R -> D3   (unused in the Rayleigh match)
 *
 * Serial protocol (9600 baud; each command terminated by newline):
 *     R<0-255>   set red level
 *     G<0-255>   set green level
 *     Y<0-255>   set yellow level
 *     ?          report state
 *   State line (parseable):  STATE,<r>,<g>,<y>     (each 0..255, intended brightness)
 *
 * If a channel behaves backwards after upload, this build assumed common-anode;
 * for common-cathode LEDs remove the inversion in writeChannel().
 */

const uint8_t R_pin = 6;
const uint8_t G_pin = 5;
const uint8_t B_pin = 3;   // present on the RGB LED but not used for the match
const uint8_t Y_pin = 9;

int r_level = 0;
int g_level = 0;
int y_level = 0;

// ACTIVE-LOW write: `value` is intended brightness (0..255), pin is inverted.
void writeChannel(uint8_t pin, int value) {
  if (value < 0)   value = 0;
  if (value > 255) value = 255;
  analogWrite(pin, 255 - value);          // common-anode: invert. (Common-cathode: drop the 255-.)
}

void apply() {
  writeChannel(R_pin, r_level);
  writeChannel(G_pin, g_level);
  writeChannel(B_pin, 0);
  writeChannel(Y_pin, y_level);
}

void printState() {
  Serial.print("STATE,");
  Serial.print(r_level); Serial.print(",");
  Serial.print(g_level); Serial.print(",");
  Serial.println(y_level);
}

void setup() {
  pinMode(R_pin, OUTPUT);
  pinMode(G_pin, OUTPUT);
  pinMode(B_pin, OUTPUT);
  pinMode(Y_pin, OUTPUT);
  Serial.begin(9600);       // baud ignored on Leonardo native USB, harmless
  apply();                  // start dark
}

// read one integer argument after a command letter (until newline / non-digit)
long readArg() {
  long v = 0; bool any = false;
  unsigned long t0 = millis();
  while (true) {
    if (Serial.available() == 0) {
      if (millis() - t0 > 50) break;       // don't busy-wait forever
      continue;
    }
    int c = Serial.peek();
    if (c >= '0' && c <= '9') { v = v * 10 + (Serial.read() - '0'); any = true; }
    else { if (c == '\r' || c == '\n') Serial.read(); break; }
  }
  return any ? v : -1;
}

void handle(char c) {
  switch (c) {
    case 'R': { long v = readArg(); if (v >= 0) r_level = (int)v; apply(); printState(); break; }
    case 'G': { long v = readArg(); if (v >= 0) g_level = (int)v; apply(); printState(); break; }
    case 'Y': { long v = readArg(); if (v >= 0) y_level = (int)v; apply(); printState(); break; }
    case '?': printState(); break;
    default:  break;
  }
}

void loop() {
  // The field is held steady by the hardware PWM; we only service serial.
  if (Serial.available() > 0) {
    int d = Serial.read();
    if (d >= 0 && d <= 127) handle((char)d);
  }
}
