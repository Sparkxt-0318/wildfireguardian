// Minimal NMEA-0183 parser (GGA, RMC, GSA) with checksum verification and epoch assembly.
// Talker-agnostic ($GP, $GN, $GB, $BD, $GA, $GL ...). Hardware independent.
//
// Epoch assembly: sentences belonging to one GNSS solution share the same hhmmss.ss time field.
// An epoch is committed when a sentence with a different time arrives, or when poll() sees no sentence
// for commit_timeout_ms (quiet gap after the 1 Hz burst). GSA (no time field) joins the open epoch.
#pragma once
#include <stdint.h>
#include <stddef.h>

namespace wfg {

struct GnssEpoch {
  bool has_time = false;          // hhmmss present
  uint32_t utc_ms_of_day = 0xFFFFFFFF;
  bool has_date = false;          // ddmmyy present (RMC)
  uint32_t utc_date = 0;          // YYYYMMDD
  bool has_gga = false, has_rmc = false, has_gsa = false;
  uint8_t gga_quality = 0xFF;     // 0 = invalid, 1 = GPS, 2 = DGPS, 4 = RTK fixed, 5 = RTK float, 6 = DR ...
  bool rmc_active = false;        // RMC status 'A'
  bool pos_valid = false;
  int32_t lat_e7 = 0, lon_e7 = 0;
  bool alt_valid = false;
  int32_t alt_cm = 0;
  bool sats_valid = false;
  uint8_t sats = 0;
  bool hdop_valid = false;
  uint16_t hdop_x100 = 0;
  bool speed_valid = false;
  uint16_t speed_cmps = 0;
  bool course_valid = false;
  uint16_t course_cdeg = 0;
  uint8_t fix_type = 0;           // GSA 1/2/3, 0 unknown
  uint32_t first_mono_ms = 0;     // receive time of first sentence of this epoch
  uint32_t last_mono_ms = 0;      // receive time of last sentence of this epoch
  bool cksum_err = false;         // checksum-failed sentence(s) seen since the previous epoch
};

class NmeaParser {
 public:
  uint32_t commit_timeout_ms = 250;

  // Feed one byte. Returns true if a new epoch was committed (retrieve with takeEpoch()).
  bool feed(char c, uint32_t mono_ms);
  // Feed a full line (without CR/LF). Returns true if an epoch was committed.
  bool feedLine(const char* line, uint32_t mono_ms);
  // Commit a stale pending epoch. Returns true if an epoch was committed.
  bool poll(uint32_t mono_ms);
  bool hasEpoch() const { return ready_; }
  bool epochPending() const { return cur_active_; }  // sentences of an uncommitted epoch received
  GnssEpoch takeEpoch() { ready_ = false; return done_; }

  // Last complete sentence (for optional raw sidecar); valid until next feed().
  const char* lastLine() const { return last_line_; }
  bool lastLineOk() const { return last_ok_; }

  uint32_t sentences_ok = 0;
  uint32_t sentences_bad_checksum = 0;
  uint32_t sentences_ignored = 0;
  uint32_t last_sentence_mono_ms = 0;
  bool bad_checksum_since_take = false;

  // Exposed for unit tests.
  static bool parseLatLon(const char* v, const char* hemi, bool is_lat, int32_t& out_e7);
  static bool parseTime(const char* v, uint32_t& ms_of_day);
  static bool parseDate(const char* v, uint32_t& yyyymmdd);
  static bool parseFixed(const char* v, int scale_digits, int64_t& out);  // "12.34",2 -> 1234

 private:
  char buf_[120];
  size_t len_ = 0;
  char last_line_[120] = {0};
  bool last_ok_ = false;
  GnssEpoch cur_;
  bool cur_active_ = false;
  GnssEpoch done_;
  bool ready_ = false;
  uint8_t pending_gsa_fix_ = 0;
  bool pending_gsa_ = false;

  bool handleSentence(char* s, uint32_t mono_ms);
  void commit();
  bool startOrJoin(uint32_t ms_of_day, uint32_t mono_ms);
};

}  // namespace wfg
