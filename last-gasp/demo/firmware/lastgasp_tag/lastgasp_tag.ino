// Last Gasp booth tag: broadcasts a BLE heartbeat advertisement every HEARTBEAT_MS.
// Format: see ../../lastgasp_demo/protocol.py (13-byte manufacturer data, company ID 0xFFFF for testing).
//
// UNTESTED: written to the documented format but not compiled or run on hardware in this session.
// Target: ESP32 / ESP32-C3 with the Arduino-ESP32 core (BLEDevice library).
// Set NODE_ID per board (1..25 for the booth map) before flashing.

#include <BLEDevice.h>
#include <BLEAdvertising.h>

#define NODE_ID 7
#define HEARTBEAT_MS 1000   // booth: 1 s. Field units would use 30 s or more.

static uint16_t seq = 0;
BLEAdvertising *adv;

static void put16(uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }

void setup() {
  BLEDevice::init("LG");
  adv = BLEDevice::getAdvertising();
}

void loop() {
  uint8_t m[13];
  put16(m + 0, 0xFFFF);          // company_id (testing)
  m[2] = 'L'; m[3] = 'G';        // magic
  m[4] = 1;                      // version
  put16(m + 5, NODE_ID);         // node_id
  put16(m + 7, ++seq);           // seq
  uint16_t mv = 3000;            // replace with a battery ADC reading
  put16(m + 9, mv);              // battery_mv
  int8_t t = (int8_t) temperatureRead();  // ESP32 internal sensor, approximate
  m[11] = (uint8_t) t;           // temp_c
  m[12] = (t > 60) ? 0x04 : 0x00;  // flags: bit2 over-temperature

  BLEAdvertisementData data;
  data.setFlags(0x06);
  data.setManufacturerData(String((char *) m, sizeof(m)));
  adv->stop();
  adv->setAdvertisementData(data);
  adv->start();
  delay(HEARTBEAT_MS);
}
