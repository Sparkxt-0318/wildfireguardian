// Booth demo transmitter: broadcasts a small ESP-NOW packet every 20 ms at fixed power.
// Board: any ESP32 dev board. Tested API: Arduino-ESP32 core 3.x (ESP-IDF 5).
// Not tested on hardware in this repository; see demo/README.md.
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

static const uint8_t kChannel = 6;                   // keep both boards on the same channel
static const uint8_t kBroadcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static uint32_t seq = 0;

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_channel(kChannel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_max_tx_power(40);                     // units of 0.25 dBm: 40 -> 10 dBm, fixed (no power control)
  if (esp_now_init() != ESP_OK) { Serial.println("esp_now_init failed"); while (true) delay(1000); }
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, kBroadcast, 6);
  peer.channel = kChannel;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
}

void loop() {
  seq++;
  esp_now_send(kBroadcast, reinterpret_cast<uint8_t*>(&seq), sizeof(seq));
  delay(20);
}
