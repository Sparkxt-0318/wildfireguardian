#include "wfg_export.h"
#include "wfg_logger.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

namespace wfg {

const char* kCsvHeader =
    "session_id,movement_mode,mode_source,seq,record_type,mono_ms,gnss_utc,utc_est,utc_est_basis,"
    "fix_valid,nofix_reason,gga_quality,fix_type,sats,hdop,lat,lon,alt_m,speed_mps,course_deg,"
    "epoch_age_ms,nmea_checksum_errors_seen,raw_nmea_available,event_no,event_located,event_ref_fix_seq,"
    "event_ref_fix_age_ms,event_press_mono_ms,clock_kind,clock_offset_ms,clock_delta_ms,end_reason,"
    "end_torn_bytes_removed,status_vbat_mv,status_vbat_pin_mv,status_vbat_factor,status_fs_free_bytes,"
    "status_fs_total_bytes,status_nmea_ok,status_nmea_checksum_errors,session_start_reason,resumed_from_session_id,"
    "owner_annotation\n";

bool Sink::puts(const char* s) { return write(s, strlen(s)); }
bool Sink::printf(const char* fmt, ...) {
  char buf[512];
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  if (n < 0) return false;
  if ((size_t)n >= sizeof(buf)) n = sizeof(buf) - 1;
  return write(buf, (size_t)n);
}

void fmt_e7(int32_t v, char* out) {
  int64_t x = v;
  const char* sign = "";
  if (x < 0) { sign = "-"; x = -x; }
  sprintf(out, "%s%lld.%07lld", sign, (long long)(x / 10000000), (long long)(x % 10000000));
}
void fmt_centi(int64_t v, char* out) {
  const char* sign = "";
  if (v < 0) { sign = "-"; v = -v; }
  sprintf(out, "%s%lld.%02lld", sign, (long long)(v / 100), (long long)(v % 100));
}
void fmt_iso(uint32_t ymd, uint32_t ms, char* out) {
  sprintf(out, "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ", (unsigned)(ymd / 10000), (unsigned)(ymd / 100 % 100),
          (unsigned)(ymd % 100), (unsigned)(ms / 3600000), (unsigned)(ms / 60000 % 60), (unsigned)(ms / 1000 % 60),
          (unsigned)(ms % 1000));
}
static void fmt_iso_epoch(int64_t epoch_ms, char* out) {
  uint32_t ymd, ms;
  epoch_ms_to_utc(epoch_ms, ymd, ms);
  fmt_iso(ymd, ms, out);
}

// ---- record iteration ----
struct Reader {
  Storage& st;
  FILE* f = nullptr;
  uint32_t index = 0;
  explicit Reader(Storage& s) : st(s) {}
  bool open(const char* name) { f = st.open(name, "rb"); index = 0; return f != nullptr; }
  void rewind() { fseek(f, 0, SEEK_SET); index = 0; }
  // returns 0 = eof, 1 = ok, -1 = bad record
  int next(Record& r) {
    uint8_t b[WFG_RECORD_SIZE];
    if (fread(b, 1, WFG_RECORD_SIZE, f) != WFG_RECORD_SIZE) return 0;
    index++;
    return decode(b, r) ? 1 : -1;
  }
  ~Reader() { if (f) st.close(f); }
};

struct SessionMeta {
  bool have_start = false;
  SessionStart start{};
  bool have_offset = false;
  int64_t first_offset = 0;
  char sid[32] = "";
  const char* mode = "UNKNOWN";
  const char* start_reason = "OWNER_BUTTON";
  char resumed_from[32] = "";  // session_id of the session cut by the reset, or empty
};

static void scanMeta(Reader& rd, SessionMeta& m) {
  rd.rewind();
  Record r;
  int k;
  while ((k = rd.next(r)) != 0) {
    if (k < 0) continue;
    if (r.h.type == REC_SESSION_START && !m.have_start) { m.have_start = true; m.start = r.start; }
    if (r.h.type == REC_CLOCK && !m.have_offset) { m.have_offset = true; m.first_offset = r.clk.offset_ms; }
  }
  if (m.have_start) {
    Logger::makeSessionId(m.start.device_id, m.start.session_no, m.sid, sizeof(m.sid));
    m.mode = mode_name(m.start.movement_mode);
    m.start_reason = start_reason_name(m.start.start_reason);
    if (m.start.resumed_from_session_no)
      Logger::makeSessionId(m.start.device_id, m.start.resumed_from_session_no, m.resumed_from, sizeof(m.resumed_from));
  }
  rd.rewind();
}

static const char* fixTypeName(uint8_t t) {
  switch (t) { case 1: return "NONE"; case 2: return "2D"; case 3: return "3D"; default: return ""; }
}

// ---------------- CSV ----------------
enum CsvCol {
  C_SID, C_MODE, C_MODE_SRC, C_SEQ, C_TYPE, C_MONO, C_GNSS_UTC, C_UTC_EST, C_UTC_BASIS, C_FIX_VALID, C_NOFIX_REASON,
  C_GGA_Q, C_FIX_TYPE, C_SATS, C_HDOP, C_LAT, C_LON, C_ALT, C_SPEED, C_COURSE, C_EPOCH_AGE, C_CKSUM, C_RAW,
  C_EV_NO, C_EV_LOCATED, C_EV_REF_SEQ, C_EV_REF_AGE, C_EV_PRESS, C_CLK_KIND, C_CLK_OFF, C_CLK_DELTA, C_END_REASON,
  C_END_TORN, C_ST_VBAT, C_ST_PIN, C_ST_FACTOR, C_ST_FREE, C_ST_TOTAL, C_ST_NMEA_OK, C_ST_NMEA_BAD, C_START_REASON,
  C_RESUMED_FROM, C_OWNER_ANNOT, C_NCOLS
};

static bool exportCsv(Reader& rd, const SessionMeta& m, Sink& out, ExportStats& stx) {
  if (!out.puts(kCsvHeader)) return false;
  Record r;
  int k;
  bool have_off = m.have_offset;
  int64_t off = m.first_offset;
  static char cell[C_NCOLS][36];
  while ((k = rd.next(r)) != 0) {
    stx.records++;
    for (int i = 0; i < C_NCOLS; i++) cell[i][0] = 0;
    snprintf(cell[C_SID], 36, "%s", m.sid);
    snprintf(cell[C_MODE], 36, "%s", m.mode);
    snprintf(cell[C_MODE_SRC], 36, "owner_selected_on_device");
    snprintf(cell[C_START_REASON], 36, "%s", m.start_reason);
    snprintf(cell[C_RESUMED_FROM], 36, "%s", m.resumed_from);
    if (k < 0) {
      stx.bad_records++;
      snprintf(cell[C_TYPE], 36, "CORRUPT");
    } else {
      if (r.h.type == REC_CLOCK) { have_off = true; off = r.clk.offset_ms; }
      snprintf(cell[C_SEQ], 36, "%u", (unsigned)r.h.seq);
      snprintf(cell[C_TYPE], 36, "%s", rec_type_name(r.h.type));
      bool recovered_end = r.h.type == REC_SESSION_END && r.end.reason == END_RECOVERED_ON_BOOT;
      if (!recovered_end) snprintf(cell[C_MONO], 36, "%u", (unsigned)r.h.mono_ms);  // recovered END: written after reboot
      uint32_t est_mono = r.h.type == REC_EVENT ? r.ev.press_mono_ms : r.h.mono_ms;
      if (have_off && !recovered_end) {
        fmt_iso_epoch(off + (int64_t)est_mono, cell[C_UTC_EST]);
        snprintf(cell[C_UTC_BASIS], 36, "mono_ms+gnss_clock_offset");
      }
      if (r.h.type == REC_FIX || r.h.type == REC_NOFIX) {
        const Obs& o = r.obs;
        bool fix = r.h.type == REC_FIX;
        if (fix) stx.fix_rows++; else stx.nofix_rows++;
        if ((o.valid & V_TIME) && (o.valid & V_DATE)) fmt_iso(o.utc_date, o.utc_ms_of_day, cell[C_GNSS_UTC]);
        snprintf(cell[C_FIX_VALID], 36, "%d", fix ? 1 : 0);
        snprintf(cell[C_NOFIX_REASON], 36, "%s", nofix_reason_name(o.nofix_reason));
        if (o.gga_quality != 0xFF) snprintf(cell[C_GGA_Q], 36, "%u", o.gga_quality);
        if (o.valid & V_FIXTYPE) snprintf(cell[C_FIX_TYPE], 36, "%s", fixTypeName(o.fix_type));
        if (o.valid & V_SATS) snprintf(cell[C_SATS], 36, "%u", o.sats);
        if (o.valid & V_HDOP) fmt_centi(o.hdop_x100, cell[C_HDOP]);
        if (o.valid & V_POS) { fmt_e7(o.lat_e7, cell[C_LAT]); fmt_e7(o.lon_e7, cell[C_LON]); }
        if (o.valid & V_ALT) fmt_centi(o.alt_cm, cell[C_ALT]);
        if (o.valid & V_SPEED) fmt_centi(o.speed_cmps, cell[C_SPEED]);
        if (o.valid & V_COURSE) fmt_centi(o.course_cdeg, cell[C_COURSE]);
        if (r.h.flags0 != 0xFF) snprintf(cell[C_EPOCH_AGE], 36, "%u", (unsigned)r.h.flags0 * 10);
        snprintf(cell[C_CKSUM], 36, "%d", (o.valid & V_CKSUM_ERR) ? 1 : 0);
        snprintf(cell[C_RAW], 36, "%d", (o.valid & V_RAW_NMEA) ? 1 : 0);
      } else if (r.h.type == REC_EVENT) {
        const Event& e = r.ev;
        stx.events++;
        if (e.located) { stx.events_located++; fmt_e7(e.lat_e7, cell[C_LAT]); fmt_e7(e.lon_e7, cell[C_LON]); }
        snprintf(cell[C_EV_NO], 36, "%u", (unsigned)e.event_no);
        snprintf(cell[C_EV_LOCATED], 36, "%d", e.located ? 1 : 0);
        if (e.ref_fix_seq != 0xFFFFFFFF) snprintf(cell[C_EV_REF_SEQ], 36, "%u", (unsigned)e.ref_fix_seq);
        if (e.ref_fix_age_ms != 0xFFFFFFFF) snprintf(cell[C_EV_REF_AGE], 36, "%u", (unsigned)e.ref_fix_age_ms);
        snprintf(cell[C_EV_PRESS], 36, "%u", (unsigned)e.press_mono_ms);
      } else if (r.h.type == REC_CLOCK) {
        fmt_iso(r.clk.utc_date, r.clk.utc_ms_of_day, cell[C_GNSS_UTC]);
        snprintf(cell[C_CLK_KIND], 36, "%s", r.clk.kind == CLOCK_FIRST_UTC ? "FIRST_UTC" : "JUMP");
        snprintf(cell[C_CLK_OFF], 36, "%lld", (long long)r.clk.offset_ms);
        snprintf(cell[C_CLK_DELTA], 36, "%lld", (long long)r.clk.delta_ms);
      } else if (r.h.type == REC_STATUS) {
        const Status& t = r.st;
        if ((t.flags & ST_BATT_VALID) && t.vbat_mv != 0xFFFF) snprintf(cell[C_ST_VBAT], 36, "%u", t.vbat_mv);
        if (t.vbat_pin_mv != 0xFFFF) snprintf(cell[C_ST_PIN], 36, "%u", t.vbat_pin_mv);
        if (t.vbat_factor_x1000) snprintf(cell[C_ST_FACTOR], 36, "%u.%03u", t.vbat_factor_x1000 / 1000, t.vbat_factor_x1000 % 1000);
        snprintf(cell[C_ST_FREE], 36, "%u", (unsigned)t.fs_free_bytes);
        snprintf(cell[C_ST_TOTAL], 36, "%u", (unsigned)t.fs_total_bytes);
        snprintf(cell[C_ST_NMEA_OK], 36, "%u", (unsigned)t.nmea_ok);
        snprintf(cell[C_ST_NMEA_BAD], 36, "%u", (unsigned)t.nmea_bad_checksum);
      } else if (r.h.type == REC_SESSION_END) {
        snprintf(cell[C_END_REASON], 36, "%s", end_reason_name(r.end.reason));
        snprintf(cell[C_END_TORN], 36, "%u", (unsigned)r.end.torn_bytes_removed);
      }
    }
    for (int i = 0; i < C_NCOLS; i++) {
      if (i && !out.write(",", 1)) return false;
      if (cell[i][0] && !out.puts(cell[i])) return false;
    }
    if (!out.write("\n", 1)) return false;
  }
  return true;
}

// ---------------- GPX ----------------
static bool exportGpx(Reader& rd, const SessionMeta& m, Sink& out, ExportStats& stx) {
  if (!out.puts("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<gpx version=\"1.1\" creator=\"WildfireGuardian route logger\" "
                "xmlns=\"http://www.topografix.com/GPX/1/1\" xmlns:wfg=\"urn:wildfireguardian:route-logger:1\">\n"))
    return false;
  if (!out.printf("<metadata><name>%s</name><desc>movement_mode=%s (owner_selected_on_device). start_reason=%s%s%s. "
                  "Coordinates as received from GNSS, not map-matched. HDOP is a unitless dilution factor, not "
                  "metres. Track segments break at every NOFIX row. STATUS rows (battery, storage) are in the CSV "
                  "only.</desc></metadata>\n",
                  m.sid, m.mode, m.start_reason, m.resumed_from[0] ? " resumed_from=" : "", m.resumed_from))
    return false;
  Record r;
  int k;
  bool have_off = m.have_offset;
  int64_t off = m.first_offset;
  // pass 1: located events as waypoints (GPX 1.1 requires wpt before trk)
  while ((k = rd.next(r)) != 0) {
    if (k < 0) continue;
    if (r.h.type == REC_CLOCK) { have_off = true; off = r.clk.offset_ms; }
    if (r.h.type == REC_EVENT && r.ev.located) {
      char lat[20], lon[20], t[32] = "";
      fmt_e7(r.ev.lat_e7, lat);
      fmt_e7(r.ev.lon_e7, lon);
      if (!out.printf("<wpt lat=\"%s\" lon=\"%s\">", lat, lon)) return false;
      if (have_off) { fmt_iso_epoch(off + (int64_t)r.ev.press_mono_ms, t); out.printf("<time>%s</time>", t); }
      if (!out.printf("<name>EVENT %u</name><type>event_marker</type><extensions><wfg:seq>%u</wfg:seq>"
                      "<wfg:ref_fix_seq>%u</wfg:ref_fix_seq><wfg:ref_fix_age_ms>%u</wfg:ref_fix_age_ms>"
                      "<wfg:position_source>last_fix_before_press</wfg:position_source></extensions></wpt>\n",
                      (unsigned)r.ev.event_no, (unsigned)r.h.seq, (unsigned)r.ev.ref_fix_seq,
                      (unsigned)r.ev.ref_fix_age_ms))
        return false;
    }
  }
  rd.rewind();
  if (!out.printf("<trk><name>%s</name><type>%s</type>\n", m.sid, m.mode)) return false;
  bool in_seg = false;
  while ((k = rd.next(r)) != 0) {
    stx.records++;
    if (k < 0) { stx.bad_records++; continue; }
    if (r.h.type == REC_FIX) {
      stx.fix_rows++;
      const Obs& o = r.obs;
      if (!in_seg) { if (!out.puts("<trkseg>\n")) return false; in_seg = true; stx.segments++; }
      char lat[20], lon[20];
      fmt_e7(o.lat_e7, lat);
      fmt_e7(o.lon_e7, lon);
      char buf[512];
      int n = snprintf(buf, sizeof(buf), "<trkpt lat=\"%s\" lon=\"%s\">", lat, lon);
      char tmp[32];
      if (o.valid & V_ALT) { fmt_centi(o.alt_cm, tmp); n += snprintf(buf + n, sizeof(buf) - n, "<ele>%s</ele>", tmp); }
      if ((o.valid & V_TIME) && (o.valid & V_DATE)) {
        fmt_iso(o.utc_date, o.utc_ms_of_day, tmp);
        n += snprintf(buf + n, sizeof(buf) - n, "<time>%s</time>", tmp);
      }
      if ((o.valid & V_FIXTYPE) && (o.fix_type == 2 || o.fix_type == 3))
        n += snprintf(buf + n, sizeof(buf) - n, "<fix>%s</fix>", o.fix_type == 2 ? "2d" : "3d");
      if (o.valid & V_SATS) n += snprintf(buf + n, sizeof(buf) - n, "<sat>%u</sat>", o.sats);
      if (o.valid & V_HDOP) { fmt_centi(o.hdop_x100, tmp); n += snprintf(buf + n, sizeof(buf) - n, "<hdop>%s</hdop>", tmp); }
      n += snprintf(buf + n, sizeof(buf) - n, "<extensions><wfg:seq>%u</wfg:seq><wfg:mono_ms>%u</wfg:mono_ms>",
                    (unsigned)r.h.seq, (unsigned)r.h.mono_ms);
      if (o.valid & V_SPEED) { fmt_centi(o.speed_cmps, tmp); n += snprintf(buf + n, sizeof(buf) - n, "<wfg:speed_mps>%s</wfg:speed_mps>", tmp); }
      if (o.valid & V_COURSE) { fmt_centi(o.course_cdeg, tmp); n += snprintf(buf + n, sizeof(buf) - n, "<wfg:course_deg>%s</wfg:course_deg>", tmp); }
      n += snprintf(buf + n, sizeof(buf) - n, "</extensions></trkpt>\n");
      if (!out.write(buf, (size_t)n)) return false;
    } else if (r.h.type == REC_NOFIX) {
      stx.nofix_rows++;
      if (in_seg) { if (!out.puts("</trkseg>\n")) return false; in_seg = false; }
    } else if (r.h.type == REC_EVENT) {
      stx.events++;
      if (r.ev.located) stx.events_located++;
    }
  }
  if (in_seg && !out.puts("</trkseg>\n")) return false;
  if (!out.puts("</trk>\n")) return false;
  // unlocated events: kept, but without a position (no interpolation)
  rd.rewind();
  bool ext_open = false;
  have_off = m.have_offset;
  off = m.first_offset;
  while ((k = rd.next(r)) != 0) {
    if (k < 0) continue;
    if (r.h.type == REC_CLOCK) { have_off = true; off = r.clk.offset_ms; }
    if (r.h.type == REC_EVENT && !r.ev.located) {
      if (!ext_open) { if (!out.puts("<extensions>\n")) return false; ext_open = true; }
      char t[32] = "";
      if (have_off) fmt_iso_epoch(off + (int64_t)r.ev.press_mono_ms, t);
      if (!out.printf("<wfg:unlocated_event no=\"%u\" seq=\"%u\" press_mono_ms=\"%u\" utc_est=\"%s\"/>\n",
                      (unsigned)r.ev.event_no, (unsigned)r.h.seq, (unsigned)r.ev.press_mono_ms, t))
        return false;
    }
  }
  if (ext_open && !out.puts("</extensions>\n")) return false;
  return out.puts("</gpx>\n");
}

// ---------------- GeoJSON ----------------
static bool exportGeoJson(Reader& rd, const SessionMeta& m, Sink& out, ExportStats& stx) {
  char rf[40] = "null";
  if (m.resumed_from[0]) snprintf(rf, sizeof(rf), "\"%s\"", m.resumed_from);
  if (!out.printf("{\"type\":\"FeatureCollection\",\"wfg\":{\"session_id\":\"%s\",\"movement_mode\":\"%s\","
                  "\"mode_source\":\"owner_selected_on_device\",\"start_reason\":\"%s\",\"resumed_from_session_id\":%s,"
                  "\"coordinates\":\"as received from GNSS, not "
                  "map-matched\",\"hdop_note\":\"unitless dilution factor, not metres\"},\"features\":[\n",
                  m.sid, m.mode, m.start_reason, rf))
    return false;
  // Feature 1: track as MultiLineString of fix runs with >= 2 points.
  if (!out.printf("{\"type\":\"Feature\",\"properties\":{\"kind\":\"track\",\"session_id\":\"%s\","
                  "\"movement_mode\":\"%s\",\"segment_break\":\"NOFIX row\"},\"geometry\":{\"type\":\"MultiLineString\","
                  "\"coordinates\":[",
                  m.sid, m.mode))
    return false;
  Record r, pend;
  memset(&pend, 0, sizeof(pend));
  int k;
  int run = 0;
  bool first_line = true;
  auto pos = [](const Obs& o, char* buf) {
    char la[20], lo[20], al[20];
    fmt_e7(o.lat_e7, la);
    fmt_e7(o.lon_e7, lo);
    if (o.valid & V_ALT) { fmt_centi(o.alt_cm, al); sprintf(buf, "[%s,%s,%s]", lo, la, al); }
    else sprintf(buf, "[%s,%s]", lo, la);
  };
  char pb[80];
  while ((k = rd.next(r)) != 0) {
    stx.records++;
    if (k < 0) { stx.bad_records++; continue; }
    if (r.h.type == REC_FIX) {
      stx.fix_rows++;
      run++;
      if (run == 1) { pend = r; continue; }
      if (run == 2) {
        if (!out.puts(first_line ? "\n[" : ",\n[")) return false;
        first_line = false;
        stx.segments++;
        pos(pend.obs, pb);
        if (!out.puts(pb)) return false;
      }
      pos(r.obs, pb);
      if (!out.puts(",") || !out.puts(pb)) return false;
    } else if (r.h.type == REC_NOFIX) {
      stx.nofix_rows++;
      if (run >= 2 && !out.puts("]")) return false;
      run = 0;
    } else if (r.h.type == REC_EVENT) {
      stx.events++;
      if (r.ev.located) stx.events_located++;
    }
  }
  if (run >= 2 && !out.puts("]")) return false;
  if (!out.puts("]}}")) return false;
  // Isolated single fixes (runs of length 1) as Points so no fix is silently dropped.
  rd.rewind();
  run = 0;
  auto isolated = [&](const Record& p) -> bool {
    pos(p.obs, pb);
    return out.printf(",\n{\"type\":\"Feature\",\"properties\":{\"kind\":\"isolated_fix\",\"seq\":%u},"
                      "\"geometry\":{\"type\":\"Point\",\"coordinates\":%s}}",
                      (unsigned)p.h.seq, pb);
  };
  while ((k = rd.next(r)) != 0) {
    if (k < 0) continue;
    if (r.h.type == REC_FIX) { run++; if (run == 1) pend = r; }
    else if (r.h.type == REC_NOFIX) { if (run == 1 && !isolated(pend)) return false; run = 0; }
  }
  if (run == 1 && !isolated(pend)) return false;
  // Events: located -> Point at last fix before press; unlocated -> geometry null.
  rd.rewind();
  bool have_off = m.have_offset;
  int64_t off = m.first_offset;
  while ((k = rd.next(r)) != 0) {
    if (k < 0) continue;
    if (r.h.type == REC_CLOCK) { have_off = true; off = r.clk.offset_ms; }
    if (r.h.type != REC_EVENT) continue;
    const Event& e = r.ev;
    char t[40] = "null";
    if (have_off) { char iso[32]; fmt_iso_epoch(off + (int64_t)e.press_mono_ms, iso); sprintf(t, "\"%s\"", iso); }
    char rs[12] = "null", ra[12] = "null";
    if (e.ref_fix_seq != 0xFFFFFFFF) sprintf(rs, "%u", (unsigned)e.ref_fix_seq);
    if (e.ref_fix_age_ms != 0xFFFFFFFF) sprintf(ra, "%u", (unsigned)e.ref_fix_age_ms);
    if (!out.printf(",\n{\"type\":\"Feature\",\"properties\":{\"kind\":\"event_marker\",\"event_no\":%u,\"seq\":%u,"
                    "\"located\":%s,\"utc_est\":%s,\"ref_fix_seq\":%s,\"ref_fix_age_ms\":%s,\"source\":\"device_button\"},"
                    "\"geometry\":",
                    (unsigned)e.event_no, (unsigned)r.h.seq, e.located ? "true" : "false", t, rs, ra))
      return false;
    if (e.located) {
      char la[20], lo[20];
      fmt_e7(e.lat_e7, la);
      fmt_e7(e.lon_e7, lo);
      if (!out.printf("{\"type\":\"Point\",\"coordinates\":[%s,%s]}}", lo, la)) return false;
    } else if (!out.puts("null}")) {
      return false;
    }
  }
  return out.puts("\n]}\n");
}

bool export_session(Storage& st, const char* name, ExportFormat fmt, Sink& out, ExportStats* stats) {
  Reader rd(st);
  if (!rd.open(name)) return false;
  SessionMeta m;
  scanMeta(rd, m);
  if (!m.have_start) {
    // Header unreadable: still export rows under a placeholder id derived from the file name.
    snprintf(m.sid, sizeof(m.sid), "WFG-UNKNOWN-%.6s", name + 1);
  }
  ExportStats local;
  ExportStats& s = stats ? *stats : local;
  s = ExportStats();
  switch (fmt) {
    case FMT_CSV: return exportCsv(rd, m, out, s);
    case FMT_GPX: return exportGpx(rd, m, out, s);
    case FMT_GEOJSON: return exportGeoJson(rd, m, out, s);
  }
  return false;
}

}  // namespace wfg
