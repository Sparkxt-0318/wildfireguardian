// Status screen (ST7735S 160x80 via LovyanGFX). All pins/offsets come from include/board_*.h.
#pragma once
#include <stdint.h>

struct UiState {
  const char* rec_state;     // "IDLE" / "REC" / "FULL" / "EXPORT" / "FS ERR"
  bool recording;
  const char* mode;          // WALK / VEHICLE / UNKNOWN
  bool gnss_seen;            // any valid NMEA in the last 3 s
  bool fix;
  uint8_t fix_type;          // 0 unknown, 2 = 2D, 3 = 3D
  int sats;                  // -1 unknown
  int hdop_x10;              // -1 unknown (displayed as unitless "HDOP")
  int batt_pct;              // -1 unknown
  int batt_mv;               // -1 unknown
  uint32_t fs_used_kb, fs_total_kb;
  float hours_left;          // storage hours remaining at 1 Hz
  uint32_t session_no;       // 0 = none
  uint32_t seq;
  int32_t last_event_no;     // 0 = none
  bool last_event_located;
  uint32_t last_event_age_s;
  const char* export_line1;  // export mode info or NULL
  const char* export_line2;
  bool resumed;              // current session was auto-resumed after a reset
  const char* banner;        // transient message (e.g. "EVENT 3 (no fix)") or NULL
  const char* hold_text;     // hold countdown text or NULL
  uint8_t hold_progress;     // 0..100
  uint16_t unexported;       // count of sessions not yet export-confirmed (all sessions, no cap)
};

void display_begin();
void display_draw(const UiState& s);
void display_power(bool on);   // backlight + panel sleep
bool display_is_on();
