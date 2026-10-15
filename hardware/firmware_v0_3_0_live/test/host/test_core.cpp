// HOST / SIMULATED unit tests for the hardware-independent logging core (wfg_core).
// These run on Linux/macOS with g++/clang++. They do NOT exercise the ESP32, LittleFS, the GNSS module, the TFT
// or the button hardware. Build + run: firmware/test/host/run_host_tests.sh
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>

#include "wfg_record.h"
#include "wfg_sha256.h"
#include "wfg_nmea.h"
#include "wfg_storage.h"
#include "wfg_logger.h"
#include "wfg_export.h"
#include "wfg_button.h"
#include "wfg_proto.h"
#include "wfg_resume.h"
#include "wfg_live.h"

using namespace wfg;

static int g_pass = 0, g_fail = 0;
static const char* g_test = "";
#define CHECK(c)                                                                     \
  do {                                                                               \
    if (c) g_pass++;                                                                 \
    else { g_fail++; fprintf(stderr, "FAIL [%s] %s:%d: %s\n", g_test, __FILE__, __LINE__, #c); } \
  } while (0)
#define CHECK_EQ(a, b)                                                               \
  do {                                                                               \
    long long _a = (long long)(a), _b = (long long)(b);                              \
    if (_a == _b) g_pass++;                                                          \
    else { g_fail++; fprintf(stderr, "FAIL [%s] %s:%d: %s == %s (%lld vs %lld)\n", g_test, __FILE__, __LINE__, #a, #b, _a, _b); } \
  } while (0)
#define CHECK_STR(a, b)                                                              \
  do {                                                                               \
    std::string _a = (a), _b = (b);                                                  \
    if (_a == _b) g_pass++;                                                          \
    else { g_fail++; fprintf(stderr, "FAIL [%s] %s:%d: \"%s\" != \"%s\"\n", g_test, __FILE__, __LINE__, _a.c_str(), _b.c_str()); } \
  } while (0)

static std::string g_root;

static std::string freshDir(const char* name) {
  std::string d = g_root + "/" + name;
  std::string cmd = "rm -rf '" + d + "' && mkdir -p '" + d + "'";
  if (system(cmd.c_str()) != 0) { fprintf(stderr, "mkdir failed\n"); exit(2); }
  return d;
}

struct StrSink : Sink {
  std::string s;
  bool write(const char* p, size_t n) override { s.append(p, n); return true; }
};

// ---------------------------------------------------------------- NMEA synthesis
static std::string withCk(const std::string& body) {
  uint8_t c = 0;
  for (char ch : body) c ^= (uint8_t)ch;
  char t[8];
  snprintf(t, sizeof(t), "*%02X", c);
  return "$" + body + t;
}
static std::string ddmm(double deg, bool lat) {
  double a = deg < 0 ? -deg : deg;
  int d = (int)a;
  double m = (a - d) * 60.0;
  char b[32];
  if (lat) snprintf(b, sizeof(b), "%02d%08.5f,%c", d, m, deg < 0 ? 'S' : 'N');
  else snprintf(b, sizeof(b), "%03d%08.5f,%c", d, m, deg < 0 ? 'W' : 'E');
  return b;
}
static std::string hms(uint32_t ms) {
  char b[16];
  snprintf(b, sizeof(b), "%02u%02u%02u.%02u", ms / 3600000, ms / 60000 % 60, ms / 1000 % 60, (ms % 1000) / 10);
  return b;
}
struct SimFix { bool fix; double lat, lon, alt, kn, cog; int sats; double hdop; };
static std::vector<std::string> epochLines(uint32_t utc_ms, const char* ddmmyy, const SimFix& f, bool time_known = true) {
  std::vector<std::string> v;
  std::string t = time_known ? hms(utc_ms) : "";
  char b[200];
  if (f.fix) {
    snprintf(b, sizeof(b), "GNGGA,%s,%s,%s,1,%02d,%.1f,%.1f,M,8.0,M,,", t.c_str(), ddmm(f.lat, true).c_str(),
             ddmm(f.lon, false).c_str(), f.sats, f.hdop, f.alt);
    v.push_back(withCk(b));
    snprintf(b, sizeof(b), "GNRMC,%s,A,%s,%s,%.3f,%.2f,%s,,,A,V", t.c_str(), ddmm(f.lat, true).c_str(),
             ddmm(f.lon, false).c_str(), f.kn, f.cog, ddmmyy);
    v.push_back(withCk(b));
    v.push_back(withCk("GNGSA,A,3,01,02,03,04,05,06,,,,,,,1.8,1.1,1.4,1"));
  } else {
    snprintf(b, sizeof(b), "GNGGA,%s,,,,,0,%02d,,,M,,M,,", t.c_str(), f.sats);
    v.push_back(withCk(b));
    snprintf(b, sizeof(b), "GNRMC,%s,V,,,,,,,%s,,,N,V", t.c_str(), time_known ? ddmmyy : "");
    v.push_back(withCk(b));
    v.push_back(withCk("GNGSA,A,1,,,,,,,,,,,,,99.99,99.99,99.99,1"));
  }
  return v;
}

// ---------------------------------------------------------------- tests
static void test_crc_sha() {
  g_test = "crc_sha";
  CHECK_EQ(crc32((const uint8_t*)"123456789", 9), 0xCBF43926u);
  Sha256 h;
  char hx[65];
  h.update("abc", 3);
  h.finishHex(hx);
  CHECK_STR(hx, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  Sha256 e;
  e.finishHex(hx);
  CHECK_STR(hx, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  std::string m(1000, 'a');
  Sha256 l;
  for (int i = 0; i < 1000; i++) l.update(m.data(), m.size());  // 1,000,000 x 'a'
  l.finishHex(hx);
  CHECK_STR(hx, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

static void test_record_roundtrip() {
  g_test = "record_roundtrip";
  uint8_t b[WFG_RECORD_SIZE];
  Record r, d;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_FIX; r.h.seq = 123456; r.h.mono_ms = 0xFFFFFF00u; r.h.flags0 = 17;
  r.obs.utc_date = 20261003; r.obs.utc_ms_of_day = 86399999;
  r.obs.lat_e7 = -899999999; r.obs.lon_e7 = 1799999999; r.obs.alt_cm = -12345;
  r.obs.speed_cmps = 65535; r.obs.course_cdeg = 35999; r.obs.hdop_x100 = 9999; r.obs.sats = 42;
  r.obs.gga_quality = 1; r.obs.fix_type = 3; r.obs.valid = 0x07FF;
  encode(r, b);
  CHECK(b[0] == 'W' && b[1] == 'F');
  CHECK(decode(b, d));
  CHECK_EQ(d.h.seq, 123456); CHECK_EQ(d.h.mono_ms, 0xFFFFFF00u); CHECK_EQ(d.h.flags0, 17);
  CHECK_EQ(d.obs.lat_e7, -899999999); CHECK_EQ(d.obs.lon_e7, 1799999999); CHECK_EQ(d.obs.alt_cm, -12345);
  CHECK_EQ(d.obs.speed_cmps, 65535); CHECK_EQ(d.obs.course_cdeg, 35999); CHECK_EQ(d.obs.hdop_x100, 9999);
  CHECK_EQ(d.obs.sats, 42); CHECK_EQ(d.obs.valid, 0x07FF); CHECK_EQ(d.obs.utc_ms_of_day, 86399999);
  // every single-bit flip in any byte must be detected (CRC-32 detects all 1- and 2-bit errors at this length)
  int undetected = 0;
  for (int i = 0; i < WFG_RECORD_SIZE; i++)
    for (int bit = 0; bit < 8; bit++) {
      uint8_t c[WFG_RECORD_SIZE];
      memcpy(c, b, sizeof(c));
      c[i] ^= (uint8_t)(1 << bit);
      if (decode(c, d)) undetected++;
    }
  CHECK_EQ(undetected, 0);
  // other types
  memset(&r, 0, sizeof(r));
  r.h.type = REC_CLOCK; r.clk.offset_ms = 1790000000000LL; r.clk.delta_ms = -3600000; r.clk.kind = CLOCK_JUMP;
  encode(r, b);
  CHECK(decode(b, d));
  CHECK_EQ(d.clk.offset_ms, 1790000000000LL); CHECK_EQ(d.clk.delta_ms, -3600000); CHECK_EQ(d.clk.kind, CLOCK_JUMP);
  memset(&r, 0, sizeof(r));
  r.h.type = REC_EVENT; r.ev.event_no = 3; r.ev.ref_fix_seq = 0xFFFFFFFF; r.ev.ref_fix_age_ms = 0xFFFFFFFF;
  encode(r, b);
  CHECK(decode(b, d));
  CHECK_EQ(d.ev.ref_fix_seq, 0xFFFFFFFFu); CHECK_EQ(d.ev.located, 0);
  memset(&r, 0, sizeof(r));
  r.h.type = REC_SESSION_END; r.end.reason = END_STORAGE_FULL; r.end.crc32_before = 0xDEADBEEF; r.end.n_clock = 2;
  encode(r, b);
  CHECK(decode(b, d));
  CHECK_EQ(d.end.crc32_before, 0xDEADBEEFu); CHECK_EQ(d.end.n_clock, 2);
  // unknown type is rejected even with a valid CRC
  b[2] = 99;
  uint32_t c = crc32(b, 44);
  b[44] = c; b[45] = c >> 8; b[46] = c >> 16; b[47] = c >> 24;
  CHECK(!decode(b, d));
}

static void test_nmea() {
  g_test = "nmea";
  int32_t v;
  CHECK(NmeaParser::parseLatLon("3112.34567", "N", true, v)); CHECK_EQ(v, 312057612);  // 31 + 12.34567/60
  CHECK(NmeaParser::parseLatLon("12127.00000", "E", false, v)); CHECK_EQ(v, 1214500000);
  CHECK(NmeaParser::parseLatLon("3352.1234", "S", true, v)); CHECK_EQ(v, -338687233);  // 33 + 52.1234/60 = 33.86872333
  CHECK(!NmeaParser::parseLatLon("3112.34567", "X", true, v));
  CHECK(!NmeaParser::parseLatLon("", "N", true, v));
  CHECK(!NmeaParser::parseLatLon("31612.0", "N", true, v));  // wrong degree width
  uint32_t t;
  CHECK(NmeaParser::parseTime("031217.50", t)); CHECK_EQ(t, (3 * 3600 + 12 * 60 + 17) * 1000 + 500);
  CHECK(NmeaParser::parseTime("235959", t)); CHECK_EQ(t, 86399000);
  CHECK(!NmeaParser::parseTime("", t));
  CHECK(!NmeaParser::parseTime("2460", t));
  uint32_t d;
  CHECK(NmeaParser::parseDate("031026", d)); CHECK_EQ(d, 20261003);
  CHECK(!NmeaParser::parseDate("320126", d));

  NmeaParser p;
  SimFix f{true, 31.2, 121.45, 12.3, 2.0, 45.5, 9, 0.9};
  auto L = epochLines(3 * 3600000 + 12 * 60000 + 17000, "031026", f);
  uint32_t now = 1000;
  for (auto& s : L) for (char c : s + "\r\n") p.feed(c, now++);
  CHECK(!p.hasEpoch());           // waits for quiet gap or next time
  CHECK(p.poll(now + 300));
  GnssEpoch e = p.takeEpoch();
  CHECK(e.pos_valid); CHECK(e.has_date); CHECK_EQ(e.utc_date, 20261003);
  CHECK_EQ(e.lat_e7, 312000000); CHECK_EQ(e.lon_e7, 1214500000);
  CHECK_EQ(e.alt_cm, 1230); CHECK_EQ(e.sats, 9); CHECK_EQ(e.hdop_x100, 90);
  CHECK_EQ(e.speed_cmps, 103);    // 2.000 kn = 1.0289 m/s
  CHECK_EQ(e.course_cdeg, 4550);
  CHECK(e.has_gsa); CHECK_EQ(e.fix_type, 3);
  CHECK_EQ(p.sentences_bad_checksum, 0);
  // corrupted checksum is counted and ignored
  std::string bad = L[0];
  bad[10] = bad[10] == '1' ? '2' : '1';
  p.feedLine(bad.c_str(), now);
  CHECK_EQ(p.sentences_bad_checksum, 1);
  CHECK(p.bad_checksum_since_take);
  // next-time sentence commits the previous epoch
  NmeaParser q;
  auto A = epochLines(1000, "031026", f), B = epochLines(2000, "031026", f);
  for (auto& s : A) q.feedLine(s.c_str(), 10);
  CHECK(!q.hasEpoch());
  CHECK(q.feedLine(B[0].c_str(), 1010));
  CHECK(q.hasEpoch());
  CHECK_EQ(q.takeEpoch().utc_ms_of_day, 1000);
  // no-fix epoch: time present, position invalid, no speed/course
  NmeaParser r;
  SimFix nf{false, 0, 0, 0, 0, 0, 3, 0};
  for (auto& s : epochLines(5000, "031026", nf)) r.feedLine(s.c_str(), 5);
  CHECK(r.poll(1000));
  GnssEpoch ne = r.takeEpoch();
  CHECK(!ne.pos_valid); CHECK(ne.has_time); CHECK(!ne.speed_valid); CHECK(!ne.course_valid); CHECK(!ne.hdop_valid);
  CHECK_EQ(ne.gga_quality, 0); CHECK_EQ(ne.fix_type, 1);
}

// ---------------------------------------------------------------- simulated recording
struct Sim {
  PosixStorage st;
  Logger lg;
  NmeaParser p;
  uint32_t now = 0;
  Sim(const std::string& dir, uint64_t cap, const LoggerConfig& c) : st(dir.c_str(), cap), lg(st, c) {}
  void step(uint32_t ms) {  // advance time in 50 ms ticks, polling as the firmware loop does
    for (uint32_t t = 0; t < ms; t += 50) {
      now += 50;
      if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
      lg.tick(now, &p);
    }
  }
  void sendEpoch(uint32_t utc_ms, const SimFix& f, bool time_known = true) {
    for (auto& s : epochLines(utc_ms, "031026", f, time_known)) {
      now += 5;
      if (p.feedLine(s.c_str(), now) && p.hasEpoch()) lg.onEpoch(p.takeEpoch(), now);
    }
  }
};

static bool testStatus(Status& t, void*) {
  t.vbat_pin_mv = 814;          // what analogReadMilliVolts would return
  t.vbat_factor_x1000 = 4900;   // nominal 390k/100k divider x calibration 1.000
  t.vbat_mv = (uint16_t)(814u * 4900u / 1000u);
  t.flags = ST_BATT_VALID | ST_GNSS_SEEN;
  return true;
}

static LoggerConfig testCfg() {
  LoggerConfig c;
  c.device_id = 0x1A2B3C4D;
  c.board_rev = 11;
  c.free_check_every_records = 1;  // check every record in tests
  return c;
}

// Produces the sample session used by phone_export/samples and returns its file name.
static std::string recordSampleSession(Sim& s, bool stop_cleanly) {
  const uint32_t utc0 = 3 * 3600000 + 30 * 60000;  // 03:30:00 UTC
  s.lg.begin();
  s.lg.setStatusSource(testStatus, nullptr);
  s.lg.tick(s.now, &s.p);
  CHECK(s.lg.start(MODE_WALK, s.now));
  std::string name = s.lg.currentName();
  // Event before any fix -> unlocated, no reference fix.
  s.step(300);
  CHECK(s.lg.markEvent(s.now - 100, 180, s.now));
  // 6 s: receiver talking, no fix, time not yet known (cold start)
  for (int k = 0; k < 6; k++) { s.sendEpoch(utc0 + k * 1000, SimFix{false, 0, 0, 0, 0, 0, k, 0}, false); s.step(1000 - 15); }
  // 40 s walking north-east at ~1.3 m/s with a fix
  double lat = 31.2001, lon = 121.4501;
  for (int k = 6; k < 46; k++) {
    lat += 0.0000085; lon += 0.0000095;
    s.sendEpoch(utc0 + k * 1000, SimFix{true, lat, lon, 8.0 + k * 0.05, 2.5, 47.0, 7 + k % 4, 1.1 + (k % 3) * 0.2});
    if (k == 20) { s.step(400); CHECK(s.lg.markEvent(s.now - 150, 220, s.now)); s.step(1000 - 15 - 400); continue; }
    s.step(1000 - 15);
  }
  // 8 s under a bridge/tunnel: receiver reports no fix (time still known)
  for (int k = 46; k < 54; k++) {
    lat += 0.0000060; lon += 0.0000140;  // walker keeps moving (turning east) while there is no fix
    s.sendEpoch(utc0 + k * 1000, SimFix{false, 0, 0, 0, 0, 0, 2, 0});
    if (k == 50) { s.step(300); CHECK(s.lg.markEvent(s.now - 100, 200, s.now)); s.step(1000 - 15 - 300); continue; }
    s.step(1000 - 15);
  }
  // 5 s of no NMEA at all (UART silent / receiver reset) -> NO_NMEA_DATA rows
  s.step(5000);
  lat += 0.0000300; lon += 0.0000700;
  // 20 s more fixes, with the GNSS clock jumping +3 s once (simulates leap/rollover correction)
  for (int k = 59; k < 79; k++) {
    lat += 0.0000090; lon += 0.0000080;
    uint32_t utc = utc0 + k * 1000 + (k >= 70 ? 3000 : 0);
    s.sendEpoch(utc, SimFix{true, lat, lon, 10.0, 2.4, 42.0, 10, 0.8});
    s.step(1000 - 15);
  }
  if (stop_cleanly) CHECK(s.lg.stop(END_USER_STOP, s.now));
  return name;
}

static int countType(Storage& st, const char* name, uint8_t type, int nofix_reason = -1) {
  FILE* f = st.open(name, "rb");
  uint8_t b[WFG_RECORD_SIZE];
  Record r;
  int n = 0;
  while (fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE)
    if (decode(b, r) && r.h.type == type && (nofix_reason < 0 || r.obs.nofix_reason == nofix_reason)) n++;
  st.close(f);
  return n;
}

static void test_session_and_export(const char* sample_out) {
  g_test = "session_and_export";
  std::string dir = freshDir("fs_session");
  Sim s(dir, 6750208, testCfg());  // simulated 6.44 MiB LittleFS (deterministic STATUS free-space values)
  std::string name = recordSampleSession(s, true);
  IntegrityReport rep = Logger::checkSession(s.st, name.c_str());
  CHECK(rep.ok());
  CHECK_STR(rep.status, "OK");
  CHECK_EQ(rep.n_fix, 60);
  CHECK_EQ(rep.n_events, 3);
  CHECK_EQ(rep.n_nofix, 4 + 8 + 5);  // cold start fillers (first after 1.5 s) + receiver no-fix + UART silent
  CHECK_EQ(countType(s.st, name.c_str(), REC_NOFIX, NOFIX_RECEIVER), 12);
  CHECK_EQ(countType(s.st, name.c_str(), REC_NOFIX, NOFIX_NO_DATA), 5);
  CHECK_EQ(rep.n_clock, 2);  // FIRST_UTC + JUMP
  CHECK_EQ(rep.n_status, 2); // at START and after 60 s
  CHECK_EQ(s.lg.nStatus(), 2);
  // movement mode stored once in the header
  Record r;
  uint8_t b[WFG_RECORD_SIZE];
  FILE* f = s.st.open(name.c_str(), "rb");
  CHECK(fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE);
  s.st.close(f);
  CHECK(decode(b, r));
  CHECK_EQ(r.start.movement_mode, MODE_WALK);
  // Max gap between consecutive observation rows <= 1.6 s (gaps are rows, not missing time)
  f = s.st.open(name.c_str(), "rb");
  uint32_t prev = 0, maxgap = 0;
  bool have = false;
  int located = 0, unlocated = 0, noref = 0;
  while (fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE) {
    decode(b, r);
    if (r.h.type == REC_FIX || r.h.type == REC_NOFIX) {
      if (have && r.h.mono_ms - prev > maxgap) maxgap = r.h.mono_ms - prev;
      prev = r.h.mono_ms; have = true;
    }
    if (r.h.type == REC_EVENT) {
      if (r.ev.located) located++; else unlocated++;
      if (r.ev.ref_fix_seq == 0xFFFFFFFF) noref++;
      if (!r.ev.located) CHECK(r.ev.lat_e7 == 0 && r.ev.lon_e7 == 0);  // no fabricated position
    }
  }
  s.st.close(f);
  CHECK(maxgap <= 1600);
  CHECK_EQ(located, 1);
  CHECK_EQ(unlocated, 2);
  CHECK_EQ(noref, 1);

  StrSink csv, gpx, gj;
  ExportStats sc, sg, sj;
  CHECK(export_session(s.st, name.c_str(), FMT_CSV, csv, &sc));
  CHECK(export_session(s.st, name.c_str(), FMT_GPX, gpx, &sg));
  CHECK(export_session(s.st, name.c_str(), FMT_GEOJSON, gj, &sj));
  CHECK_EQ(sc.fix_rows, 60);
  CHECK_EQ(sc.records, rep.n_records);
  CHECK_EQ(sg.segments, 2);  // fix gap splits the track
  CHECK_EQ(sj.segments, 2);
  // CSV: header + one line per record
  int lines = 0;
  for (char c : csv.s) if (c == '\n') lines++;
  CHECK_EQ(lines, (int)rep.n_records + 1);
  // every CSV line has the same number of columns as the header
  {
    size_t pos = 0;
    int hdr_cols = -1, bad_cols = 0;
    while (pos < csv.s.size()) {
      size_t e = csv.s.find('\n', pos);
      std::string ln = csv.s.substr(pos, e - pos);
      int cols = 1;
      for (char c : ln) if (c == ',') cols++;
      if (hdr_cols < 0) hdr_cols = cols; else if (cols != hdr_cols) bad_cols++;
      pos = e + 1;
    }
    CHECK_EQ(bad_cols, 0);
    CHECK_EQ(hdr_cols, 43);
  }
  CHECK(csv.s.find("WFG-1A2B3C4D-000001,WALK,owner_selected_on_device,") != std::string::npos);
  CHECK(csv.s.find(",NO_NMEA_DATA,") != std::string::npos);
  CHECK(csv.s.find(",RECEIVER_NO_FIX,") != std::string::npos);
  CHECK(csv.s.find(",FIRST_UTC,") != std::string::npos);
  CHECK(csv.s.find(",STATUS,") != std::string::npos);
  CHECK(csv.s.find(",3988,814,4.900,") != std::string::npos);
  CHECK(csv.s.find(",OWNER_BUTTON,,\n") != std::string::npos);
  CHECK(csv.s.find(",JUMP,") != std::string::npos);
  CHECK(csv.s.find("2026-10-03T03:30:06.000Z") != std::string::npos);
  CHECK(gpx.s.find("<trkseg>") != std::string::npos);
  CHECK(gpx.s.find("<wfg:unlocated_event") != std::string::npos);
  CHECK(gpx.s.find("<hdop>") != std::string::npos);
  CHECK(gj.s.find("\"located\":false") != std::string::npos);
  CHECK(gj.s.find("\"geometry\":null") != std::string::npos);
  // round-trip: exporter must be deterministic
  StrSink csv2;
  export_session(s.st, name.c_str(), FMT_CSV, csv2);
  CHECK(csv.s == csv2.s);

  if (sample_out) {
    std::string base = std::string(sample_out) + "/" + std::string(name.c_str(), 7);
    auto save = [](const std::string& p, const std::string& d) {
      FILE* o = fopen(p.c_str(), "wb");
      if (o) { fwrite(d.data(), 1, d.size(), o); fclose(o); }
    };
    std::string raw;
    f = s.st.open(name.c_str(), "rb");
    char tmp[4096];
    size_t n;
    while ((n = fread(tmp, 1, sizeof(tmp), f)) > 0) raw.append(tmp, n);
    s.st.close(f);
    save(base + "_WALK.wfg", raw);
    save(base + "_WALK.csv", csv.s);
    save(base + "_WALK.gpx", gpx.s);
    save(base + "_WALK.geojson", gj.s);
    char sha[65];
    s.lg.sha256File(name.c_str(), sha);
    save(base + "_WALK.wfg.sha256", std::string(sha) + "  " + std::string(name.c_str(), 7) + "_WALK.wfg\n");
  }
}

static void test_torn_tail_recovery(const char* sample_out) {
  g_test = "torn_tail_recovery";
  std::string dir = freshDir("fs_torn");
  long size_before = 0;
  std::string name;
  {
    Sim s(dir, 0, testCfg());
    name = recordSampleSession(s, false);  // never closed (simulated power loss)
    size_before = (long)s.lg.seq() * WFG_RECORD_SIZE;  // records accepted so far (stdio buffer not yet flushed)
    // write a partial record: power cut 20 bytes into the next record
    s.st.fail_after_bytes = 20;
    s.lg.markEvent(s.now, 100, s.now);  // append() sees a short write and tries to close; prevent that:
  }
  // The logger's short-write path truncates + writes END; emulate a true power loss instead by appending
  // a torn tail and removing the END record manually.
  {
    PosixStorage st(dir.c_str());
    long sz = st.size(name.c_str());
    // remove END if the short-write path managed to add one
    FILE* f = st.open(name.c_str(), "rb");
    fseek(f, sz - WFG_RECORD_SIZE, SEEK_SET);
    uint8_t b[WFG_RECORD_SIZE];
    Record r;
    CHECK(fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE);
    st.close(f);
    if (decode(b, r) && r.h.type == REC_SESSION_END) st.truncate(name.c_str(), sz - WFG_RECORD_SIZE);
    CHECK_EQ(st.size(name.c_str()), size_before);
    f = st.open(name.c_str(), "ab");
    uint8_t junk[29];
    for (int i = 0; i < 29; i++) junk[i] = (uint8_t)(0x57 + i);
    fwrite(junk, 1, sizeof(junk), f);
    st.close(f);
    IntegrityReport pre = Logger::checkSession(st, name.c_str());
    CHECK(!pre.ok());
    CHECK_EQ(pre.trailing_bytes, 29);
    CHECK(!pre.has_end);
    CHECK_STR(pre.status, "TORN_TAIL");
  }
  // Reboot: begin() must truncate the torn tail and append END(RECOVERED_ON_BOOT)
  {
    PosixStorage st(dir.c_str());
    Logger lg(st, testCfg());
    RecoveryItem items[4];
    int n = lg.begin(items, 4);
    CHECK_EQ(n, 1);
    CHECK_EQ(items[0].torn_bytes_removed, 29);
    CHECK(items[0].closed_now);
    CHECK(!items[0].unrecoverable);
    IntegrityReport rep = Logger::checkSession(st, name.c_str());
    CHECK(rep.ok());
    CHECK_STR(rep.status, "RECOVERED");
    CHECK_EQ(rep.end_reason, END_RECOVERED_ON_BOOT);
    CHECK_EQ(st.size(name.c_str()), size_before + WFG_RECORD_SIZE);
    // second boot: nothing more to recover, file unchanged; next session gets a new number
    Logger lg2(st, testCfg());
    CHECK_EQ(lg2.begin(), 0);
    CHECK_EQ(st.size(name.c_str()), size_before + WFG_RECORD_SIZE);
    CHECK(lg2.start(MODE_VEHICLE, 0));
    CHECK(std::string(lg2.currentName()) != name);
    lg2.stop(END_USER_STOP, 10);
    if (sample_out) {
      StrSink csv;
      export_session(st, name.c_str(), FMT_CSV, csv);
      FILE* o = fopen((std::string(sample_out) + "/S000001_WALK_recovered.csv").c_str(), "wb");
      if (o) { fwrite(csv.s.data(), 1, csv.s.size(), o); fclose(o); }
    }
  }
  // Corrupt header -> renamed to .bad (kept, never deleted)
  {
    std::string d2 = freshDir("fs_badhdr");
    PosixStorage st(d2.c_str());
    FILE* f = st.open("S000007.wfg", "wb");
    uint8_t z[100] = {0};
    fwrite(z, 1, sizeof(z), f);
    st.close(f);
    Logger lg(st, testCfg());
    RecoveryItem items[2];
    CHECK_EQ(lg.begin(items, 2), 1);
    CHECK(items[0].unrecoverable);
    CHECK(st.exists("S000007.bad"));
    CHECK_EQ(st.size("S000007.bad"), 100);
    CHECK_EQ(lg.nextSessionNo(), 8);  // number 7 is never reused
  }
}

static void test_storage_full() {
  g_test = "storage_full";
  std::string dir = freshDir("fs_full");
  LoggerConfig c = testCfg();
  c.reserve_bytes = 16384;
  const uint64_t cap = 128 * 1024;  // 128 KiB simulated filesystem
  PosixStorage st(dir.c_str(), cap);
  Logger lg(st, c);
  lg.begin();
  // A previous, unexported session that must survive
  CHECK(lg.start(MODE_VEHICLE, 0));
  std::string first = lg.currentName();
  NmeaParser p;
  uint32_t now = 0, utc = 3600000;
  for (int k = 0; k < 300; k++) {
    for (auto& s : epochLines(utc + k * 1000, "031026", SimFix{true, 31.2 + k * 1e-5, 121.4, 5, 20, 90, 8, 1.0}))
      p.feedLine(s.c_str(), now += 5);
    now += 985;
    if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
  }
  CHECK(lg.stop(END_USER_STOP, now));
  long first_size = st.size(first.c_str());
  char first_sha[65];
  lg.sha256File(first.c_str(), first_sha);
  // Record until full
  CHECK(lg.start(MODE_WALK, now));
  std::string second = lg.currentName();
  int k = 0;
  while (lg.state() == LS_RECORDING && k < 100000) {
    for (auto& s : epochLines(utc + (k % 80000) * 1000, "031026", SimFix{true, 31.3, 121.5, 5, 1, 0, 8, 1.0}))
      p.feedLine(s.c_str(), now += 5);
    now += 985;
    if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
    lg.tick(now, &p);
    k++;
  }
  CHECK_EQ(lg.state(), LS_FULL);
  CHECK(k < 100000);
  IntegrityReport rep = Logger::checkSession(st, second.c_str());
  CHECK(rep.ok());
  CHECK_EQ(rep.end_reason, END_STORAGE_FULL);
  CHECK(rep.n_fix > 100);  // it used the space instead of an arbitrary cap
  // The earlier session is untouched
  char sha_now[65];
  lg.sha256File(first.c_str(), sha_now);
  CHECK_EQ(st.size(first.c_str()), first_size);
  CHECK_STR(sha_now, first_sha);
  // Cannot start a new session while full
  lg.clearFull();
  CHECK(!lg.start(MODE_WALK, now));
  CHECK_EQ(lg.state(), LS_FULL);
  // Delete is refused without export confirmation, with a wrong hash, and for the wrong file
  CHECK(!lg.deleteConfirmedSession(first.c_str(), first_sha));
  CHECK(!lg.confirmExport(first.c_str(), "00000000000000000000000000000000000000000000000000000000000000ff", "usb"));
  CHECK(!lg.deleteConfirmedSession(first.c_str(), first_sha));
  // Proper flow: confirm (hash matches) -> delete -> space available -> recording possible again
  CHECK(lg.confirmExport(first.c_str(), first_sha, "usb"));
  CHECK(lg.isExportConfirmed(first.c_str()));
  CHECK(!lg.deleteConfirmedSession(first.c_str(), "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"));
  CHECK(lg.deleteConfirmedSession(first.c_str(), first_sha));
  CHECK(!st.exists(first.c_str()));
  CHECK(st.exists(second.c_str()));
  CHECK_EQ(lg.state(), LS_IDLE);
  CHECK(lg.start(MODE_WALK, now));
  lg.stop(END_USER_STOP, now + 10);
  // Hard ENOSPC mid-record (free-space check too coarse): partial record removed, session closed cleanly
  std::string d2 = freshDir("fs_enospc");
  PosixStorage st2(d2.c_str(), 32 * 1024);
  LoggerConfig c2 = testCfg();
  c2.reserve_bytes = 0;  // disable soft check, rely on the short write
  c2.free_check_every_records = 1000000;
  Logger lg2(st2, c2);
  lg2.begin();
  CHECK(lg2.start(MODE_WALK, 0));
  std::string n2 = lg2.currentName();
  NmeaParser p2;
  now = 0;
  k = 0;
  while (lg2.state() == LS_RECORDING && k < 10000) {
    for (auto& s : epochLines(utc + k * 1000, "031026", SimFix{true, 31.3, 121.5, 5, 1, 0, 8, 1.0}))
      p2.feedLine(s.c_str(), now += 5);
    now += 985;
    if (p2.poll(now)) lg2.onEpoch(p2.takeEpoch(), now);
    k++;
  }
  CHECK_EQ(lg2.state(), LS_FULL);
  IntegrityReport r2 = Logger::checkSession(st2, n2.c_str());
  CHECK_EQ(r2.trailing_bytes, 0);
  CHECK_EQ(r2.n_crc_errors, 0);
  CHECK(r2.has_start);
  // Either closed with STORAGE_FULL, or (if not even 48 bytes were left) left OPEN for boot recovery
  CHECK(r2.ok() || std::string(r2.status) == "OPEN");
}

static void test_export_confirm_invalidated_by_change() {
  g_test = "export_confirm_invalidated";
  std::string dir = freshDir("fs_confirm");
  PosixStorage st(dir.c_str());
  Logger lg(st, testCfg());
  lg.begin();
  CHECK(lg.start(MODE_UNKNOWN, 0));
  std::string n = lg.currentName();
  // cannot confirm the active session
  char sha[65];
  lg.sha256File(n.c_str(), sha);
  CHECK(!lg.confirmExport(n.c_str(), sha, "wifi"));
  lg.stop(END_USER_STOP, 1000);
  lg.sha256File(n.c_str(), sha);
  CHECK(lg.confirmExport(n.c_str(), sha, "wifi"));
  CHECK(lg.isExportConfirmed(n.c_str()));
  // any modification of the file invalidates the confirmation
  FILE* f = st.open(n.c_str(), "ab");
  fputc('x', f);
  st.close(f);
  CHECK(!lg.isExportConfirmed(n.c_str()));
  CHECK(!lg.deleteConfirmedSession(n.c_str(), sha));
  CHECK(st.exists(n.c_str()));
}

static void test_button() {
  g_test = "button";
  ButtonConfig bc;
  Button b(bc);
  b.begin(false, 0);
  uint32_t t = 0;
  auto press = [&](uint32_t hold) -> Gesture {
    Gesture g = G_NONE, x;
    for (uint32_t i = 0; i < hold; i += 10) { t += 10; if ((x = b.update(true, t)) != G_NONE) g = x; }
    for (uint32_t i = 0; i < 60; i += 10) { t += 10; if ((x = b.update(false, t)) != G_NONE) g = x; }
    return g;
  };
  CHECK_EQ(press(150), G_SHORT);
  CHECK_EQ(press(2600), G_LONG);
  CHECK_EQ(press(6500), G_VERY_LONG);
  CHECK_EQ(press(10), G_NONE);  // bounce shorter than debounce is ignored
  // bouncy contact: chatter on press is filtered
  Gesture g = G_NONE, x;
  for (int i = 0; i < 6; i++) { t += 5; b.update(i % 2 == 0, t); }
  for (int i = 0; i < 20; i++) { t += 10; if ((x = b.update(true, t)) != G_NONE) g = x; }
  for (int i = 0; i < 6; i++) { t += 10; if ((x = b.update(false, t)) != G_NONE) g = x; }
  CHECK_EQ(g, G_SHORT);
  // held through reset/boot: ignored until released, no gesture
  Button b2(bc);
  b2.begin(true, 0);
  Gesture g2 = G_NONE;
  for (uint32_t i = 0; i < 8000; i += 10) if ((x = b2.update(true, i)) != G_NONE) g2 = x;
  for (uint32_t i = 8000; i < 8100; i += 10) if ((x = b2.update(false, i)) != G_NONE) g2 = x;
  CHECK_EQ(g2, G_NONE);
  CHECK(!b2.isDown());
  // double press (export mode only)
  Button b3(bc);
  b3.begin(false, 0);
  b3.setDoubleEnabled(true);
  t = 0;
  Gesture got = G_NONE;
  auto feed = [&](bool lvl, uint32_t dur) { for (uint32_t i = 0; i < dur; i += 10) { t += 10; Gesture y = b3.update(lvl, t); if (y) got = y; } };
  feed(true, 100); feed(false, 150); feed(true, 100); feed(false, 600);
  CHECK_EQ(got, G_DOUBLE);
  got = G_NONE;
  feed(true, 100); feed(false, 600);
  CHECK_EQ(got, G_SHORT);  // single press reported after the double window
}

static void test_proto(const char* sample_out) {
  g_test = "usb_proto";
  std::string dir = freshDir("fs_proto");
  Sim s(dir, 0, testCfg());
  std::string name = recordSampleSession(s, true);
  StrSink out;
  Proto pr(s.lg, s.st, out, "TEST", 0x1A2B3C4D, "0.1.0");
  pr.handleLine("HELLO", 0, MODE_WALK);
  CHECK(out.s.find("OK HELLO fw=0.1.0") == 0);
  out.s.clear();
  pr.handleLine("LIST", 0, MODE_WALK);
  CHECK(out.s.find("SESS S000001.wfg ") == 0);
  CHECK(out.s.find("OK LIST 1") != std::string::npos);
  out.s.clear();
  pr.handleLine(("DUMP " + name).c_str(), 0, MODE_WALK);
  CHECK(out.s.find("BEGIN S000001.wfg ") == 0);
  CHECK(out.s.find("OK DUMP S000001.wfg") != std::string::npos);
  if (sample_out) {
    FILE* o = fopen((std::string(sample_out) + "/usb_dump_transcript.txt").c_str(), "wb");
    if (o) { fwrite(out.s.data(), 1, out.s.size(), o); fclose(o); }
  }
  char sha[65];
  s.lg.sha256File(name.c_str(), sha);
  out.s.clear();
  pr.handleLine(("DELETE " + name + " " + sha).c_str(), 100, MODE_WALK);
  CHECK(out.s.find("ERR DELETE S000001.wfg not-export-confirmed") == 0);
  out.s.clear();
  pr.handleLine(("CONFIRM " + name + " " + sha).c_str(), 100, MODE_WALK);
  CHECK(out.s.find("OK CONFIRM") == 0);
  out.s.clear();
  pr.handleLine(("DELETE " + name + " " + sha).c_str(), 100, MODE_WALK);
  CHECK(out.s.find("PENDING DELETE") == 0);
  CHECK(pr.hasPendingDelete(200));
  // timeout without the physical button -> nothing deleted
  CHECK(!pr.hasPendingDelete(100 + 31000));
  CHECK(s.st.exists(name.c_str()));
  // with the button confirmation
  pr.handleLine(("DELETE " + name + " " + sha).c_str(), 40000, MODE_WALK);
  pr.confirmPendingDelete(41000);
  CHECK(!s.st.exists(name.c_str()));
  CHECK(out.s.find("OK DELETE S000001.wfg") != std::string::npos);
}

static void test_clock_utils() {
  g_test = "clock_utils";
  CHECK_EQ(utc_epoch_ms(19700101, 0), 0);
  CHECK_EQ(utc_epoch_ms(20000301, 0), 951868800000LL);
  uint32_t ymd, ms;
  epoch_ms_to_utc(utc_epoch_ms(20261003, 12345678), ymd, ms);
  CHECK_EQ(ymd, 20261003); CHECK_EQ(ms, 12345678);
  epoch_ms_to_utc(utc_epoch_ms(20281231, 86399999) + 1, ymd, ms);
  CHECK_EQ(ymd, 20290101); CHECK_EQ(ms, 0);
  char b[40];
  fmt_e7(-5, b); CHECK_STR(b, "-0.0000005");
  fmt_e7(1214500000, b); CHECK_STR(b, "121.4500000");
  fmt_centi(-5, b); CHECK_STR(b, "-0.05");
}

// ---- R4: no 64-session cap ----
struct ListCount { int n; uint32_t last; bool sorted; };
static void list_count_cb(const SessionInfo& si, void* ctx) {
  ListCount* c = (ListCount*)ctx;
  if (c->n && si.session_no <= c->last) c->sorted = false;
  c->last = si.session_no;
  c->n++;
}
static void test_many_sessions() {
  g_test = "many_sessions_150";
  std::string dir = freshDir("fs_many");
  PosixStorage st(dir.c_str());
  LoggerConfig c = testCfg();
  {
    Logger lg(st, c);
    lg.begin();
    NmeaParser p;
    uint32_t now = 0;
    for (int i = 0; i < 150; i++) {
      CHECK(lg.start(i % 2 ? MODE_VEHICLE : MODE_WALK, now));
      for (int k = 0; k < 3; k++) {
        for (auto& ln : epochLines(3600000 + (i * 10 + k) * 1000, "031026", SimFix{true, 31.2, 121.4, 5, 1, 0, 8, 1.0}))
          p.feedLine(ln.c_str(), now += 5);
        now += 985;
        if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
      }
      CHECK(lg.stop(END_USER_STOP, now));
    }
    // first 10 sessions are export-confirmed
    for (int i = 1; i <= 10; i++) {
      char n[20], sha[65];
      snprintf(n, sizeof(n), "S%06d.wfg", i);
      lg.sha256File(n, sha);
      CHECK(lg.confirmExport(n, sha, "usb"));
    }
  }
  // Damage two sessions beyond index 64: S000100 gets a torn tail, S000150 loses its END (power cut)
  auto chopEnd = [&](const char* n, int junk) {
    long sz = st.size(n);
    st.truncate(n, sz - WFG_RECORD_SIZE);
    if (junk) { FILE* f = st.open(n, "ab"); for (int j = 0; j < junk; j++) fputc(0x5A, f); st.close(f); }
  };
  chopEnd("S000100.wfg", 13);
  chopEnd("S000150.wfg", 0);
  CHECK_STR(Logger::checkSession(st, "S000100.wfg").status, "TORN_TAIL");
  CHECK_STR(Logger::checkSession(st, "S000150.wfg").status, "OPEN");
  Logger lg(st, c);
  RecoveryItem items[4];
  CHECK_EQ(lg.begin(items, 4), 2);  // both found although they are past the old 64-file limit
  CHECK_STR(Logger::checkSession(st, "S000100.wfg").status, "RECOVERED");
  CHECK_STR(Logger::checkSession(st, "S000150.wfg").status, "RECOVERED");
  ListCount lc{0, 0, true};
  CHECK_EQ(lg.forEachSession(list_count_cb, &lc), 150);
  CHECK_EQ(lc.n, 150);
  CHECK(lc.sorted);
  CHECK_EQ(lc.last, 150);
  CHECK_EQ(lg.countUnexported(), 140);
  CHECK_EQ(lg.nextSessionNo(), 151);
  StrSink out;
  Proto pr(lg, st, out, "TEST", c.device_id, "0.2.0");
  pr.handleLine("LIST", 0, MODE_WALK);
  int sess_lines = 0;
  for (size_t pos = 0; (pos = out.s.find("SESS S", pos)) != std::string::npos; pos++) sess_lines++;
  CHECK_EQ(sess_lines, 150);
  CHECK(out.s.find("OK LIST 150") != std::string::npos);
  CHECK(out.s.find("SESS S000150.wfg") != std::string::npos);
}

// ---- R3: auto-resume after unexpected reset ----
static void test_resume(const char* sample_out) {
  g_test = "auto_resume";
  ResumeNvs nv;
  ResumeInputs in;
  CHECK_EQ(decide_resume(nv, in), RA_NONE);              // clean stop: nothing to do
  nv.active = true; nv.mode = MODE_VEHICLE; nv.session_no = 5;
  CHECK_EQ(decide_resume(nv, in), RA_RESUME);
  in.batt_mv = -1; CHECK_EQ(decide_resume(nv, in), RA_RESUME);   // unknown battery does not block
  in.batt_mv = 3300; CHECK_EQ(decide_resume(nv, in), RA_BLOCKED_LOW_BATT);
  in.batt_mv = 3900; CHECK_EQ(decide_resume(nv, in), RA_RESUME);
  in.storage_full = true; CHECK_EQ(decide_resume(nv, in), RA_BLOCKED_FULL);
  in.storage_full = false; in.fs_ok = false; CHECK_EQ(decide_resume(nv, in), RA_BLOCKED_FS);
  in.fs_ok = true; nv.quick_fail_count = 2; CHECK_EQ(decide_resume(nv, in), RA_RESUME);
  nv.quick_fail_count = 3; CHECK_EQ(decide_resume(nv, in), RA_GIVE_UP_LOOP);

  // Integration: session cut by a reset is recovered and a NEW attributed session starts; nothing is merged.
  std::string dir = freshDir("fs_resume");
  PosixStorage st(dir.c_str());
  std::string first;
  {
    Sim s(dir, 0, testCfg());
    first = recordSampleSession(s, false);  // still recording when the "reset" happens
  }
  long first_size_before_recovery = st.size(first.c_str());
  Logger lg(st, testCfg());
  CHECK_EQ(lg.begin(), 1);
  ResumeNvs nv2; nv2.active = true; nv2.mode = MODE_WALK; nv2.session_no = (uint32_t)atoi(first.c_str() + 1);
  ResumeInputs in2;
  CHECK_EQ(decide_resume(nv2, in2), RA_RESUME);
  CHECK(lg.start(nv2.mode, 10, START_AUTO_RESUMED_AFTER_RESET, nv2.session_no, 9 /* BROWNOUT */));
  std::string second = lg.currentName();
  CHECK(second != first);
  lg.stop(END_USER_STOP, 2000);
  IntegrityReport r1 = Logger::checkSession(st, first.c_str());
  CHECK_STR(r1.status, "RECOVERED");
  CHECK(st.size(first.c_str()) >= first_size_before_recovery);  // old file only gained its END record
  IntegrityReport r2 = Logger::checkSession(st, second.c_str());
  CHECK_STR(r2.status, "OK");
  uint8_t b[WFG_RECORD_SIZE];
  Record r;
  FILE* f = st.open(second.c_str(), "rb");
  CHECK(fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE);
  st.close(f);
  CHECK(decode(b, r));
  CHECK_EQ(r.start.format_version, 2);
  CHECK_EQ(r.start.start_reason, START_AUTO_RESUMED_AFTER_RESET);
  CHECK_EQ(r.start.resumed_from_session_no, nv2.session_no);
  CHECK_EQ(r.start.reset_reason, 9);
  CHECK_EQ(r.start.movement_mode, MODE_WALK);
  StrSink csv, gpx, gj;
  export_session(st, second.c_str(), FMT_CSV, csv);
  export_session(st, second.c_str(), FMT_GPX, gpx);
  export_session(st, second.c_str(), FMT_GEOJSON, gj);
  CHECK(csv.s.find(",AUTO_RESUMED_AFTER_RESET,WFG-1A2B3C4D-000001,") != std::string::npos);
  CHECK(gpx.s.find("start_reason=AUTO_RESUMED_AFTER_RESET resumed_from=WFG-1A2B3C4D-000001") != std::string::npos);
  CHECK(gj.s.find("\"resumed_from_session_id\":\"WFG-1A2B3C4D-000001\"") != std::string::npos);
  // the old session's CSV still says OWNER_BUTTON and has its own id (not merged)
  StrSink c1;
  export_session(st, first.c_str(), FMT_CSV, c1);
  CHECK(c1.s.find("WFG-1A2B3C4D-000002") == std::string::npos);
  if (sample_out) {  // sample of an auto-resumed session for the Python byte-identity test
    std::string base = std::string(sample_out) + "/S000002_WALK_autoresumed";
    std::string raw;
    FILE* fr = st.open(second.c_str(), "rb");
    char tmp[4096];
    size_t nn;
    while ((nn = fread(tmp, 1, sizeof(tmp), fr)) > 0) raw.append(tmp, nn);
    st.close(fr);
    for (auto& pr : {std::make_pair(std::string(".wfg"), raw), std::make_pair(std::string(".csv"), csv.s),
                     std::make_pair(std::string(".gpx"), gpx.s), std::make_pair(std::string(".geojson"), gj.s)}) {
      FILE* o = fopen((base + pr.first).c_str(), "wb");
      if (o) { fwrite(pr.second.data(), 1, pr.second.size(), o); fclose(o); }
    }
  }
}

// ---- format v1 files remain readable ----
static void test_read_v1(const char* sample_out) {
  g_test = "read_format_v1";
  if (!sample_out) return;
  std::string src = std::string(sample_out) + "/format_v1/S000001_WALK_v1.wfg";
  FILE* in = fopen(src.c_str(), "rb");
  CHECK(in != nullptr);
  if (!in) return;
  std::string dir = freshDir("fs_v1");
  std::string dst = dir + "/S000001.wfg";
  FILE* out = fopen(dst.c_str(), "wb");
  char buf[4096];
  size_t n;
  while ((n = fread(buf, 1, sizeof(buf), in)) > 0) fwrite(buf, 1, n, out);
  fclose(in); fclose(out);
  PosixStorage st(dir.c_str());
  IntegrityReport rep = Logger::checkSession(st, "S000001.wfg");
  CHECK_STR(rep.status, "OK");
  CHECK_EQ(rep.n_fix, 60);
  CHECK_EQ(rep.n_status, 0);
  uint8_t b[WFG_RECORD_SIZE];
  Record r;
  FILE* f = st.open("S000001.wfg", "rb");
  CHECK(fread(b, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE);
  st.close(f);
  CHECK(decode(b, r));
  CHECK_EQ(r.start.format_version, 1);
  CHECK_EQ(r.start.start_reason, START_OWNER_BUTTON);
  CHECK_EQ(r.start.resumed_from_session_no, 0);
  StrSink csv;
  ExportStats sx;
  CHECK(export_session(st, "S000001.wfg", FMT_CSV, csv, &sx));
  CHECK_EQ(sx.fix_rows, 60);
  CHECK(csv.s.find(",OWNER_BUTTON,,\n") != std::string::npos);
}

// ================================================================ LIVE lines (firmware 0.3.0)
struct CapLiveSink : LiveSink {
  std::string s;
  size_t avail = 1u << 20;
  bool consume = false;  // write() uses up avail, like a transmit buffer that fills
  bool fail = false;     // write() reports a failure
  int avail_calls = 0, writes = 0;
  size_t availableForWrite() override { avail_calls++; return avail; }
  bool write(const char* p, size_t n) override {
    writes++;
    if (fail) return false;
    s.append(p, n);
    if (consume) avail = avail >= n ? avail - n : 0;
    return true;
  }
};

static std::vector<std::string> splitLines(const std::string& s) {  // keeps each '\n'
  std::vector<std::string> v;
  size_t pos = 0;
  while (pos < s.size()) {
    size_t e = s.find('\n', pos);
    if (e == std::string::npos) { v.push_back(s.substr(pos)); break; }
    v.push_back(s.substr(pos, e - pos + 1));
    pos = e + 1;
  }
  return v;
}
static std::string hexOf(const uint8_t* b, size_t n) {
  static const char* d = "0123456789abcdef";
  std::string h;
  for (size_t i = 0; i < n; i++) { h += d[b[i] >> 4]; h += d[b[i] & 15]; }
  return h;
}
static std::string fileBytes(Storage& st, const char* name) {
  std::string raw;
  FILE* f = st.open(name, "rb");
  if (!f) return raw;
  char tmp[4096];
  size_t n;
  while ((n = fread(tmp, 1, sizeof(tmp), f)) > 0) raw.append(tmp, n);
  st.close(f);
  return raw;
}
// Raw value of "key" in a #J line (up to the next ',' or '}'), "" if the key is missing.
static std::string jfield(const std::string& line, const char* key) {
  std::string k = std::string("\"") + key + "\":";
  size_t p = line.find(k);
  if (p == std::string::npos) return "";
  p += k.size();
  size_t e = line.find_first_of(",}", p);
  return line.substr(p, e == std::string::npos ? std::string::npos : e - p);
}
static bool cleanLine(const std::string& l) {  // ASCII, one '\n' at the end, at most 320 bytes, starts with '#'
  if (l.empty() || l.size() > kLiveMaxLine || l[0] != '#' || l.back() != '\n') return false;
  for (size_t i = 0; i + 1 < l.size(); i++)
    if ((uint8_t)l[i] < 0x20 || (uint8_t)l[i] > 0x7E) return false;
  return true;
}
static std::string epLine(const GnssEpoch& e, uint8_t st, int32_t ss, uint8_t md) {
  char b[400];
  size_t n = Live::fmtEpoch(b, sizeof(b), e, st, ss, md);
  return std::string(b, n);
}
static GnssEpoch specEpoch() {  // the values of the "ep" example in DEMO_SPEC section 5
  GnssEpoch e;
  e.has_time = true; e.utc_ms_of_day = (8 * 3600 + 16 * 60 + 47) * 1000u;
  e.has_date = true; e.utc_date = 20261014;
  e.has_gga = true; e.gga_quality = 1;
  e.has_rmc = true; e.rmc_active = true;
  e.has_gsa = true; e.fix_type = 3;
  e.pos_valid = true; e.lat_e7 = 312092653; e.lon_e7 = 1214389532;
  e.alt_valid = true; e.alt_cm = 1240;
  e.sats_valid = true; e.sats = 11;
  e.hdop_valid = true; e.hdop_x100 = 90;
  e.speed_valid = true; e.speed_cmps = 8;
  e.course_valid = true; e.course_cdeg = 34300;
  e.first_mono_ms = 741230; e.last_mono_ms = 741400;
  return e;
}
static void encRec(uint8_t* b, uint8_t type, uint32_t seq, uint32_t session_no = 0, uint8_t reason = 0) {
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = type; r.h.seq = seq; r.h.mono_ms = 1000 + seq;
  if (type == REC_SESSION_START) {
    r.start.session_no = session_no; r.start.format_version = WFG_FORMAT_VERSION; r.start.record_size = WFG_RECORD_SIZE;
  }
  if (type == REC_SESSION_END) { r.end.reason = reason; r.end.n_records_before = seq; }
  if (type == REC_FIX || type == REC_NOFIX) r.obs.utc_ms_of_day = 0xFFFFFFFF;
  encode(r, b);
}

static void test_live_formats() {
  g_test = "live_formats";
  // ep: the example line of DEMO_SPEC section 5, byte for byte
  CHECK_STR(epLine(specEpoch(), LS_RECORDING, 14, MODE_WALK),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":741230,\"utc\":\"2026-10-14T08:16:47.000Z\",\"fix\":1,\"q\":1,\"ft\":\"3D\","
            "\"su\":11,\"hd\":0.9,\"la\":31.2092653,\"lo\":121.4389532,\"al\":12.4,\"sp\":0.08,\"co\":343.0,\"nr\":null,"
            "\"rs\":\"RECORDING\",\"ss\":14,\"md\":\"WALK\"}\n");
  // ep: nothing known
  GnssEpoch z;
  CHECK_STR(epLine(z, LS_IDLE, -1, MODE_UNKNOWN),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":0,\"utc\":null,\"fix\":0,\"q\":null,\"ft\":null,\"su\":null,\"hd\":null,"
            "\"la\":null,\"lo\":null,\"al\":null,\"sp\":null,\"co\":null,\"nr\":\"RECEIVER_NO_FIX\",\"rs\":\"IDLE\","
            "\"ss\":null,\"md\":\"UNKNOWN\"}\n");
  // ep: south and west, negative altitude, rounding to one decimal, 359.95 degrees -> 0.0, time without a date
  GnssEpoch w = specEpoch();
  w.has_date = false;
  w.lat_e7 = -338687233; w.lon_e7 = -5; w.alt_cm = -1245;
  w.hdop_x100 = 95; w.course_cdeg = 35995; w.speed_cmps = 65535;
  w.gga_quality = 2; w.fix_type = 2; w.sats = 0; w.first_mono_ms = 4294967295u;
  CHECK_STR(epLine(w, LS_FULL, -1, MODE_VEHICLE),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":4294967295,\"utc\":null,\"fix\":1,\"q\":2,\"ft\":\"2D\",\"su\":0,\"hd\":1.0,"
            "\"la\":-33.8687233,\"lo\":-0.0000005,\"al\":-12.5,\"sp\":655.35,\"co\":0.0,\"nr\":null,\"rs\":\"FULL\","
            "\"ss\":null,\"md\":\"VEHICLE\"}\n");
  // ep: receiver answers without a position (Logger::onEpoch writes NOFIX with RECEIVER_NO_FIX)
  GnssEpoch nf = specEpoch();
  nf.pos_valid = false; nf.alt_valid = false; nf.speed_valid = false; nf.course_valid = false; nf.hdop_valid = false;
  nf.gga_quality = 0; nf.fix_type = 1; nf.sats = 3; nf.rmc_active = false;
  CHECK_STR(epLine(nf, LS_ERROR, 7, MODE_WALK),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":741230,\"utc\":\"2026-10-14T08:16:47.000Z\",\"fix\":0,\"q\":0,\"ft\":\"NONE\","
            "\"su\":3,\"hd\":null,\"la\":null,\"lo\":null,\"al\":null,\"sp\":null,\"co\":null,"
            "\"nr\":\"RECEIVER_NO_FIX\",\"rs\":\"ERROR\",\"ss\":7,\"md\":\"WALK\"}\n");
  // ep: single fields null on their own
  GnssEpoch a = specEpoch();
  a.alt_valid = false; a.gga_quality = 0xFF; a.has_gsa = false; a.sats_valid = false;
  std::string al = epLine(a, LS_IDLE, -1, MODE_WALK);
  CHECK_STR(jfield(al, "al"), "null"); CHECK_STR(jfield(al, "q"), "null"); CHECK_STR(jfield(al, "ft"), "null");
  CHECK_STR(jfield(al, "su"), "null"); CHECK_STR(jfield(al, "la"), "31.2092653"); CHECK_STR(jfield(al, "fix"), "1");
  // ep: 7 decimals straight from the e7 integers
  struct { int32_t la, lo; const char* sla; const char* slo; } pos[] = {
      {0, 0, "0.0000000", "0.0000000"},
      {1, -1, "0.0000001", "-0.0000001"},
      {900000000, 1800000000, "90.0000000", "180.0000000"},
      {-900000000, -1800000000, "-90.0000000", "-180.0000000"},
      {312092653, 1799999999, "31.2092653", "179.9999999"},
      {-10000000, 10000001, "-1.0000000", "1.0000001"}};
  for (auto& p : pos) {
    GnssEpoch e = specEpoch();
    e.lat_e7 = p.la; e.lon_e7 = p.lo;
    std::string l = epLine(e, LS_IDLE, -1, MODE_WALK);
    CHECK_STR(jfield(l, "la"), p.sla);
    CHECK_STR(jfield(l, "lo"), p.slo);
  }
  // ep: one decimal for altitude and HDOP (half away from zero), two for speed, course 0.0 to 359.9
  struct { int32_t v; const char* s; } alts[] = {{1240, "12.4"}, {1244, "12.4"}, {1245, "12.5"}, {-1244, "-12.4"},
                                               {-4, "0.0"}, {5, "0.1"}, {-5, "-0.1"}, {0, "0.0"}, {123456789, "1234567.9"}};
  for (auto& x : alts) { GnssEpoch e = specEpoch(); e.alt_cm = x.v; CHECK_STR(jfield(epLine(e, 0, -1, 1), "al"), x.s); }
  struct { int32_t v; const char* s; } hds[] = {{90, "0.9"}, {94, "0.9"}, {95, "1.0"}, {100, "1.0"}, {0, "0.0"}, {9999, "100.0"}};
  for (auto& x : hds) { GnssEpoch e = specEpoch(); e.hdop_x100 = (uint16_t)x.v; CHECK_STR(jfield(epLine(e, 0, -1, 1), "hd"), x.s); }
  struct { int32_t v; const char* s; } sps[] = {{0, "0.00"}, {8, "0.08"}, {103, "1.03"}, {65535, "655.35"}};
  for (auto& x : sps) { GnssEpoch e = specEpoch(); e.speed_cmps = (uint16_t)x.v; CHECK_STR(jfield(epLine(e, 0, -1, 1), "sp"), x.s); }
  struct { int32_t v; const char* s; } cdegs[] = {{0, "0.0"}, {4, "0.0"}, {5, "0.1"}, {34300, "343.0"}, {35994, "359.9"},
                                                {35995, "0.0"}, {35999, "0.0"}};
  for (auto& x : cdegs) { GnssEpoch e = specEpoch(); e.course_cdeg = (uint16_t)x.v; CHECK_STR(jfield(epLine(e, 0, -1, 1), "co"), x.s); }

  char lb[400];
  size_t ln;
  // rec: seq, record type, file size, CRC-32 as 8 lowercase hex digits (u32 at bytes 44..47), the 48 bytes in hex
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_FIX; r.h.flags0 = 3; r.h.seq = 701; r.h.mono_ms = 741230;
  r.obs.utc_date = 20261014; r.obs.utc_ms_of_day = 29807000; r.obs.lat_e7 = 312092653; r.obs.lon_e7 = 1214389532;
  r.obs.alt_cm = 1240; r.obs.speed_cmps = 8; r.obs.course_cdeg = 34300; r.obs.hdop_x100 = 90; r.obs.sats = 11;
  r.obs.gga_quality = 1; r.obs.fix_type = 3; r.obs.valid = V_TIME | V_DATE | V_POS | V_ALT;
  uint8_t b[WFG_RECORD_SIZE];
  encode(r, b);
  char crc8[16];
  snprintf(crc8, sizeof(crc8), "%08x", (unsigned)crc32(b, 44));
  ln = Live::fmtRecord(lb, sizeof(lb), b, 701, 33696);
  std::string want = std::string("#J {\"v\":1,\"t\":\"rec\",\"seq\":701,\"ty\":2,\"b\":33696,\"crc\":\"") + crc8 +
                     "\",\"hx\":\"" + hexOf(b, WFG_RECORD_SIZE) + "\"}\n";
  CHECK_STR(std::string(lb, ln), want);
  CHECK(want.find("\"hx\":\"57460203") != std::string::npos);  // "WF", type 2, flags0 3 as in the spec example
  CHECK_EQ(jfield(want, "hx").size(), 2 + 2 * WFG_RECORD_SIZE);
  for (uint32_t m = 0; m < 4000 && crc32(b, 44) >= 0x10000000u; m++) { r.h.mono_ms = m; encode(r, b); }
  CHECK(crc32(b, 44) < 0x10000000u);
  ln = Live::fmtRecord(lb, sizeof(lb), b, 0, 48);
  std::string c8 = jfield(std::string(lb, ln), "crc");
  CHECK_EQ(c8.size(), 10);  // a leading zero is kept: 8 digits plus quotes
  CHECK(c8.size() == 10 && c8[1] == '0');
  // st, ev, ss, se, drop, #N: the example lines of the spec and the null cases
  auto S = [&](size_t n) { return std::string(lb, n); };
  CHECK_STR(S(Live::fmtStatus(lb, sizeof(lb), 3912, 2310144)), "#J {\"v\":1,\"t\":\"st\",\"vb\":3912,\"ff\":2310144}\n");
  CHECK_STR(S(Live::fmtStatus(lb, sizeof(lb), -1, 2310144)), "#J {\"v\":1,\"t\":\"st\",\"vb\":null,\"ff\":2310144}\n");
  CHECK_STR(S(Live::fmtStatus(lb, sizeof(lb), -1, -1)), "#J {\"v\":1,\"t\":\"st\",\"vb\":null,\"ff\":null}\n");
  CHECK_STR(S(Live::fmtStatus(lb, sizeof(lb), 4100, 5000000000LL)), "#J {\"v\":1,\"t\":\"st\",\"vb\":4100,\"ff\":4294967295}\n");
  CHECK_STR(S(Live::fmtEvent(lb, sizeof(lb), 3, true)), "#J {\"v\":1,\"t\":\"ev\",\"n\":3,\"loc\":1}\n");
  CHECK_STR(S(Live::fmtEvent(lb, sizeof(lb), 1, false)), "#J {\"v\":1,\"t\":\"ev\",\"n\":1,\"loc\":0}\n");
  CHECK_STR(S(Live::fmtSessionStart(lb, sizeof(lb), 14, MODE_WALK, START_OWNER_BUTTON)),
            "#J {\"v\":1,\"t\":\"ss\",\"ss\":14,\"md\":\"WALK\",\"sr\":\"OWNER_BUTTON\"}\n");
  CHECK_STR(S(Live::fmtSessionStart(lb, sizeof(lb), 15, MODE_VEHICLE, START_AUTO_RESUMED_AFTER_RESET)),
            "#J {\"v\":1,\"t\":\"ss\",\"ss\":15,\"md\":\"VEHICLE\",\"sr\":\"AUTO_RESUMED_AFTER_RESET\"}\n");
  CHECK_STR(S(Live::fmtSessionEnd(lb, sizeof(lb), 14, END_USER_STOP, 993)),
            "#J {\"v\":1,\"t\":\"se\",\"ss\":14,\"er\":\"USER_STOP\",\"n\":993}\n");
  CHECK_STR(S(Live::fmtSessionEnd(lb, sizeof(lb), 14, -1, 992)), "#J {\"v\":1,\"t\":\"se\",\"ss\":14,\"er\":null,\"n\":992}\n");
  CHECK_STR(S(Live::fmtDrop(lb, sizeof(lb), 3)), "#J {\"v\":1,\"t\":\"drop\",\"n\":3}\n");
  const char* gga = "$GNGGA,081647.000,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,,*4B";  // as received, unchecked
  CHECK_STR(S(Live::fmtNmea(lb, sizeof(lb), gga)), std::string("#N ") + gga + "\n");
  std::string s100 = "$" + std::string(99, 'A'), s101 = "$" + std::string(100, 'A');
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), s100.c_str()), 3 + 100 + 1);
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), s101.c_str()), 0);
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), ""), 0);
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), nullptr), 0);
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), "$GN\tGGA"), 0);
  CHECK_EQ(Live::fmtNmea(lb, sizeof(lb), "$GN\xb5GGA"), 0);
}

static void test_live_limits() {
  g_test = "live_320_byte_limit";
  // The longest lines the formats can produce stay within 320 bytes.
  GnssEpoch e = specEpoch();
  e.first_mono_ms = 4294967295u; e.utc_date = 20791231; e.utc_ms_of_day = 86400999;
  e.gga_quality = 254; e.fix_type = 1; e.sats = 255; e.hdop_x100 = 65535;
  e.lat_e7 = -900000000; e.lon_e7 = -1800000000; e.alt_cm = INT32_MIN; e.speed_cmps = 65535; e.course_cdeg = 35994;
  std::string l1 = epLine(e, LS_RECORDING, 2147483647, MODE_VEHICLE);
  e.pos_valid = false;  // without a fix "nr" is set instead of la/lo/al
  std::string l2 = epLine(e, LS_RECORDING, 2147483647, MODE_VEHICLE);
  CHECK(cleanLine(l1));
  CHECK(cleanLine(l2));
  char buf[400];
  uint8_t b[WFG_RECORD_SIZE];
  memset(b, 0xFF, sizeof(b));
  std::string lr(buf, Live::fmtRecord(buf, sizeof(buf), b, 4294967295u, 4294967295u));
  CHECK(cleanLine(lr));
  std::string ls(buf, Live::fmtStatus(buf, sizeof(buf), 2147483647, 4294967295LL));
  std::string lv(buf, Live::fmtEvent(buf, sizeof(buf), 4294967295u, true));
  std::string lss(buf, Live::fmtSessionStart(buf, sizeof(buf), 4294967295u, MODE_UNKNOWN, START_AUTO_RESUMED_AFTER_RESET));
  std::string lse(buf, Live::fmtSessionEnd(buf, sizeof(buf), 4294967295u, END_RECOVERED_ON_BOOT, 4294967295u));
  std::string ld(buf, Live::fmtDrop(buf, sizeof(buf), 4294967295u));
  std::string ln(buf, Live::fmtNmea(buf, sizeof(buf), ("$" + std::string(99, '9')).c_str()));
  for (const std::string* l : {&ls, &lv, &lss, &lse, &ld, &ln}) CHECK(cleanLine(*l));
  printf("LIVE line lengths, longest possible (bytes, limit %u): ep %u / %u, rec %u, st %u, ev %u, ss %u, se %u, "
         "drop %u, #N %u\n", (unsigned)kLiveMaxLine, (unsigned)l1.size(), (unsigned)l2.size(), (unsigned)lr.size(),
         (unsigned)ls.size(), (unsigned)lv.size(), (unsigned)lss.size(), (unsigned)lse.size(), (unsigned)ld.size(),
         (unsigned)ln.size());
  // A buffer that is too small gives 0 and an empty string, never a cut line.
  CHECK_EQ(Live::fmtEpoch(buf, 50, specEpoch(), LS_IDLE, -1, MODE_WALK), 0);
  CHECK_EQ(buf[0], 0);
  CHECK_EQ(Live::fmtRecord(buf, 100, b, 1, 96), 0);
  CHECK_EQ(buf[0], 0);
  // A line that cannot be sent within the limits is not written and counts as dropped.
  CapLiveSink k;
  Live live(k);
  StrSink r;
  live.handleCommand("LIVE ON", r);
  live.handleCommand("LIVE NMEA ON", r);
  CHECK(!live.nmea(("$" + std::string(400, 'A')).c_str()));
  CHECK_EQ(k.writes, 0);
  CHECK_EQ(live.pendingDrops(), 1);
}

static void test_live_epoch_from_parser() {
  g_test = "live_ep_from_nmea";
  // The spec's sentences (with real checksums) through the real parser, as the firmware loop feeds it.
  std::string gga = withCk("GNGGA,081647.000,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,,");
  std::string rmc = withCk("GNRMC,081647.000,A,3112.5559,N,12126.3372,E,0.155,343.0,141026,,,A,V");
  std::string gsa = withCk("GNGSA,A,3,01,02,03,04,05,06,,,,,,,1.8,0.9,1.4,1");
  NmeaParser p;
  uint32_t t = 741230;
  for (const std::string* s : {&gga, &rmc, &gsa}) { for (char c : *s + "\r\n") p.feed(c, t); t += 10; }
  CHECK(p.poll(t + 300));
  CHECK_STR(epLine(p.takeEpoch(), LS_RECORDING, 14, MODE_WALK),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":741230,\"utc\":\"2026-10-14T08:16:47.000Z\",\"fix\":1,\"q\":1,\"ft\":\"3D\","
            "\"su\":11,\"hd\":0.9,\"la\":31.2092650,\"lo\":121.4389533,\"al\":12.4,\"sp\":0.08,\"co\":343.0,\"nr\":null,"
            "\"rs\":\"RECORDING\",\"ss\":14,\"md\":\"WALK\"}\n");
  // No fix (indoors): time and date known, no position
  NmeaParser q;
  t = 900000;
  for (const char* body : {"GNGGA,081650.000,,,,,0,03,,,M,,M,,", "GNRMC,081650.000,V,,,,,,,141026,,,N,V",
                           "GNGSA,A,1,,,,,,,,,,,,,99.99,99.99,99.99,1"}) {
    for (char c : withCk(body) + "\r\n") q.feed(c, t);
    t += 10;
  }
  CHECK(q.poll(t + 300));
  CHECK_STR(epLine(q.takeEpoch(), LS_IDLE, -1, MODE_WALK),
            "#J {\"v\":1,\"t\":\"ep\",\"ms\":900000,\"utc\":\"2026-10-14T08:16:50.000Z\",\"fix\":0,\"q\":0,\"ft\":\"NONE\","
            "\"su\":3,\"hd\":null,\"la\":null,\"lo\":null,\"al\":null,\"sp\":null,\"co\":null,"
            "\"nr\":\"RECEIVER_NO_FIX\",\"rs\":\"IDLE\",\"ss\":null,\"md\":\"WALK\"}\n");
  // GGA only: time without a date gives "utc":null
  NmeaParser g;
  for (char c : gga + "\r\n") g.feed(c, 5000);
  CHECK(g.poll(5400));
  std::string l = epLine(g.takeEpoch(), LS_IDLE, -1, MODE_WALK);
  CHECK_STR(jfield(l, "utc"), "null");
  CHECK_STR(jfield(l, "ft"), "null");
  CHECK_STR(jfield(l, "sp"), "null");
  CHECK_STR(jfield(l, "la"), "31.2092650");
}

static void test_live_commands() {
  g_test = "live_commands";
  CapLiveSink k;
  Live live(k);
  StrSink r;
  auto cmd = [&](const char* l) -> std::string {
    r.s.clear();
    bool is = live.handleCommand(l, r);
    return (is ? "1|" : "0|") + r.s;
  };
  CHECK_STR(cmd("LIVE ON"), "1|OK LIVE ON\n");
  CHECK(live.on()); CHECK(!live.nmeaOn());
  CHECK_STR(cmd("LIVE NMEA ON"), "1|OK LIVE NMEA ON\n");
  CHECK(live.nmeaOn());
  CHECK_STR(cmd("LIVE NMEA OFF"), "1|OK LIVE NMEA OFF\n");
  CHECK(!live.nmeaOn());
  CHECK_STR(cmd("LIVE OFF"), "1|OK LIVE OFF\n");
  CHECK(!live.on());
  CHECK_STR(cmd("LIVE ON"), "1|OK LIVE ON\n");
  CHECK_STR(cmd("LIVE ON"), "1|OK LIVE ON\n");  // repeating is harmless
  CHECK_STR(cmd("  LIVE   OFF  "), "1|OK LIVE OFF\n");  // spaces as the protocol's sscanf("%s") accepts them
  CHECK_STR(cmd("LIVE\tNMEA\tON"), "1|OK LIVE NMEA ON\n");
  for (const char* bad : {"LIVE", "LIVE on", "LIVE MAYBE", "LIVE NMEA", "LIVE NMEA MAYBE", "LIVE ON NOW",
                          "LIVE NMEA ON NOW", "LIVE OFF ON", "LIVE NMEA on", "LIVE 1"})
    CHECK_STR(cmd(bad), "1|ERR LIVE bad-argument\n");
  CHECK(!live.on());  // bad arguments change nothing
  CHECK(live.nmeaOn());
  for (const char* other : {"HELLO", "STATUS", "LIVEON", "LIVES ON", "XLIVE ON", "live on", "", "   "})
    CHECK_STR(cmd(other), "0|");
  CHECK_EQ(k.writes, 0);  // replies go to the protocol sink, never to the LIVE sink
}

static void test_live_default_off() {
  g_test = "live_default_off";
  CapLiveSink k;
  Live live(k);
  CHECK(!live.on());
  CHECK(!live.nmeaOn());
  CHECK(!live.epoch(specEpoch(), LS_IDLE, -1, MODE_WALK));
  CHECK(!live.status(3900, 100000));
  CHECK(!live.event(1, true));
  CHECK(!live.nmea("$GNGGA,1*00"));
  uint8_t b[WFG_RECORD_SIZE];
  encRec(b, REC_SESSION_START, 0, 1);
  live.onRecord(b, 0, 48);
  live.sessionStarted(1, MODE_WALK, START_OWNER_BUTTON);
  encRec(b, REC_STATUS, 1);
  live.onRecord(b, 1, 96);
  encRec(b, REC_SESSION_END, 2, 0, END_USER_STOP);
  live.onRecord(b, 2, 144);
  live.sessionCheck(false);
  CHECK_EQ(k.avail_calls, 0);  // not even asked for space
  CHECK_EQ(k.writes, 0);
  CHECK(k.s.empty());
  CHECK_EQ(live.pendingDrops(), 0);
  CHECK_EQ(live.linesDropped(), 0);
  CHECK_EQ(live.linesSent(), 0);
}

static void test_live_nmea_needs_live() {
  g_test = "live_nmea_needs_live_on";
  CapLiveSink k;
  Live live(k);
  StrSink r;
  const char* s = "$GNGGA,081647.000,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,,*4F";
  live.handleCommand("LIVE NMEA ON", r);
  CHECK(!live.nmea(s));  // NMEA on, LIVE off: nothing
  CHECK(k.s.empty());
  live.handleCommand("LIVE ON", r);
  CHECK(live.nmea(s));
  CHECK_STR(k.s, std::string("#N ") + s + "\n");
  k.s.clear();
  live.handleCommand("LIVE NMEA OFF", r);
  CHECK(!live.nmea(s));  // LIVE on, NMEA off: no #N
  CHECK(k.s.empty());
  CHECK(live.event(1, true));  // the other LIVE lines continue
  live.handleCommand("LIVE NMEA ON", r);
  live.handleCommand("LIVE OFF", r);
  k.s.clear();
  CHECK(!live.nmea(s));
  CHECK(k.s.empty());
  live.handleCommand("LIVE ON", r);  // LIVE OFF kept the NMEA setting
  CHECK(live.nmea(s));
}

static void test_live_drop_counter() {
  g_test = "live_drop_counter";
  CapLiveSink k;
  Live live(k);
  StrSink r;
  live.handleCommand("LIVE ON", r);
  char lb[100];
  size_t evn = Live::fmtEvent(lb, sizeof(lb), 4, true);
  // No room: lines are dropped and counted, nothing is written
  k.avail = 0;
  CHECK(!live.event(1, true));
  CHECK(!live.event(2, true));
  CHECK(!live.event(3, false));
  CHECK_EQ(live.pendingDrops(), 3);
  CHECK_EQ(k.writes, 0);
  // Room for the line but not for the drop line before it: dropped and counted too
  k.avail = evn + 5;
  CHECK(!live.event(4, true));
  CHECK_EQ(live.pendingDrops(), 4);
  CHECK_EQ(k.writes, 0);
  // Room for both: the drop line first, then the line; the count restarts at 0
  size_t dn = Live::fmtDrop(lb, sizeof(lb), 4);
  k.avail = dn + evn;
  CHECK(live.event(5, true));
  CHECK_EQ(live.pendingDrops(), 0);
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"drop\",\"n\":4}\n#J {\"v\":1,\"t\":\"ev\",\"n\":5,\"loc\":1}\n");
  // Then normal lines, without a drop line
  k.s.clear();
  k.avail = 1000;
  CHECK(live.event(6, false));
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"ev\",\"n\":6,\"loc\":0}\n");
  CHECK_EQ(live.linesSent(), 2);
  CHECK_EQ(live.linesDropped(), 4);
  // A buffer that fills up: 3 lines fit, the 4th and 5th do not; after it drains, "n":2 and the next line
  k.s.clear();
  k.consume = true;
  k.avail = 3 * evn + 10;
  for (uint32_t i = 10; i < 15; i++) live.event(i, true);
  CHECK_EQ(splitLines(k.s).size(), 3);
  CHECK_EQ(live.pendingDrops(), 2);
  k.s.clear();
  k.avail = 1000;
  CHECK(live.event(15, true));
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"drop\",\"n\":2}\n#J {\"v\":1,\"t\":\"ev\",\"n\":15,\"loc\":1}\n");
  k.consume = false;
  // A failing sink write is counted like a drop
  k.s.clear();
  k.fail = true;
  CHECK(!live.event(16, true));
  CHECK_EQ(live.pendingDrops(), 1);
  k.fail = false;
  CHECK(live.event(17, true));
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"drop\",\"n\":1}\n#J {\"v\":1,\"t\":\"ev\",\"n\":17,\"loc\":1}\n");
  // The drop rule covers every line type, here an ep line after a dropped rec line
  k.s.clear();
  k.avail = 0;
  uint8_t b[WFG_RECORD_SIZE];
  encRec(b, REC_FIX, 9);
  live.onRecord(b, 9, 480);
  CHECK_EQ(live.pendingDrops(), 1);
  k.avail = 1000;
  CHECK(live.epoch(specEpoch(), LS_RECORDING, 14, MODE_WALK));
  std::vector<std::string> L = splitLines(k.s);
  CHECK_EQ(L.size(), 2);
  if (L.size() == 2) {
    CHECK_STR(L[0], "#J {\"v\":1,\"t\":\"drop\",\"n\":1}\n");
    CHECK_STR(jfield(L[1], "t"), "\"ep\"");
  }
  // LIVE OFF clears a pending count, so LIVE ON starts without an old drop line
  k.avail = 0;
  live.event(18, true);
  CHECK_EQ(live.pendingDrops(), 1);
  live.handleCommand("LIVE OFF", r);
  CHECK_EQ(live.pendingDrops(), 0);
  live.handleCommand("LIVE ON", r);
  k.avail = 1000;
  k.s.clear();
  CHECK(live.event(19, true));
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"ev\",\"n\":19,\"loc\":1}\n");
}

static void test_live_sessions() {
  g_test = "live_ss_se";
  CapLiveSink k;
  Live live(k);
  StrSink r;
  live.handleCommand("LIVE ON", r);
  uint8_t b[WFG_RECORD_SIZE];
  // Normal session: ss after the start, se once after the stop with the END reason and the record count
  encRec(b, REC_SESSION_START, 0, 5);
  live.onRecord(b, 0, 48);
  k.s.clear();
  live.sessionStarted(5, MODE_WALK, START_OWNER_BUTTON);
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"ss\",\"ss\":5,\"md\":\"WALK\",\"sr\":\"OWNER_BUTTON\"}\n");
  encRec(b, REC_FIX, 1);
  live.onRecord(b, 1, 96);
  live.sessionCheck(true);  // still recording: nothing
  encRec(b, REC_SESSION_END, 2, 0, END_USER_STOP);
  live.onRecord(b, 2, 144);
  k.s.clear();
  live.sessionCheck(false);
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"se\",\"ss\":5,\"er\":\"USER_STOP\",\"n\":3}\n");
  k.s.clear();
  live.sessionCheck(false);  // only once
  CHECK(k.s.empty());
  // The END record could not be written: "er":null, n = records in the file
  encRec(b, REC_SESSION_START, 0, 6);
  live.onRecord(b, 0, 48);
  live.sessionStarted(6, MODE_VEHICLE, START_AUTO_RESUMED_AFTER_RESET);
  encRec(b, REC_NOFIX, 1);
  live.onRecord(b, 1, 96);
  k.s.clear();
  live.sessionCheck(false);
  CHECK_STR(k.s, "#J {\"v\":1,\"t\":\"se\",\"ss\":6,\"er\":null,\"n\":2}\n");
  // No sessionCheck before the next session: its START record ends the previous session first
  encRec(b, REC_SESSION_START, 0, 7);
  live.onRecord(b, 0, 48);
  live.sessionStarted(7, MODE_WALK, START_OWNER_BUTTON);
  encRec(b, REC_SESSION_END, 1, 0, END_LOW_BATTERY);
  live.onRecord(b, 1, 96);
  k.s.clear();
  encRec(b, REC_SESSION_START, 0, 8);
  live.onRecord(b, 0, 48);
  live.sessionStarted(8, MODE_WALK, START_OWNER_BUTTON);
  std::vector<std::string> L = splitLines(k.s);
  CHECK_EQ(L.size(), 3);
  if (L.size() == 3) {
    CHECK_STR(L[0], "#J {\"v\":1,\"t\":\"se\",\"ss\":7,\"er\":\"LOW_BATTERY\",\"n\":2}\n");
    CHECK(L[1].find("\"t\":\"rec\",\"seq\":0,\"ty\":1,") != std::string::npos);
    CHECK_STR(L[2], "#J {\"v\":1,\"t\":\"ss\",\"ss\":8,\"md\":\"WALK\",\"sr\":\"OWNER_BUTTON\"}\n");
  }
  // LIVE off when the session ends: no se, also not later
  live.handleCommand("LIVE OFF", r);
  encRec(b, REC_SESSION_END, 1, 0, END_USER_STOP);
  live.onRecord(b, 1, 96);
  live.sessionCheck(false);
  live.handleCommand("LIVE ON", r);
  k.s.clear();
  live.sessionCheck(false);
  CHECK(k.s.empty());
  // LIVE turned on in the middle of a session: the session was followed anyway, so se has the right count
  live.handleCommand("LIVE OFF", r);
  encRec(b, REC_SESSION_START, 0, 9);
  live.onRecord(b, 0, 48);
  live.sessionStarted(9, MODE_WALK, START_OWNER_BUTTON);
  for (uint32_t i = 1; i < 10; i++) { encRec(b, REC_FIX, i); live.onRecord(b, i, (i + 1) * 48); }
  live.handleCommand("LIVE ON", r);
  k.s.clear();
  encRec(b, REC_SESSION_END, 10, 0, END_STORAGE_FULL);
  live.onRecord(b, 10, 11 * 48);
  live.sessionCheck(false);
  L = splitLines(k.s);
  CHECK_EQ(L.size(), 2);
  if (L.size() == 2) CHECK_STR(L[1], "#J {\"v\":1,\"t\":\"se\",\"ss\":9,\"er\":\"STORAGE_FULL\",\"n\":11}\n");
  // STATUS record: rec, then st with the battery only when ST_BATT_VALID is set
  Record st;
  memset(&st, 0, sizeof(st));
  st.h.type = REC_STATUS; st.h.seq = 3;
  st.st.vbat_mv = 3988; st.st.flags = ST_BATT_VALID; st.st.fs_free_bytes = 2310144;
  encode(st, b);
  k.s.clear();
  live.onRecord(b, 3, 192);
  L = splitLines(k.s);
  CHECK_EQ(L.size(), 2);
  if (L.size() == 2) CHECK_STR(L[1], "#J {\"v\":1,\"t\":\"st\",\"vb\":3988,\"ff\":2310144}\n");
  st.st.flags = 0;
  encode(st, b);
  k.s.clear();
  live.onRecord(b, 3, 192);
  L = splitLines(k.s);
  if (L.size() == 2) CHECK_STR(L[1], "#J {\"v\":1,\"t\":\"st\",\"vb\":null,\"ff\":2310144}\n");
}

struct ObsTap {
  std::string bytes;  // every observed record, in order
  std::vector<uint32_t> seqs, sizes;
  Live* live = nullptr;
};
static void tap_cb(const uint8_t* rec, uint32_t seq, uint32_t size, void* ctx) {
  ObsTap* t = (ObsTap*)ctx;
  t->bytes.append((const char*)rec, WFG_RECORD_SIZE);
  t->seqs.push_back(seq);
  t->sizes.push_back(size);
  if (t->live) live_record_observer(rec, seq, size, t->live);
}
static bool tapContiguous(const ObsTap& t) {
  for (size_t i = 0; i < t.seqs.size(); i++)
    if (t.seqs[i] != i || t.sizes[i] != (i + 1) * WFG_RECORD_SIZE) return false;
  return true;
}

static void test_live_record_observer() {
  g_test = "live_record_observer";
  // A. The observer sees every record of the sample session in order (seq, size after the write, bytes), and the
  //    file is byte-identical to the same session recorded without an observer.
  {
    std::string d1 = freshDir("fs_live_obs"), d2 = freshDir("fs_live_noobs");
    Sim s1(d1, 6750208, testCfg()), s2(d2, 6750208, testCfg());
    ObsTap tap;
    s1.lg.setRecordObserver(tap_cb, &tap);
    std::string n1 = recordSampleSession(s1, true), n2 = recordSampleSession(s2, true);
    std::string f1 = fileBytes(s1.st, n1.c_str()), f2 = fileBytes(s2.st, n2.c_str());
    CHECK(!f1.empty() && f1 == f2);
    CHECK(tap.bytes == f1);
    CHECK_EQ(tap.seqs.size(), f1.size() / WFG_RECORD_SIZE);
    CHECK(tapContiguous(tap));
  }
  // B. LIVE end to end on the logging core, with the calls main.cpp makes: rec lines rebuild the file, crc and b are
  //    right, ep/st/ev/ss/se come in the expected places.
  {
    std::string d = freshDir("fs_live_e2e");
    Sim s(d, 6750208, testCfg());
    CapLiveSink k;
    Live live(k);
    StrSink rep;
    live.handleCommand("LIVE ON", rep);
    ObsTap tap;
    tap.live = &live;
    s.lg.setRecordObserver(tap_cb, &tap);
    s.lg.begin();
    s.lg.setStatusSource(testStatus, nullptr);
    s.lg.tick(s.now, &s.p);
    CHECK(s.lg.start(MODE_VEHICLE, s.now));
    std::string name = s.lg.currentName();
    live.sessionStarted((uint32_t)atoi(name.c_str() + 1), MODE_VEHICLE, START_OWNER_BUTTON);
    auto take = [&]() {
      GnssEpoch e = s.p.takeEpoch();
      live.epoch(e, s.lg.state(), s.lg.recording() ? (int32_t)atoi(s.lg.currentName() + 1) : -1, MODE_VEHICLE);
      s.lg.onEpoch(e, s.now);
    };
    for (int i = 0; i < 5; i++) {
      for (auto& l : epochLines(3600000 + i * 1000, "141026", SimFix{true, 31.2 + i * 1e-5, 121.4, 5, 1, 0, 8, 1.0})) {
        s.now += 5;
        if (s.p.feedLine(l.c_str(), s.now) && s.p.hasEpoch()) take();
      }
      for (int j = 0; j < 20; j++) {
        s.now += 49;
        if (s.p.poll(s.now) && s.p.hasEpoch()) take();
        s.lg.tick(s.now, &s.p);
        live.sessionCheck(s.lg.recording());
      }
      if (i == 2 && s.lg.markEvent(s.now - 100, 100, s.now)) live.event((uint32_t)s.lg.lastEventNo(), s.lg.lastEventLocated());
    }
    CHECK(s.lg.stop(END_USER_STOP, s.now));
    live.sessionCheck(s.lg.recording());
    std::string file = fileBytes(s.st, name.c_str());
    size_t nrec = file.size() / WFG_RECORD_SIZE;
    std::vector<std::string> L = splitLines(k.s);
    std::string hx;
    int n_rec = 0, n_ep = 0, n_st = 0, n_ev = 0, n_ss = 0, n_se = 0, n_other = 0;
    bool clean = true, crc_ok = true, b_ok = true, seq_ok = true, ep_ok = true;
    size_t i_ss = 0, i_se = 0;
    for (size_t i = 0; i < L.size(); i++) {
      const std::string& l = L[i];
      if (!cleanLine(l) || l.compare(0, 4, "#J {") != 0) clean = false;
      std::string t = jfield(l, "t");
      if (t == "\"rec\"") {
        std::string h = jfield(l, "hx");
        h = h.size() >= 2 ? h.substr(1, h.size() - 2) : "";
        if (h.size() == 2 * WFG_RECORD_SIZE) {
          uint8_t rb[WFG_RECORD_SIZE];
          for (size_t j = 0; j < WFG_RECORD_SIZE; j++) rb[j] = (uint8_t)strtoul(h.substr(2 * j, 2).c_str(), nullptr, 16);
          char c8[16];
          snprintf(c8, sizeof(c8), "\"%08x\"", (unsigned)crc32(rb, 44));
          if (jfield(l, "crc") != c8) crc_ok = false;
          if (jfield(l, "ty") != std::to_string(rb[2])) crc_ok = false;
        }
        if (jfield(l, "seq") != std::to_string(n_rec)) seq_ok = false;
        if (jfield(l, "b") != std::to_string((n_rec + 1) * WFG_RECORD_SIZE)) b_ok = false;
        hx += h;
        n_rec++;
      } else if (t == "\"ep\"") {
        n_ep++;
        if (jfield(l, "rs") != "\"RECORDING\"" || jfield(l, "ss") != "1" || jfield(l, "md") != "\"VEHICLE\"" ||
            jfield(l, "fix") != "1")
          ep_ok = false;
      } else if (t == "\"st\"") n_st++;
      else if (t == "\"ev\"") n_ev++;
      else if (t == "\"ss\"") { n_ss++; i_ss = i; }
      else if (t == "\"se\"") { n_se++; i_se = i; }
      else n_other++;
    }
    CHECK(clean); CHECK(crc_ok); CHECK(b_ok); CHECK(seq_ok); CHECK(ep_ok);
    CHECK(hx == hexOf((const uint8_t*)file.data(), file.size()));
    CHECK_EQ(n_rec, nrec);
    CHECK_EQ(n_ep, 5);
    CHECK_EQ(n_st, 1);  // the STATUS record written at the start
    CHECK_EQ(n_ev, 1);
    CHECK_EQ(n_ss, 1);
    CHECK_EQ(n_se, 1);
    CHECK_EQ(n_other, 0);
    CHECK_EQ(i_se, L.size() - 1);  // se is the last line, right after the END record's rec line
    CHECK(i_se > 0 && jfield(L[i_se - 1], "ty") == "6");
    CHECK(i_ss > 0 && i_ss < i_se);
    if (!L.empty()) {
      CHECK_STR(L[i_ss], "#J {\"v\":1,\"t\":\"ss\",\"ss\":1,\"md\":\"VEHICLE\",\"sr\":\"OWNER_BUTTON\"}\n");
      char want[120];
      snprintf(want, sizeof(want), "#J {\"v\":1,\"t\":\"se\",\"ss\":1,\"er\":\"USER_STOP\",\"n\":%u}\n", (unsigned)nrec);
      CHECK_STR(L[i_se], want);
    }
    // st carries the STATUS record's battery and free-space values
    Record sr;
    bool found = false;
    for (size_t j = 0; j + WFG_RECORD_SIZE <= file.size(); j += WFG_RECORD_SIZE)
      if (decode((const uint8_t*)file.data() + j, sr) && sr.h.type == REC_STATUS) { found = true; break; }
    CHECK(found);
    if (found) {
      char want[120];
      snprintf(want, sizeof(want), "#J {\"v\":1,\"t\":\"st\",\"vb\":3988,\"ff\":%u}\n", (unsigned)sr.st.fs_free_bytes);
      CHECK(k.s.find(want) != std::string::npos);
    }
    CHECK(k.s.find("#J {\"v\":1,\"t\":\"ev\",\"n\":1,\"loc\":1}\n") != std::string::npos);
  }
  // C. Storage runs out (free-space check): the END(STORAGE_FULL) record is observed and se reports it
  {
    std::string d = freshDir("fs_live_full");
    LoggerConfig c = testCfg();
    c.reserve_bytes = 16384;
    PosixStorage st(d.c_str(), 128 * 1024);
    Logger lg(st, c);
    CapLiveSink k;
    Live live(k);
    StrSink rep;
    live.handleCommand("LIVE ON", rep);
    ObsTap tap;
    tap.live = &live;
    lg.setRecordObserver(tap_cb, &tap);
    lg.begin();
    CHECK(lg.start(MODE_WALK, 0));
    std::string name = lg.currentName();
    live.sessionStarted(1, MODE_WALK, START_OWNER_BUTTON);
    NmeaParser p;
    uint32_t now = 0;
    int i = 0;
    while (lg.state() == LS_RECORDING && i < 100000) {
      for (auto& s : epochLines(3600000 + (i % 80000) * 1000, "031026", SimFix{true, 31.3, 121.5, 5, 1, 0, 8, 1.0}))
        p.feedLine(s.c_str(), now += 5);
      now += 985;
      if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
      lg.tick(now, &p);
      live.sessionCheck(lg.recording());
      i++;
    }
    CHECK_EQ(lg.state(), LS_FULL);
    std::string file = fileBytes(st, name.c_str());
    CHECK(tap.bytes == file);
    CHECK(tapContiguous(tap));
    std::vector<std::string> L = splitLines(k.s);
    CHECK(L.size() >= 2);
    if (L.size() >= 2) {
      char want[120];
      snprintf(want, sizeof(want), "#J {\"v\":1,\"t\":\"se\",\"ss\":1,\"er\":\"STORAGE_FULL\",\"n\":%u}\n",
               (unsigned)(file.size() / WFG_RECORD_SIZE));
      CHECK_STR(L.back(), want);
      CHECK_STR(jfield(L[L.size() - 2], "ty"), "6");
      CHECK_STR(jfield(L[L.size() - 2], "b"), std::to_string(file.size()));
    }
  }
  // D. Hard short write (ENOSPC mid-record): the END record the logger writes after cutting the partial record is
  //    observed too; if not even that fits, the file stays OPEN and se has "er":null. Either way n = records in file.
  {
    std::string d = freshDir("fs_live_enospc");
    PosixStorage st(d.c_str(), 32 * 1024);
    LoggerConfig c = testCfg();
    c.reserve_bytes = 0;
    c.free_check_every_records = 1000000;
    Logger lg(st, c);
    CapLiveSink k;
    Live live(k);
    StrSink rep;
    live.handleCommand("LIVE ON", rep);
    ObsTap tap;
    tap.live = &live;
    lg.setRecordObserver(tap_cb, &tap);
    lg.begin();
    CHECK(lg.start(MODE_WALK, 0));
    std::string name = lg.currentName();
    live.sessionStarted(1, MODE_WALK, START_OWNER_BUTTON);
    NmeaParser p;
    uint32_t now = 0;
    int i = 0;
    while (lg.state() == LS_RECORDING && i < 10000) {
      for (auto& s : epochLines(3600000 + i * 1000, "031026", SimFix{true, 31.3, 121.5, 5, 1, 0, 8, 1.0}))
        p.feedLine(s.c_str(), now += 5);
      now += 985;
      if (p.poll(now)) lg.onEpoch(p.takeEpoch(), now);
      live.sessionCheck(lg.recording());
      i++;
    }
    CHECK_EQ(lg.state(), LS_FULL);
    IntegrityReport ir = Logger::checkSession(st, name.c_str());
    std::string file = fileBytes(st, name.c_str());
    CHECK(tap.bytes == file);
    CHECK(tapContiguous(tap));
    std::vector<std::string> L = splitLines(k.s);
    if (!L.empty()) {
      char want[120];
      snprintf(want, sizeof(want), "#J {\"v\":1,\"t\":\"se\",\"ss\":1,\"er\":%s,\"n\":%u}\n",
               ir.has_end ? "\"STORAGE_FULL\"" : "null", (unsigned)(file.size() / WFG_RECORD_SIZE));
      CHECK_STR(L.back(), want);
    }
  }
}

static void test_nmea_line_collector() {
  g_test = "nmea_line_collector";
  NmeaLineCollector c;
  auto feed = [&](const std::string& bytes) {
    std::vector<std::string> out;
    for (char ch : bytes)
      if (c.feed(ch)) out.push_back(c.line());
    return out;
  };
  std::string gga = withCk("GNGGA,081647.000,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,,");
  std::vector<std::string> v = feed(gga + "\r\n" + "$GNRMC,X*00\n" + "\r\n");
  CHECK_EQ(v.size(), 2);
  if (v.size() == 2) { CHECK_STR(v[0], gga); CHECK_STR(v[1], "$GNRMC,X*00"); }
  // Bytes before '$' (noise, a partial line after boot) are not part of the sentence; lines without '$' are ignored
  v = feed("\x07zz garbage$GNGSA,A,3*00\r\nno sentence here\r\n");
  CHECK_EQ(v.size(), 1);
  if (v.size() == 1) CHECK_STR(v[0], "$GNGSA,A,3*00");
  CHECK_EQ(c.discarded(), 0);
  // 100 characters pass, 101 are discarded
  std::string s100 = "$" + std::string(99, 'A'), s101 = "$" + std::string(100, 'A');
  v = feed(s100 + "\r\n" + s101 + "\r\n");
  CHECK_EQ(v.size(), 1);
  if (v.size() == 1) CHECK_EQ(v[0].size(), 100);
  CHECK_EQ(c.discarded(), 1);
  // Control or non-ASCII bytes inside a sentence: discarded
  v = feed(std::string("$GN\tGGA*00\r\n") + "$GN\xb5GGA*00\r\n");
  CHECK_EQ(v.size(), 0);
  CHECK_EQ(c.discarded(), 3);
  // A sentence cut short by the next '$' is discarded and the next one kept (NmeaParser also restarts at '$')
  v = feed("$GNGGA,081647$GNRMC,081647.000,V*00\r\n");
  CHECK_EQ(v.size(), 1);
  if (v.size() == 1) CHECK_STR(v[0], "$GNRMC,081647.000,V*00");
  CHECK_EQ(c.discarded(), 4);
}

static void test_tx_queue_model() {
  g_test = "tx_queue_model";
  TxQueueModel q(3072, 5760, 32);  // the values main.cpp uses for the classic ESP32
  CHECK_EQ(q.freeBytes(1000), 3072);
  q.add(100, 1000);
  CHECK_EQ(q.queuedBytes(1000), 132);  // line + per-write overhead
  CHECK_EQ(q.freeBytes(1000), 3072 - 132);
  CHECK_EQ(q.queuedBytes(11000), 75);  // 10 ms at 5760 bytes/s = 57.6 bytes sent; 74.4 rounded up
  CHECK_EQ(q.queuedBytes(1000), 75);   // time going backwards changes nothing
  CHECK_EQ(q.queuedBytes(1000000), 0);
  for (int i = 0; i < 20; i++) q.add(288, 2000000);  // 20 x 320 = 6400 > 3072
  CHECK_EQ(q.freeBytes(2000000), 0);
  CHECK_EQ(q.freeBytes(2500000), 0);           // 0.5 s later 2880 bytes are out, 3520 still queued
  CHECK_EQ(q.freeBytes(3000000), 3072 - 640);  // 1 s later 5760 are out, 640 queued
  CHECK_EQ(q.queuedBytes(3000000 + 60000000), 0);  // a minute later: empty
  // Wired into Live, the estimate limits the output: one second of epoch lines at 1 Hz never comes near the cap
  struct ModelSink : LiveSink {
    TxQueueModel m{3072, 5760, 32};
    uint64_t now = 0;
    std::string s;
    size_t availableForWrite() override { return m.freeBytes(now); }
    bool write(const char* p, size_t n) override { m.add(n, now); s.append(p, n); return true; }
  } ms;
  Live live(ms);
  StrSink r;
  live.handleCommand("LIVE ON", r);
  live.handleCommand("LIVE NMEA ON", r);
  std::string gga = withCk("GNGGA,081647.000,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,,");
  uint8_t b[WFG_RECORD_SIZE];
  encRec(b, REC_FIX, 1);
  for (int sec = 0; sec < 600; sec++) {  // 10 minutes: per second 1 ep, 2 rec, 15 #N lines
    ms.now = (uint64_t)sec * 1000000u;
    live.epoch(specEpoch(), LS_RECORDING, 1, MODE_WALK);
    live.onRecord(b, 1, 96);
    live.onRecord(b, 1, 96);
    for (int j = 0; j < 15; j++) { ms.now += 50000; live.nmea(gga.c_str()); }
  }
  CHECK_EQ(live.linesDropped(), 0);
  CHECK_EQ(live.linesSent(), 600 * 18);
  // ...while a burst far above the line rate is cut off by drops instead of waiting
  for (int j = 0; j < 100; j++) live.nmea(gga.c_str());
  CHECK(live.linesDropped() > 0);
}

int main(int argc, char** argv) {
  g_root = argc > 1 ? argv[1] : "./host_test_tmp";
  const char* sample_out = argc > 2 ? argv[2] : nullptr;
  mkdir(g_root.c_str(), 0755);
  test_crc_sha();
  test_record_roundtrip();
  test_nmea();
  test_clock_utils();
  test_session_and_export(sample_out);
  test_torn_tail_recovery(sample_out);
  test_storage_full();
  test_export_confirm_invalidated_by_change();
  test_button();
  test_proto(sample_out);
  test_many_sessions();
  test_resume(sample_out);
  test_read_v1(sample_out);
  // LIVE lines (firmware 0.3.0)
  test_live_formats();
  test_live_limits();
  test_live_epoch_from_parser();
  test_live_commands();
  test_live_default_off();
  test_live_nmea_needs_live();
  test_live_drop_counter();
  test_live_sessions();
  test_live_record_observer();
  test_nmea_line_collector();
  test_tx_queue_model();
  printf("HOST TESTS (simulated, no hardware): %d checks passed, %d failed\n", g_pass, g_fail);
  return g_fail ? 1 : 0;
}
