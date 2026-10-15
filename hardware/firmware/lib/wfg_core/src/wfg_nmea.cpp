#include "wfg_nmea.h"
#include <string.h>
#include <stdlib.h>

namespace wfg {

static int hexv(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

bool NmeaParser::parseFixed(const char* v, int scale_digits, int64_t& out) {
  if (!v || !*v) return false;
  bool neg = false;
  if (*v == '-') { neg = true; v++; } else if (*v == '+') v++;
  int64_t ip = 0; int nd = 0;
  while (*v >= '0' && *v <= '9') { ip = ip * 10 + (*v - '0'); v++; nd++; }
  int64_t fp = 0; int fd = 0; int64_t round_up = 0;
  if (*v == '.') {
    v++;
    while (*v >= '0' && *v <= '9') {
      if (fd < scale_digits) { fp = fp * 10 + (*v - '0'); fd++; }
      else if (fd == scale_digits) { round_up = (*v >= '5') ? 1 : 0; fd++; }
      v++; nd++;
    }
  }
  if (*v != 0 || nd == 0) return false;
  int used = fd > scale_digits ? scale_digits : fd;
  for (int i = used; i < scale_digits; i++) fp *= 10;
  int64_t mul = 1; for (int i = 0; i < scale_digits; i++) mul *= 10;
  out = ip * mul + fp + round_up;
  if (neg) out = -out;
  return true;
}

bool NmeaParser::parseLatLon(const char* v, const char* hemi, bool is_lat, int32_t& out_e7) {
  if (!v || !*v || !hemi || !*hemi) return false;
  const char* dot = strchr(v, '.');
  size_t intlen = dot ? (size_t)(dot - v) : strlen(v);
  size_t degdigits = is_lat ? 2 : 3;
  if (intlen < degdigits + 2 || intlen > degdigits + 2) return false;
  int deg = 0;
  for (size_t i = 0; i < degdigits; i++) {
    if (v[i] < '0' || v[i] > '9') return false;
    deg = deg * 10 + (v[i] - '0');
  }
  int64_t min_e9 = 0;  // minutes * 1e9 (keeps sub-1e-7 deg precision before final rounding)
  if (!parseFixed(v + degdigits, 9, min_e9)) return false;
  if (min_e9 < 0 || min_e9 >= 60LL * 1000000000LL) return false;
  // deg_e7 = deg*1e7 + min/60*1e7 = deg*1e7 + min_e9/6000 (rounded half away from zero)
  int64_t e7 = (int64_t)deg * 10000000LL + (min_e9 + 3000) / 6000;
  char h = hemi[0];
  if (is_lat) {
    if (h == 'S') e7 = -e7; else if (h != 'N') return false;
    if (e7 > 900000000LL || e7 < -900000000LL) return false;
  } else {
    if (h == 'W') e7 = -e7; else if (h != 'E') return false;
    if (e7 > 1800000000LL || e7 < -1800000000LL) return false;
  }
  out_e7 = (int32_t)e7;
  return true;
}

bool NmeaParser::parseTime(const char* v, uint32_t& ms) {
  if (!v || strlen(v) < 6) return false;
  for (int i = 0; i < 6; i++) if (v[i] < '0' || v[i] > '9') return false;
  int hh = (v[0] - '0') * 10 + (v[1] - '0');
  int mm = (v[2] - '0') * 10 + (v[3] - '0');
  int ss = (v[4] - '0') * 10 + (v[5] - '0');
  if (hh > 23 || mm > 59 || ss > 60) return false;
  int frac_ms = 0;
  if (v[6] == '.') {
    int64_t f = 0;
    char tmp[16] = "0.";
    strncat(tmp, v + 7, 10);
    if (!parseFixed(tmp, 3, f)) return false;
    frac_ms = (int)f;
  } else if (v[6] != 0) {
    return false;
  }
  ms = (uint32_t)(((hh * 60 + mm) * 60 + ss) * 1000 + frac_ms);
  return true;
}

bool NmeaParser::parseDate(const char* v, uint32_t& ymd) {
  if (!v || strlen(v) != 6) return false;
  for (int i = 0; i < 6; i++) if (v[i] < '0' || v[i] > '9') return false;
  int dd = (v[0] - '0') * 10 + (v[1] - '0');
  int mo = (v[2] - '0') * 10 + (v[3] - '0');
  int yy = (v[4] - '0') * 10 + (v[5] - '0');
  if (dd < 1 || dd > 31 || mo < 1 || mo > 12) return false;
  // Two-digit year: GNSS receivers report years >= 2000 in practice. 80..99 -> 19xx for safety.
  int year = yy >= 80 ? 1900 + yy : 2000 + yy;
  ymd = (uint32_t)(year * 10000 + mo * 100 + dd);
  return true;
}

bool NmeaParser::feed(char c, uint32_t mono_ms) {
  if (c == '\r' || c == '\n') {
    if (len_ == 0) return false;
    buf_[len_] = 0;
    len_ = 0;
    return feedLine(buf_, mono_ms);
  }
  if (c == '$') len_ = 0;  // resync on sentence start
  if (len_ < sizeof(buf_) - 1) buf_[len_++] = c;
  else len_ = 0;  // overlong garbage -> drop
  return false;
}

bool NmeaParser::feedLine(const char* line, uint32_t mono_ms) {
  bool committed_before = ready_;
  strncpy(last_line_, line, sizeof(last_line_) - 1);
  last_line_[sizeof(last_line_) - 1] = 0;
  last_ok_ = false;
  char s[120];
  strncpy(s, line, sizeof(s) - 1);
  s[sizeof(s) - 1] = 0;
  if (s[0] != '$') { sentences_ignored++; return false; }
  char* star = strrchr(s, '*');
  if (!star || strlen(star) < 3) { sentences_bad_checksum++; bad_checksum_since_take = true; return false; }
  uint8_t ck = 0;
  for (char* p = s + 1; p < star; p++) ck ^= (uint8_t)*p;
  int h1 = hexv(star[1]), h2 = hexv(star[2]);
  if (h1 < 0 || h2 < 0 || ((h1 << 4) | h2) != ck) {
    sentences_bad_checksum++;
    bad_checksum_since_take = true;
    return false;
  }
  *star = 0;
  last_ok_ = true;
  last_sentence_mono_ms = mono_ms;
  bool r = handleSentence(s + 1, mono_ms);
  return r || (!committed_before && ready_);
}

// Split comma-separated fields in place (empty fields preserved).
static int splitFields(char* s, char** f, int maxf) {
  int n = 0;
  f[n++] = s;
  for (char* p = s; *p && n < maxf; p++) {
    if (*p == ',') { *p = 0; f[n++] = p + 1; }
  }
  return n;
}

void NmeaParser::commit() {
  if (!cur_active_) return;
  if (pending_gsa_) { cur_.has_gsa = true; cur_.fix_type = pending_gsa_fix_; }
  done_ = cur_;
  done_.cksum_err = bad_checksum_since_take;
  bad_checksum_since_take = false;
  ready_ = true;
  cur_active_ = false;
  cur_ = GnssEpoch();
}

bool NmeaParser::startOrJoin(uint32_t ms_of_day, uint32_t mono_ms) {
  bool committed = false;
  if (cur_active_ && cur_.utc_ms_of_day != ms_of_day) { commit(); committed = true; }
  if (!cur_active_) {
    cur_ = GnssEpoch();
    cur_active_ = true;
    cur_.has_time = true;
    cur_.utc_ms_of_day = ms_of_day;
    cur_.first_mono_ms = mono_ms;
  }
  cur_.last_mono_ms = mono_ms;
  return committed;
}

bool NmeaParser::poll(uint32_t mono_ms) {
  if (cur_active_ && (uint32_t)(mono_ms - cur_.last_mono_ms) > commit_timeout_ms) {
    commit();
    return true;
  }
  return false;
}

bool NmeaParser::handleSentence(char* s, uint32_t mono_ms) {
  char* f[24];
  int n = splitFields(s, f, 24);
  if (strlen(f[0]) != 5) { sentences_ignored++; return false; }
  const char* type = f[0] + 2;
  bool committed = false;

  if (!strcmp(type, "GGA")) {
    // $xxGGA,time,lat,N,lon,E,quality,numSV,HDOP,alt,M,sep,M,diffAge,diffStation
    if (n < 10) { sentences_ignored++; return false; }
    sentences_ok++;
    uint32_t t;
    if (!parseTime(f[1], t)) {
      // No time: receiver has nothing yet. Still evidence that GNSS is talking; don't start an epoch.
      return false;
    }
    committed = startOrJoin(t, mono_ms);
    cur_.has_gga = true;
    cur_.gga_quality = (uint8_t)atoi(f[6]);
    if (f[6][0] == 0) cur_.gga_quality = 0xFF;
    int64_t v;
    if (f[7][0]) { cur_.sats_valid = true; cur_.sats = (uint8_t)atoi(f[7]); }
    if (parseFixed(f[8], 2, v) && v >= 0 && v < 65535) { cur_.hdop_valid = true; cur_.hdop_x100 = (uint16_t)v; }
    int32_t la, lo;
    bool posok = parseLatLon(f[2], f[3], true, la) && parseLatLon(f[4], f[5], false, lo);
    if (posok && cur_.gga_quality != 0 && cur_.gga_quality != 0xFF) {
      cur_.pos_valid = true; cur_.lat_e7 = la; cur_.lon_e7 = lo;
      if (parseFixed(f[9], 2, v)) { cur_.alt_valid = true; cur_.alt_cm = (int32_t)v; }
    }
  } else if (!strcmp(type, "RMC")) {
    // $xxRMC,time,status,lat,N,lon,E,sog_knots,cog_deg,ddmmyy,magvar,E,mode[,navstatus]
    if (n < 10) { sentences_ignored++; return false; }
    sentences_ok++;
    uint32_t t;
    if (!parseTime(f[1], t)) return false;
    committed = startOrJoin(t, mono_ms);
    cur_.has_rmc = true;
    cur_.rmc_active = (f[2][0] == 'A');
    uint32_t d;
    if (parseDate(f[9], d)) { cur_.has_date = true; cur_.utc_date = d; }
    int64_t v;
    if (cur_.rmc_active) {
      // knots -> cm/s : 1 kn = 1852/3600 m/s = 51.4444 cm/s
      if (parseFixed(f[7], 3, v) && v >= 0) {
        int64_t cmps = (v * 1852 * 100 / 3600 + 500) / 1000;
        if (cmps > 65535) cmps = 65535;
        cur_.speed_valid = true; cur_.speed_cmps = (uint16_t)cmps;
      }
      if (parseFixed(f[8], 2, v) && v >= 0 && v < 36000) { cur_.course_valid = true; cur_.course_cdeg = (uint16_t)v; }
      if (!cur_.has_gga) {  // RMC position used only if no GGA in this epoch; GGA overwrites it (GGA has altitude)
        int32_t la, lo;
        if (parseLatLon(f[3], f[4], true, la) && parseLatLon(f[5], f[6], false, lo)) {
          cur_.pos_valid = true; cur_.lat_e7 = la; cur_.lon_e7 = lo;
        }
      }
    }
  } else if (!strcmp(type, "GSA")) {
    // $xxGSA,mode,fixtype,sv...,PDOP,HDOP,VDOP[,systemId]  (no time field -> attach to current/next epoch)
    if (n < 3) { sentences_ignored++; return false; }
    sentences_ok++;
    int ft = atoi(f[2]);
    if (ft >= 1 && ft <= 3) {
      if (cur_active_) { cur_.has_gsa = true; cur_.fix_type = (uint8_t)ft; cur_.last_mono_ms = mono_ms; }
      else { pending_gsa_ = true; pending_gsa_fix_ = (uint8_t)ft; }
    }
    return false;
  } else {
    sentences_ignored++;
    return false;
  }
  if (pending_gsa_ && cur_active_ && !cur_.has_gsa) { cur_.has_gsa = true; cur_.fix_type = pending_gsa_fix_; }
  pending_gsa_ = false;
  // The epoch is NOT committed as soon as GGA+RMC are both in, because GSA (no time field) usually
  // follows them in the same burst. It is committed when a sentence with a different time arrives or
  // when poll() sees the bus quiet for commit_timeout_ms.
  return committed;
}

}  // namespace wfg
