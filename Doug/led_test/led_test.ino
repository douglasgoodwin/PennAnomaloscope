/*
 * led_test.ino — bring-up diagnostic for the anomaloscope shield.
 *
 * Walks each channel one at a time, full on for 1 s, and prints which pin it is
 * driving (open Serial Monitor at 9600). Runs on boot, no input needed.
 *
 * Use it to confirm wiring per-pin BEFORE running the real firmware.
 *
 * POLARITY: this build is common-anode (active-low) -> ACTIVE_LOW 1.
 * If every LED is ON when it should be off and vice-versa, set ACTIVE_LOW 0
 * and re-upload. (That would mean the LEDs are actually common-cathode.)
 */
#define ACTIVE_LOW 1

const uint8_t R_pin = 6;
const uint8_t G_pin = 5;
const uint8_t B_pin = 3;
const uint8_t Y_pin = 9;

const uint8_t pins[4]  = {R_pin, G_pin, B_pin, Y_pin};
const char*   names[4] = {"RED (D6)", "GREEN (D5)", "BLUE (D3)", "YELLOW (D9)"};

void writeChannel(uint8_t pin, int value) {       // value = intended brightness 0..255
#if ACTIVE_LOW
  analogWrite(pin, 255 - value);
#else
  analogWrite(pin, value);
#endif
}

void allOff() {
  for (int i = 0; i < 4; i++) writeChannel(pins[i], 0);
}

void setup() {
  for (int i = 0; i < 4; i++) pinMode(pins[i], OUTPUT);
  Serial.begin(9600);
  allOff();
}

void loop() {
  for (int i = 0; i < 4; i++) {
    allOff();
    writeChannel(pins[i], 255);                   // full on
    Serial.print("ON: "); Serial.println(names[i]);
    delay(1000);
  }
  allOff();
  Serial.println("--- all off (1s) ---");
  delay(1000);
}
