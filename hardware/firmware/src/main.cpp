// WildfireGuardian field route logger - main firmware (Arduino-ESP32 2.0.17 via PlatformIO espressif32 6.9.0).
// Board-specific values live ONLY in include/board_*.h. Logging/storage/export logic lives in lib/wfg_core
// (hardware independent, host-tested).
//
// Button (single PRG/USER button on GPIO0; see README "Button and boot-strap behaviour"):
//   IDLE       short          : wake screen; if already awake: cycle movement mode WALK -> VEHICLE -> UNKNOWN
//              hold >= 2.5 s  : start recording (countdown shown); release between 2.5 and 6 s
//              hold >= 6 s    : enter Wi-Fi export mode
//              hold >= 2.5 s while a delete is pending: confirm that delete instead
//   RECORDING  short          : event marker (also when the screen is off)
//              hold >= 2.5 s  : stop recording
//   EXPORT     hold >= 2.5 s  : confirm a pending delete (requested by phone page or USB)
//              hold >= 6 s    : leave export mode (Wi-Fi off)
//   FULL       same as IDLE, but start is refused until sessions are exported and deleted
#include <Arduino.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <SPI.h>
#include <esp_partition.h>
#include "board.h"
#include "display.h"
#include "web_export.h"
#include "wfg_button.h"
#include "wfg_export.h"
#include "wfg_logger.h"
#include "wfg_nmea.h"
#include "wfg_proto.h"
#include "wfg_resume.h"
#include <esp_system.h>

using namespace wfg;

static const char* FS_MOUNT = "/littlefs";
static uint64_t fsTotal() { return LittleFS.totalBytes(); }
static uint64_t fsUsed() { return LittleFS.usedBytes(); }

static PosixStorage* g_st = nullptr;
static Logger* g_lg = nullptr;
static Proto* g_proto = nullptr;
static NmeaParser g_nmea;
static Button g_btn;
static Preferences g_prefs;
static LoggerConfig g_cfg;

static bool g_fs_ok = false;
static uint8_t g_mode = MODE_WALK;
static uint32_t g_device_id = 0;
static uint32_t g_last_input_ms = 0;
static uint32_t g_last_draw_ms = 0;
static uint32_t g_last_batt_ms = 0;
static int g_batt_mv = -1, g_batt_pct = -1;
static uint8_t g_low_batt_count = 0;
static GnssEpoch g_last_epoch;
static bool g_have_epoch = false;
static uint32_t g_last_epoch_ms = 0;
static char g_banner[40] = "";
static uint32_t g_banner_until = 0;
static uint16_t g_unexported = 0;
static uint16_t g_vbat_cal_x1000 = 1000;   // owner calibration (NVS "vcal"), 1000 = 1.000
static int g_vbat_pin_mv = -1;
static bool g_nvs_rec = false;             // NVS recording-intent flag currently set
static bool g_resumed_session = false;     // auto-resumed session still inside its 60 s loop-guard window
static bool g_cur_is_resumed = false;      // current session was auto-resumed (for the screen)
static uint32_t g_rec_started_ms = 0;
static uint8_t g_reset_reason = 0;
static uint32_t g_export_since = 0;
static uint32_t g_export_last_client_ms = 0;
static const uint32_t SCREEN_TIMEOUT_MS = 30000;
static const uint32_t EXPORT_IDLE_TIMEOUT_MS = 10 * 60 * 1000;

struct SerialSink : Sink {
  bool write(const char* s, size_t n) override { return Serial.write((const uint8_t*)s, n) == n; }
};
static SerialSink g_serial_sink;

static void banner(const char* msg, uint32_t ms = 4000) {
  strncpy(g_banner, msg, sizeof(g_banner) - 1);
  g_banner_until = millis() + ms;
  Serial.printf("# %s\n", msg);
}

// ---------------------------------------------------------------- hardware helpers
static void vext(bool on) {
  if (WFG_PIN_VEXT_CTRL >= 0) {
    pinMode(WFG_PIN_VEXT_CTRL, OUTPUT);
    digitalWrite(WFG_PIN_VEXT_CTRL, on ? WFG_VEXT_ON_LEVEL : !WFG_VEXT_ON_LEVEL);
  }
  if (WFG_PIN_GNSS_EN >= 0) {
    pinMode(WFG_PIN_GNSS_EN, OUTPUT);
    digitalWrite(WFG_PIN_GNSS_EN, on ? WFG_GNSS_EN_ON_LEVEL : !WFG_GNSS_EN_ON_LEVEL);
  }
}

static void loraSleep() {
#if WFG_HAS_LORA
  // The SX1262 is unused. Deselect it and send SetSleep(0x84, cold start) so it does not idle in STDBY_RC.
  // UNVERIFIED on hardware: current saving not measured.
  pinMode(WFG_PIN_LORA_CS, OUTPUT);
  digitalWrite(WFG_PIN_LORA_CS, HIGH);
  if (WFG_PIN_LORA_FEM_POWER >= 0) { pinMode(WFG_PIN_LORA_FEM_POWER, OUTPUT); digitalWrite(WFG_PIN_LORA_FEM_POWER, LOW); }
#ifdef WFG_PIN_LORA_BUSY
  pinMode(WFG_PIN_LORA_BUSY, INPUT);
  uint32_t t0 = millis();
  while (digitalRead(WFG_PIN_LORA_BUSY) == HIGH && millis() - t0 < 50) delay(1);
  SPIClass spi(FSPI);
  spi.begin(WFG_PIN_LORA_SCK, WFG_PIN_LORA_MISO, WFG_PIN_LORA_MOSI, -1);
  spi.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(WFG_PIN_LORA_CS, LOW);
  spi.transfer(0x84);
  spi.transfer(0x00);
  digitalWrite(WFG_PIN_LORA_CS, HIGH);
  spi.endTransaction();
  spi.end();
#endif
#endif
}

static int lipoPercent(int mv) {
  // Rough open-circuit LiPo curve (UNVERIFIED for the purchased cell; voltage under ~100 mA load reads lower).
  static const int16_t mvT[] = {3300, 3500, 3600, 3700, 3750, 3800, 3850, 3900, 4000, 4100, 4200};
  static const int8_t pcT[] = {0, 5, 10, 20, 30, 40, 50, 60, 75, 90, 100};
  if (mv <= mvT[0]) return 0;
  for (int i = 1; i < 11; i++)
    if (mv <= mvT[i]) return pcT[i - 1] + (pcT[i] - pcT[i - 1]) * (mv - mvT[i - 1]) / (mvT[i] - mvT[i - 1]);
  return 100;
}

static uint32_t vbatFactorX1000() { return (uint32_t)WFG_VBAT_DIVIDER_X1000 * g_vbat_cal_x1000 / 1000; }

static void readBattery() {
  if (WFG_PIN_VBAT_ADC < 0) { g_batt_mv = g_batt_pct = -1; return; }
  if (WFG_PIN_VBAT_ADC_CTRL >= 0) {
    if (WFG_VBAT_CTRL_USE_PULLUP) pinMode(WFG_PIN_VBAT_ADC_CTRL, INPUT_PULLUP);
    else { pinMode(WFG_PIN_VBAT_ADC_CTRL, OUTPUT); digitalWrite(WFG_PIN_VBAT_ADC_CTRL, HIGH); }
    delay(5);
  }
  uint32_t acc = 0;
  for (int i = 0; i < 8; i++) acc += analogReadMilliVolts(WFG_PIN_VBAT_ADC);
  if (WFG_PIN_VBAT_ADC_CTRL >= 0) {
    if (WFG_VBAT_CTRL_USE_PULLUP) pinMode(WFG_PIN_VBAT_ADC_CTRL, INPUT_PULLDOWN);
    else digitalWrite(WFG_PIN_VBAT_ADC_CTRL, LOW);
  }
  g_vbat_pin_mv = (int)(acc / 8);
  int mv = (int)((uint32_t)g_vbat_pin_mv * vbatFactorX1000() / 1000);
  if (mv < 2500 || mv > 4500) { g_batt_mv = mv; g_batt_pct = -1; return; }  // no battery / implausible
  g_batt_mv = mv;
  g_batt_pct = lipoPercent(mv);
}

static uint32_t deviceId() {
  uint64_t mac = ESP.getEfuseMac();
  return (uint32_t)(mac >> 16) ^ (uint32_t)(mac & 0xFFFF) << 16;
}

static bool partitionLooksErased() {
  const esp_partition_t* p =
      esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "spiffs");
  if (!p) return false;
  uint8_t buf[256];
  for (uint32_t off = 0; off < 8192; off += sizeof(buf)) {
    if (esp_partition_read(p, off, buf, sizeof(buf)) != ESP_OK) return false;
    for (uint8_t b : buf) if (b != 0xFF) return false;
  }
  return true;
}

static void countUnexported() {
  int u = g_lg->countUnexported();  // every session, no cap (review R4)
  g_unexported = (uint16_t)(u > 65535 ? 65535 : u);
}

// STATUS record source (battery + screen + GNSS flags); fs and NMEA counters are filled by the logger.
static bool statusSource(Status& t, void*) {
  t.vbat_factor_x1000 = (uint16_t)vbatFactorX1000();
  if (g_vbat_pin_mv >= 0) t.vbat_pin_mv = (uint16_t)g_vbat_pin_mv;
  if (g_batt_mv > 0) t.vbat_mv = (uint16_t)g_batt_mv;
  if (g_batt_pct >= 0) t.flags |= ST_BATT_VALID;
  if (display_is_on()) t.flags |= ST_SCREEN_ON;
  if (g_nmea.sentences_ok && millis() - g_nmea.last_sentence_mono_ms < 3000) t.flags |= ST_GNSS_SEEN;
  if (g_low_batt_count) t.flags |= ST_LOW_BATT_PENDING;
  t.free_heap = ESP.getFreeHeap();
  return true;
}

// ---- recording intent in NVS (review R3) ----
static void nvsSetRecording(uint8_t mode, uint32_t session_no) {
  g_prefs.putUChar("rec_mode", mode);
  g_prefs.putUInt("rec_sess", session_no);
  g_prefs.putBool("rec_on", true);
  g_nvs_rec = true;
  g_rec_started_ms = millis();
}
static void nvsClearRecording() {
  if (!g_nvs_rec) return;
  g_prefs.putBool("rec_on", false);
  g_nvs_rec = false;
}
static bool g_lg_session_resumed();
static bool startSession(uint8_t mode, uint32_t now, uint8_t reason, uint32_t resumed_from) {
  if (!g_lg->start(mode, now, reason, resumed_from, g_reset_reason)) return false;
  nvsSetRecording(mode, (uint32_t)atoi(g_lg->currentName() + 1));
  g_resumed_session = reason == START_AUTO_RESUMED_AFTER_RESET;
  if (!g_resumed_session) g_prefs.putUChar("rs_qf", 0);  // owner start resets the reboot-loop guard
  g_cur_is_resumed = g_resumed_session;
  return true;
}
static bool g_lg_session_resumed() { return g_cur_is_resumed; }

// ---------------------------------------------------------------- setup
void setup() {
  Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT
  Serial.setTxTimeoutMs(0);  // never block logging when no USB host is reading (native USB CDC only)
#endif
  setCpuFrequencyMhz(80);    // power: logging needs little CPU; Wi-Fi works at 80 MHz
  if (WFG_PIN_LED >= 0) { pinMode(WFG_PIN_LED, OUTPUT); digitalWrite(WFG_PIN_LED, LOW); }
  pinMode(WFG_PIN_BUTTON, INPUT_PULLUP);
  g_btn.begin(digitalRead(WFG_PIN_BUTTON) == (WFG_BUTTON_ACTIVE_LOW ? LOW : HIGH), millis());

  vext(true);  // GNSS + TFT power
  delay(50);
  if (WFG_PIN_GNSS_RST >= 0) {
    pinMode(WFG_PIN_GNSS_RST, OUTPUT);
    digitalWrite(WFG_PIN_GNSS_RST, !WFG_GNSS_RST_ACTIVE_LEVEL);  // release reset
  }
  Serial1.setRxBufferSize(4096);
  Serial1.begin(WFG_GNSS_BAUD, SERIAL_8N1, WFG_PIN_GNSS_RX, WFG_PIN_GNSS_TX);
  loraSleep();
  display_begin();

  g_device_id = deviceId();
  g_prefs.begin("wfg", false);
  g_mode = g_prefs.getUChar("mode", MODE_WALK);
  g_vbat_cal_x1000 = g_prefs.getUShort("vcal", 1000);
  if (g_vbat_cal_x1000 < 800 || g_vbat_cal_x1000 > 1200) g_vbat_cal_x1000 = 1000;
  g_reset_reason = (uint8_t)esp_reset_reason();
  if (g_mode > MODE_VEHICLE) g_mode = MODE_UNKNOWN;

  if (ESP.getFlashChipSize() < (uint32_t)WFG_FLASH_MB * 1024 * 1024) {
    // partitions.csv assumes 8 MB. A smaller chip would put the LittleFS partition past the end of flash.
    Serial.printf("# FLASH SIZE MISMATCH: chip reports %u bytes, board header expects %d MB\n",
                  (unsigned)ESP.getFlashChipSize(), WFG_FLASH_MB);
    banner("FLASH SIZE MISMATCH", 600000);
  }
  g_fs_ok = LittleFS.begin(false, FS_MOUNT, 10, "spiffs");
  if (!g_fs_ok && partitionLooksErased()) {
    Serial.println("# LittleFS partition is blank: formatting (no data to lose)");
    g_fs_ok = LittleFS.begin(true, FS_MOUNT, 10, "spiffs");
  }
  g_cfg.device_id = g_device_id;
  g_cfg.board_rev = WFG_BOARD_REV_CODE;
  g_cfg.fw_version = WFG_FW_VERSION;
  g_st = new PosixStorage(FS_MOUNT, 0, fsTotal, fsUsed);
  g_lg = new Logger(*g_st, g_cfg);
  g_proto = new Proto(*g_lg, *g_st, g_serial_sink, WFG_BOARD_NAME, g_device_id, WFG_FW_VERSION_STR);
  if (g_fs_ok) {
    RecoveryItem items[8];
    int n = g_lg->begin(items, 8);
    for (int i = 0; i < n && i < 8; i++)
      Serial.printf("# RECOVERED %s records=%u torn_bytes=%u closed=%d unrecoverable=%d\n", items[i].name,
                    (unsigned)items[i].valid_records, (unsigned)items[i].torn_bytes_removed, items[i].closed_now,
                    items[i].unrecoverable);
    if (n) { char b[40]; snprintf(b, sizeof(b), "RECOVERED %d session%s", n, n > 1 ? "s" : ""); banner(b, 8000); }
    countUnexported();
  }
  g_lg->setStatusSource(statusSource, nullptr);
  g_lg->tick(millis(), &g_nmea);
  readBattery();
  {
    ResumeNvs nv;
    nv.active = g_prefs.getBool("rec_on", false);
    nv.mode = g_prefs.getUChar("rec_mode", MODE_UNKNOWN);
    nv.session_no = g_prefs.getUInt("rec_sess", 0);
    nv.quick_fail_count = g_prefs.getUChar("rs_qf", 0);
    g_nvs_rec = nv.active;
    ResumeInputs in;
    in.fs_ok = g_fs_ok;
    in.storage_full = g_fs_ok && g_st->freeBytes() < g_cfg.reserve_bytes + 8192;
    in.batt_mv = g_batt_pct >= 0 ? g_batt_mv : -1;
    in.low_batt_mv = WFG_LOW_BATT_MV;
    ResumeAction a = decide_resume(nv, in);
    if (nv.active)
      Serial.printf("# RESUME decision %s (was S%06u mode %s, reset_reason %u, quick_fails %u)\n",
                    resume_action_name(a), (unsigned)nv.session_no, mode_name(nv.mode), g_reset_reason,
                    nv.quick_fail_count);
    if (a == RA_RESUME) {
      g_prefs.putUChar("rs_qf", nv.quick_fail_count + 1);
      if (startSession(nv.mode > MODE_VEHICLE ? MODE_UNKNOWN : nv.mode, millis(), START_AUTO_RESUMED_AFTER_RESET,
                       nv.session_no)) {
        g_mode = nv.mode;
        banner("AUTO-RESUMED after reset", 15000);
      } else {
        nvsClearRecording();
        banner("RESUME FAILED", 15000);
      }
    } else if (a == RA_GIVE_UP_LOOP) {
      nvsClearRecording();
      g_prefs.putUChar("rs_qf", 0);
      banner("RESET LOOP: not resuming", 30000);
    } else if (a == RA_BLOCKED_FULL || a == RA_BLOCKED_LOW_BATT) {
      nvsClearRecording();
      banner(a == RA_BLOCKED_FULL ? "FULL: not resuming" : "LOW BATT: not resuming", 15000);
    }
  }
  if (!g_fs_ok) {
    banner("FS ERROR: see README", 600000);
    Serial.println("# LittleFS mount failed and partition is not blank. Not formatting automatically.");
    Serial.println("# To erase ALL data: send 'FORMAT ERASE-ALL-SESSIONS' over USB.");
  }
  g_last_input_ms = millis();
  Serial.printf("# WFG logger fw %s board %s device %08X\n", WFG_FW_VERSION_STR, WFG_BOARD_NAME, (unsigned)g_device_id);
}

// ---------------------------------------------------------------- UI
static float hoursLeft() {
  uint64_t fr = g_st->freeBytes();
  uint64_t res = g_cfg.reserve_bytes;
  if (fr <= res) return 0;
  return (float)(fr - res) / (WFG_RECORD_SIZE * 3600.0f * 1000.0f / g_cfg.log_interval_ms);
}

static void draw(uint32_t now) {
  UiState u{};
  bool exporting = web_active();
  u.recording = g_lg->recording();
  if (!g_fs_ok) u.rec_state = "FS ERR";
  else if (exporting) u.rec_state = "EXPORT";
  else if (g_lg->state() == LS_FULL) u.rec_state = "FULL";
  else if (g_lg->state() == LS_ERROR) u.rec_state = "ERROR";
  else u.rec_state = u.recording ? "REC" : "IDLE";
  u.mode = mode_name(g_mode);
  u.gnss_seen = g_nmea.sentences_ok > 0 && now - g_nmea.last_sentence_mono_ms < 3000;
  bool fresh = g_have_epoch && now - g_last_epoch_ms < 3000;
  u.fix = fresh && g_last_epoch.pos_valid;
  u.fix_type = fresh && g_last_epoch.has_gsa ? g_last_epoch.fix_type : 0;
  u.sats = fresh && g_last_epoch.sats_valid ? g_last_epoch.sats : -1;
  u.hdop_x10 = fresh && g_last_epoch.hdop_valid ? g_last_epoch.hdop_x100 / 10 : -1;
  u.batt_pct = g_batt_pct;
  u.batt_mv = g_batt_mv;
  if (g_fs_ok) {
    u.fs_used_kb = (uint32_t)(g_st->usedBytes() / 1024);
    u.fs_total_kb = (uint32_t)(g_st->totalBytes() / 1024);
    u.hours_left = hoursLeft();
  }
  u.session_no = u.recording ? (uint32_t)atoi(g_lg->currentName() + 1) : 0;
  u.seq = g_lg->seq();
  u.last_event_no = g_lg->lastEventNo();
  u.last_event_located = g_lg->lastEventLocated();
  u.last_event_age_s = (now - g_lg->lastEventMono()) / 1000;
  u.unexported = g_unexported;
  u.resumed = u.recording && g_lg_session_resumed();
  static char l1[40], l2[40];
  if (exporting) {
    snprintf(l1, sizeof(l1), "%s", web_ssid());
    snprintf(l2, sizeof(l2), "pw %s %s", web_password(), web_ip());
    u.export_line1 = l1;
    u.export_line2 = l2;
  }
  static char hold[40];
  if (g_btn.isDown()) {
    uint32_t h = g_btn.holdMs(now);
    const ButtonConfig& c = g_btn.cfg();
    bool pend = g_proto->hasPendingDelete(now);
    if (u.recording) {
      if (h < c.long_ms) snprintf(hold, sizeof(hold), "hold %.1fs: STOP", (c.long_ms - h) / 1000.0f);
      else snprintf(hold, sizeof(hold), "release: STOP REC");
      u.hold_progress = h >= c.long_ms ? 100 : h * 100 / c.long_ms;
    } else if (h < 300) {
      hold[0] = 0;
    } else if (h < c.long_ms) {
      snprintf(hold, sizeof(hold), "hold %.1fs: %s", (c.long_ms - h) / 1000.0f,
               pend ? "DELETE" : exporting ? "-" : "START");
      u.hold_progress = h * 100 / c.long_ms;
    } else if (h < c.very_long_ms) {
      if (pend) snprintf(hold, sizeof(hold), "release: DELETE %.7s", g_proto->pendingDeleteName());
      else if (exporting) snprintf(hold, sizeof(hold), "hold %.1fs: EXIT EXPORT", (c.very_long_ms - h) / 1000.0f);
      else snprintf(hold, sizeof(hold), "release:START %.1fs:EXPORT", (c.very_long_ms - h) / 1000.0f);
      u.hold_progress = (h - c.long_ms) * 100 / (c.very_long_ms - c.long_ms);
    } else {
      snprintf(hold, sizeof(hold), exporting ? "release: EXIT EXPORT" : "release: EXPORT MODE");
      u.hold_progress = 100;
    }
    if (hold[0]) u.hold_text = hold;
  }
  if (!u.hold_text && g_banner[0] && (int32_t)(g_banner_until - now) > 0) u.banner = g_banner;
  else if (!u.hold_text && g_proto->hasPendingDelete(now)) {
    static char pb[40];
    snprintf(pb, sizeof(pb), "HOLD 2.5s TO DELETE %.7s", g_proto->pendingDeleteName());
    u.banner = pb;
  }
  display_draw(u);
}

static void wake(uint32_t now) {
  g_last_input_ms = now;
  display_power(true);
}

static void handleGesture(Gesture g, uint32_t now) {
  bool was_on = display_is_on();
  wake(now);
  if (!g_fs_ok) return;
  if (g_lg->recording()) {
    if (g == G_SHORT) {
      uint32_t down = g_btn.lastDownAt();
      if (g_lg->markEvent(down, (uint16_t)min<uint32_t>(g_btn.lastPressDuration(), 65535), now)) {
        char b[40];
        snprintf(b, sizeof(b), "EVENT %d %s", (int)g_lg->lastEventNo(), g_lg->lastEventLocated() ? "marked" : "(NO POSITION)");
        banner(b, 3000);
      }
    } else if (g == G_LONG || g == G_VERY_LONG) {  // emitted on RELEASE after a >= 2.5 s hold
      g_lg->stop(END_USER_STOP, now);
      nvsClearRecording();
      banner("STOPPED - saved", 4000);
      countUnexported();
    }
    return;
  }
  bool pend = g_proto->hasPendingDelete(now);
  if ((g == G_LONG || g == G_VERY_LONG) && pend) {
    g_proto->confirmPendingDelete(now);
    banner(g_proto->lastDeleteResult(), 5000);
    countUnexported();
    return;
  }
  if (web_active()) {
    if (g == G_VERY_LONG) { web_stop(); banner("Export mode OFF", 3000); countUnexported(); }
    return;
  }
  if (g == G_SHORT) {
    if (!was_on) return;  // first press only wakes the screen
    g_mode = g_mode == MODE_WALK ? MODE_VEHICLE : g_mode == MODE_VEHICLE ? MODE_UNKNOWN : MODE_WALK;
    g_prefs.putUChar("mode", g_mode);
    char b[40];
    snprintf(b, sizeof(b), "MODE: %s", mode_name(g_mode));
    banner(b, 2500);
  } else if (g == G_LONG) {
    if (g_lg->state() == LS_FULL) { banner("FULL: export+delete first", 5000); return; }
    if (startSession(g_mode, now, START_OWNER_BUTTON, 0)) {
      char b[40];
      snprintf(b, sizeof(b), "REC %s %s", g_lg->currentName(), mode_name(g_mode));
      banner(b, 3000);
    } else {
      banner(g_lg->state() == LS_FULL ? "FULL: cannot start" : "START FAILED", 5000);
    }
  } else if (g == G_VERY_LONG) {
    web_begin(g_lg, g_st, g_proto, g_device_id);
    g_export_since = g_export_last_client_ms = now;
    banner("Export mode ON", 3000);
  }
}

// ---------------------------------------------------------------- USB line input
static void handleSerial(uint32_t now) {
  static char line[200];
  static size_t len = 0;
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[len] = 0;
      len = 0;
      if (!strncmp(line, "FORMAT ERASE-ALL-SESSIONS", 25)) {
        if (g_lg->recording()) { Serial.println("ERR FORMAT recording-active"); continue; }
        Serial.println("# formatting LittleFS (all sessions erased by owner request)");
        LittleFS.end();
        g_fs_ok = LittleFS.format() && LittleFS.begin(false, FS_MOUNT, 10, "spiffs");
        if (g_fs_ok) { g_lg->begin(); countUnexported(); }
        Serial.printf("%s FORMAT\n", g_fs_ok ? "OK" : "ERR");
        continue;
      }
      if (!strncmp(line, "VBAT", 4)) {
        readBattery();
        Serial.printf("OK VBAT pin_mv=%d factor=%u.%03u cal=%u.%03u vbat_mv=%d low_stop_mv=%d\n", g_vbat_pin_mv,
                      (unsigned)(vbatFactorX1000() / 1000), (unsigned)(vbatFactorX1000() % 1000),
                      g_vbat_cal_x1000 / 1000, g_vbat_cal_x1000 % 1000, g_batt_mv, WFG_LOW_BATT_MV);
        continue;
      }
      if (!strncmp(line, "CALVBAT ", 8)) {
        // CALVBAT <multimeter mV at the battery> | CALVBAT RESET
        if (!strcmp(line + 8, "RESET")) g_vbat_cal_x1000 = 1000;
        else {
          readBattery();
          int meas = atoi(line + 8);
          uint32_t nominal = g_vbat_pin_mv > 0 ? (uint32_t)g_vbat_pin_mv * WFG_VBAT_DIVIDER_X1000 / 1000 : 0;
          uint32_t cal = nominal ? (uint32_t)meas * 1000 / nominal : 0;
          if (meas < 3000 || meas > 4300 || cal < 800 || cal > 1200) {
            Serial.println("ERR CALVBAT out-of-range (expect 3000-4300 mV and a correction within 20 %)");
            continue;
          }
          g_vbat_cal_x1000 = (uint16_t)cal;
        }
        g_prefs.putUShort("vcal", g_vbat_cal_x1000);
        readBattery();
        Serial.printf("OK CALVBAT cal=%u.%03u vbat_mv=%d\n", g_vbat_cal_x1000 / 1000, g_vbat_cal_x1000 % 1000, g_batt_mv);
        continue;
      }
      if (!g_fs_ok) { Serial.println("ERR FS not-mounted"); continue; }
      bool heavy = !strncmp(line, "DUMP", 4) || !strncmp(line, "LIST", 4) || !strncmp(line, "CHECK", 5);
      if (heavy && g_lg->recording()) {
        // Long USB transfers would starve the GNSS UART while recording.
        Serial.printf("ERR %.5s recording-active (stop recording first)\n", line);
        continue;
      }
      // A host is actively talking: allow blocking writes so long DUMPs are not truncated. Back to
      // non-blocking afterwards so a disconnected cable can never stall logging.
#if ARDUINO_USB_CDC_ON_BOOT
      Serial.setTxTimeoutMs(2000);
#endif
      g_proto->handleLine(line, now, g_mode);
      Serial.flush();
#if ARDUINO_USB_CDC_ON_BOOT
      Serial.setTxTimeoutMs(0);
#endif
      if (!strncmp(line, "CONFIRM", 7)) countUnexported();
    } else if (len < sizeof(line) - 1) {
      line[len++] = (char)c;
    }
  }
}

// ---------------------------------------------------------------- loop
void loop() {
  uint32_t now = millis();
  // 1. GNSS bytes -> parser -> logger
  int budget = 512;
  while (Serial1.available() && budget--) {
    if (g_nmea.feed((char)Serial1.read(), millis()) && g_nmea.hasEpoch()) {
      GnssEpoch e = g_nmea.takeEpoch();
      g_last_epoch = e; g_have_epoch = true; g_last_epoch_ms = millis();
      if (g_fs_ok) g_lg->onEpoch(e, millis());
    }
  }
  now = millis();
  if (g_nmea.poll(now) && g_nmea.hasEpoch()) {
    GnssEpoch e = g_nmea.takeEpoch();
    g_last_epoch = e; g_have_epoch = true; g_last_epoch_ms = now;
    if (g_fs_ok) g_lg->onEpoch(e, now);
  }
  if (g_fs_ok) g_lg->tick(now, &g_nmea);
  if (g_nvs_rec && !g_lg->recording()) nvsClearRecording();  // logger ended the session itself (FULL, FS error)
  if (g_resumed_session && g_lg->recording() && now - g_rec_started_ms > 60000) {
    g_prefs.putUChar("rs_qf", 0);  // resumed session ran 60 s: not a reboot loop
    g_resumed_session = false;
  }
  if (g_lg->state() == LS_FULL && g_lg->recording() == false) {
    static bool full_shown = false;
    if (!full_shown) { banner("STORAGE FULL - stopped", 10000); wake(now); countUnexported(); full_shown = true; }
  }

  // 2. Button
  bool pressed = digitalRead(WFG_PIN_BUTTON) == (WFG_BUTTON_ACTIVE_LOW ? LOW : HIGH);
  if (pressed) { g_last_input_ms = now; if (!display_is_on() && g_btn.holdMs(now) > 300) display_power(true); }
  Gesture g = g_btn.update(pressed, now);
  if (g != G_NONE) handleGesture(g, now);

  // 3. Battery every 10 s; low-battery clean stop
  if (now - g_last_batt_ms > 10000) {
    g_last_batt_ms = now;
    readBattery();
    if (g_lg->recording() && g_batt_pct >= 0 && g_batt_mv < WFG_LOW_BATT_MV) {
      if (++g_low_batt_count >= 3) {
        g_lg->stop(END_LOW_BATTERY, now);
        nvsClearRecording();
        banner("LOW BATTERY - stopped", 10000);
      }
    } else {
      g_low_batt_count = 0;
    }
  }

  // 4. Export mode
  if (web_active()) {
    web_loop();
    if (web_clients()) g_export_last_client_ms = now;
    if (now - g_export_last_client_ms > EXPORT_IDLE_TIMEOUT_MS) { web_stop(); banner("Export mode timed out", 5000); }
    g_last_input_ms = max(g_last_input_ms, now - SCREEN_TIMEOUT_MS + 1000);  // keep SSID/password visible
  }

  // 5. USB protocol
  handleSerial(now);
  g_proto->hasPendingDelete(now);  // expire stale requests

  // 6. Screen
  if (display_is_on() && now - g_last_input_ms > SCREEN_TIMEOUT_MS && !g_btn.isDown()) display_power(false);
  uint32_t period = g_btn.isDown() ? 100 : 500;
  if (display_is_on() && now - g_last_draw_ms >= period) { g_last_draw_ms = now; draw(now); }
  delay(5);
}
