// Booth demo receiver: prints "millis,seq,rssi_dBm" for every packet from the transmitter.
// Board: any ESP32 dev board. Tested API: Arduino-ESP32 core 3.x (ESP-IDF 5).
// Not tested on hardware in this repository; see demo/README.md.
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

static const uint8_t kChannel = 6;

void onRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(uint32_t)) return;
  uint32_t seq;
  memcpy(&seq, data, sizeof(seq));
  Serial.printf("%lu,%lu,%d\n", (unsigned long)millis(), (unsigned long)seq, info->rx_ctrl->rssi);
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_channel(kChannel, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK) { Serial.println("esp_now_init failed"); while (true) delay(1000); }
  esp_now_register_recv_cb(onRecv);
}

void loop() { delay(1000); }
