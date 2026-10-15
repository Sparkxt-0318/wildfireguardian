#include "wfg_record.h"
#include <string.h>

namespace wfg {

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len) {
  crc = ~crc;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

static void w8(uint8_t* p, size_t o, uint8_t v) { p[o] = v; }
static void w16(uint8_t* p, size_t o, uint16_t v) { p[o] = v & 0xFF; p[o + 1] = v >> 8; }
static void w32(uint8_t* p, size_t o, uint32_t v) { for (int i = 0; i < 4; i++) p[o + i] = (v >> (8 * i)) & 0xFF; }
static void w64(uint8_t* p, size_t o, uint64_t v) { for (int i = 0; i < 8; i++) p[o + i] = (v >> (8 * i)) & 0xFF; }
static uint8_t r8(const uint8_t* p, size_t o) { return p[o]; }
static uint16_t r16(const uint8_t* p, size_t o) { return (uint16_t)(p[o] | (p[o + 1] << 8)); }
static uint32_t r32(const uint8_t* p, size_t o) {
  uint32_t v = 0; for (int i = 3; i >= 0; i--) v = (v << 8) | p[o + i]; return v;
}
static uint64_t r64(const uint8_t* p, size_t o) {
  uint64_t v = 0; for (int i = 7; i >= 0; i--) v = (v << 8) | p[o + i]; return v;
}

void encode(const Record& r, uint8_t out[WFG_RECORD_SIZE]) {
  memset(out, 0, WFG_RECORD_SIZE);
  w16(out, 0, WFG_MAGIC);
  w8(out, 2, r.h.type);
  w8(out, 3, r.h.type == REC_SESSION_START ? r.start.start_reason : r.h.flags0);
  w32(out, 4, r.h.seq);
  w32(out, 8, r.h.mono_ms);
  switch (r.h.type) {
    case REC_SESSION_START: {
      const SessionStart& s = r.start;
      w32(out, 12, s.device_id); w32(out, 16, s.session_no);
      w8(out, 20, s.movement_mode); w8(out, 21, s.board_rev);
      w16(out, 22, s.fw_version); w16(out, 24, s.log_interval_ms);
      w8(out, 26, s.format_version); w8(out, 27, s.record_size);
      w32(out, 28, s.boot_count);
      if (s.format_version <= 1) { w32(out, 32, s.utc_date); w32(out, 36, s.utc_ms_of_day); }
      else { w32(out, 32, s.resumed_from_session_no); w8(out, 36, s.reset_reason); }
      w32(out, 40, s.event_locate_max_age_ms);
      break;
    }
    case REC_FIX:
    case REC_NOFIX: {
      const Obs& o = r.obs;
      w32(out, 12, o.utc_date); w32(out, 16, o.utc_ms_of_day);
      w32(out, 20, (uint32_t)o.lat_e7); w32(out, 24, (uint32_t)o.lon_e7); w32(out, 28, (uint32_t)o.alt_cm);
      w16(out, 32, o.speed_cmps); w16(out, 34, o.course_cdeg); w16(out, 36, o.hdop_x100);
      w8(out, 38, o.sats); w8(out, 39, o.gga_quality); w8(out, 40, o.fix_type); w8(out, 41, o.nofix_reason);
      w16(out, 42, o.valid);
      break;
    }
    case REC_EVENT: {
      const Event& e = r.ev;
      w32(out, 12, e.event_no); w32(out, 16, e.ref_fix_seq);
      w32(out, 20, (uint32_t)e.lat_e7); w32(out, 24, (uint32_t)e.lon_e7);
      w32(out, 28, e.ref_fix_age_ms); w32(out, 32, e.press_mono_ms);
      w16(out, 36, e.press_duration_ms); w8(out, 38, e.located); w8(out, 39, e.source);
      break;
    }
    case REC_CLOCK: {
      const Clock& c = r.clk;
      w32(out, 12, c.utc_date); w32(out, 16, c.utc_ms_of_day);
      w64(out, 20, (uint64_t)c.offset_ms); w64(out, 28, (uint64_t)c.delta_ms); w8(out, 36, c.kind);
      break;
    }
    case REC_SESSION_END: {
      const SessionEnd& e = r.end;
      w8(out, 12, e.reason);
      w32(out, 16, e.n_records_before); w32(out, 20, e.n_fix); w32(out, 24, e.n_nofix);
      w32(out, 28, e.n_events); w32(out, 32, e.crc32_before); w32(out, 36, e.torn_bytes_removed);
      w32(out, 40, e.n_clock);
      break;
    }
    case REC_STATUS: {
      const Status& t = r.st;
      w16(out, 12, t.vbat_mv); w16(out, 14, t.vbat_pin_mv); w16(out, 16, t.vbat_factor_x1000); w8(out, 18, t.flags);
      w32(out, 20, t.fs_free_bytes); w32(out, 24, t.fs_total_bytes); w32(out, 28, t.nmea_ok);
      w32(out, 32, t.nmea_bad_checksum); w32(out, 36, t.free_heap);
      break;
    }
    default: break;
  }
  w32(out, 44, crc32(out, 44));
}

bool decode(const uint8_t* in, Record& r) {
  memset(&r, 0, sizeof(r));
  if (r16(in, 0) != WFG_MAGIC) return false;
  if (r32(in, 44) != crc32(in, 44)) return false;
  r.h.type = r8(in, 2); r.h.flags0 = r8(in, 3); r.h.seq = r32(in, 4); r.h.mono_ms = r32(in, 8);
  switch (r.h.type) {
    case REC_SESSION_START: {
      SessionStart& s = r.start;
      s.device_id = r32(in, 12); s.session_no = r32(in, 16);
      s.movement_mode = r8(in, 20); s.board_rev = r8(in, 21);
      s.fw_version = r16(in, 22); s.log_interval_ms = r16(in, 24);
      s.format_version = r8(in, 26); s.record_size = r8(in, 27);
      s.boot_count = r32(in, 28);
      if (s.format_version <= 1) {
        s.utc_date = r32(in, 32); s.utc_ms_of_day = r32(in, 36);
        s.start_reason = START_OWNER_BUTTON;
      } else {
        s.utc_ms_of_day = 0xFFFFFFFF;
        s.resumed_from_session_no = r32(in, 32); s.reset_reason = r8(in, 36);
        s.start_reason = r.h.flags0;
      }
      s.event_locate_max_age_ms = r32(in, 40);
      return true;
    }
    case REC_FIX:
    case REC_NOFIX: {
      Obs& o = r.obs;
      o.utc_date = r32(in, 12); o.utc_ms_of_day = r32(in, 16);
      o.lat_e7 = (int32_t)r32(in, 20); o.lon_e7 = (int32_t)r32(in, 24); o.alt_cm = (int32_t)r32(in, 28);
      o.speed_cmps = r16(in, 32); o.course_cdeg = r16(in, 34); o.hdop_x100 = r16(in, 36);
      o.sats = r8(in, 38); o.gga_quality = r8(in, 39); o.fix_type = r8(in, 40); o.nofix_reason = r8(in, 41);
      o.valid = r16(in, 42);
      return true;
    }
    case REC_EVENT: {
      Event& e = r.ev;
      e.event_no = r32(in, 12); e.ref_fix_seq = r32(in, 16);
      e.lat_e7 = (int32_t)r32(in, 20); e.lon_e7 = (int32_t)r32(in, 24);
      e.ref_fix_age_ms = r32(in, 28); e.press_mono_ms = r32(in, 32);
      e.press_duration_ms = r16(in, 36); e.located = r8(in, 38); e.source = r8(in, 39);
      return true;
    }
    case REC_CLOCK: {
      Clock& c = r.clk;
      c.utc_date = r32(in, 12); c.utc_ms_of_day = r32(in, 16);
      c.offset_ms = (int64_t)r64(in, 20); c.delta_ms = (int64_t)r64(in, 28); c.kind = r8(in, 36);
      return true;
    }
    case REC_SESSION_END: {
      SessionEnd& e = r.end;
      e.reason = r8(in, 12);
      e.n_records_before = r32(in, 16); e.n_fix = r32(in, 20); e.n_nofix = r32(in, 24);
      e.n_events = r32(in, 28); e.crc32_before = r32(in, 32); e.torn_bytes_removed = r32(in, 36);
      e.n_clock = r32(in, 40);
      return true;
    }
    case REC_STATUS: {
      Status& t = r.st;
      t.vbat_mv = r16(in, 12); t.vbat_pin_mv = r16(in, 14); t.vbat_factor_x1000 = r16(in, 16); t.flags = r8(in, 18);
      t.fs_free_bytes = r32(in, 20); t.fs_total_bytes = r32(in, 24); t.nmea_ok = r32(in, 28);
      t.nmea_bad_checksum = r32(in, 32); t.free_heap = r32(in, 36);
      return true;
    }
    default:
      return false;
  }
}

const char* mode_name(uint8_t m) {
  switch (m) { case MODE_WALK: return "WALK"; case MODE_VEHICLE: return "VEHICLE"; default: return "UNKNOWN"; }
}
const char* rec_type_name(uint8_t t) {
  switch (t) {
    case REC_SESSION_START: return "SESSION_START"; case REC_FIX: return "FIX"; case REC_NOFIX: return "NOFIX";
    case REC_EVENT: return "EVENT"; case REC_CLOCK: return "CLOCK"; case REC_SESSION_END: return "SESSION_END";
    case REC_STATUS: return "STATUS";
    default: return "UNKNOWN";
  }
}
const char* end_reason_name(uint8_t r) {
  switch (r) {
    case END_USER_STOP: return "USER_STOP"; case END_STORAGE_FULL: return "STORAGE_FULL";
    case END_LOW_BATTERY: return "LOW_BATTERY"; case END_RECOVERED_ON_BOOT: return "RECOVERED_ON_BOOT";
    case END_FS_ERROR: return "FS_ERROR"; default: return "UNKNOWN";
  }
}
const char* start_reason_name(uint8_t r) {
  return r == START_AUTO_RESUMED_AFTER_RESET ? "AUTO_RESUMED_AFTER_RESET" : "OWNER_BUTTON";
}
const char* nofix_reason_name(uint8_t r) {
  switch (r) {
    case NOFIX_RECEIVER: return "RECEIVER_NO_FIX"; case NOFIX_NO_DATA: return "NO_NMEA_DATA";
    case NOFIX_CKSUM_ONLY: return "CHECKSUM_ERRORS_ONLY"; default: return "";
  }
}

}  // namespace wfg
