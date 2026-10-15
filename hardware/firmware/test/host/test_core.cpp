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
  printf("HOST TESTS (simulated, no hardware): %d checks passed, %d failed\n", g_pass, g_fail);
  return g_fail ? 1 : 0;
}
