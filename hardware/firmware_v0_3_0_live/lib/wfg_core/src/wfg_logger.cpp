#include "wfg_logger.h"
#include "wfg_sha256.h"
#include <string.h>
#include <stdlib.h>
#include <algorithm>

namespace wfg {

static const char* kMeta = "meta.txt";
static const char* kMetaTmp = "meta.tmp";

// ---------- civil date helpers (proleptic Gregorian, days since 1970-01-01) ----------
static int64_t days_from_civil(int64_t y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int64_t era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = (unsigned)(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + (int64_t)doe - 719468;
}
static void civil_from_days(int64_t z, int& y, unsigned& m, unsigned& d) {
  z += 719468;
  const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
  const unsigned doe = (unsigned)(z - era * 146097);
  const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  const int64_t yy = (int64_t)yoe + era * 400;
  const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const unsigned mp = (5 * doy + 2) / 153;
  d = doy - (153 * mp + 2) / 5 + 1;
  m = mp < 10 ? mp + 3 : mp - 9;
  y = (int)(yy + (m <= 2));
}
int64_t utc_epoch_ms(uint32_t ymd, uint32_t ms_of_day) {
  int64_t days = days_from_civil(ymd / 10000, (ymd / 100) % 100, ymd % 100);
  return days * 86400000LL + ms_of_day;
}
void epoch_ms_to_utc(int64_t ms, uint32_t& ymd, uint32_t& ms_of_day) {
  int64_t days = ms >= 0 ? ms / 86400000LL : -((-ms + 86400000LL - 1) / 86400000LL);
  ms_of_day = (uint32_t)(ms - days * 86400000LL);
  int y; unsigned m, d;
  civil_from_days(days, y, m, d);
  ymd = (uint32_t)(y * 10000 + m * 100 + d);
}

// ---------- names ----------
bool Logger::validName(const char* n) {
  // S + 6 digits + ".wfg"
  if (!n || strlen(n) != 11 || n[0] != 'S') return false;
  for (int i = 1; i <= 6; i++) if (n[i] < '0' || n[i] > '9') return false;
  return strcmp(n + 7, ".wfg") == 0;
}
void Logger::makeSessionId(uint32_t dev, uint32_t no, char* out, size_t n) {
  snprintf(out, n, "WFG-%08X-%06u", (unsigned)dev, (unsigned)no);
}
static void okName(const char* name, char* out, size_t n) {  // S000001.wfg -> S000001.ok
  snprintf(out, n, "%.7s.ok", name);
}

// ---------- meta (boot counter, next session number) ----------
void Logger::loadMeta() {
  boot_count_ = 0;
  next_session_no_ = 1;
  FILE* f = st_.open(kMeta, "rb");
  if (f) {
    unsigned b = 0, s = 1;
    if (fscanf(f, "%u %u", &b, &s) == 2) { boot_count_ = b; next_session_no_ = s ? s : 1; }
    st_.close(f);
  }
}
bool Logger::saveMeta() {
  FILE* f = st_.open(kMetaTmp, "wb");
  if (!f) return false;
  char line[40];
  int n = snprintf(line, sizeof(line), "%u %u\n", (unsigned)boot_count_, (unsigned)next_session_no_);
  bool ok = st_.write(f, (const uint8_t*)line, n) == (size_t)n && st_.sync(f);
  st_.close(f);
  if (!ok) { st_.remove(kMetaTmp); return false; }
  if (!st_.rename(kMetaTmp, kMeta)) {
    st_.remove(kMeta);  // some VFS renames refuse to replace
    return st_.rename(kMetaTmp, kMeta);
  }
  return true;
}

struct MaxNoCtx { uint32_t max_no; };
static void maxno_cb(const char* name, long, void* ctx) {
  if (strlen(name) >= 7 && name[0] == 'S') {
    bool digits = true;
    for (int i = 1; i <= 6; i++) if (name[i] < '0' || name[i] > '9') digits = false;
    if (digits) {
      uint32_t no = (uint32_t)atoi(name + 1);
      MaxNoCtx* c = (MaxNoCtx*)ctx;
      if (no > c->max_no) c->max_no = no;
    }
  }
}

int Logger::begin(RecoveryItem* items, int max_items) {
  loadMeta();
  boot_count_++;
  MaxNoCtx c{0};
  st_.list(maxno_cb, &c);  // never reuse a session number even if meta.txt was lost
  if (c.max_no + 1 > next_session_no_) next_session_no_ = c.max_no + 1;
  saveMeta();
  return recoverAll(items, max_items);
}

// ---------- recovery ----------
static void collect_cb(const char* name, long, void* ctx) {
  if (Logger::validName(name)) ((std::vector<uint32_t>*)ctx)->push_back((uint32_t)atoi(name + 1));
}

std::vector<uint32_t> Logger::sessionNumbers() {
  std::vector<uint32_t> v;
  st_.list(collect_cb, &v);
  std::sort(v.begin(), v.end());
  return v;
}

int Logger::recoverAll(RecoveryItem* items, int max_items) {
  // No count limit: every session file is checked (review R4). items[] only reports the first max_items.
  std::vector<uint32_t> nums = sessionNumbers();
  int recovered = 0;
  for (size_t i = 0; i < nums.size(); i++) {
    char name[20];
    snprintf(name, sizeof(name), "S%06u.wfg", (unsigned)nums[i]);
    long sz = st_.size(name);
    if (sz < 0) continue;
    uint32_t whole = (uint32_t)(sz / WFG_RECORD_SIZE);
    uint8_t buf[WFG_RECORD_SIZE];
    Record r;
    // Fast path: closed session (last whole record is a valid END and no trailing bytes).
    FILE* f = st_.open(name, "rb");
    if (!f) continue;
    if (sz % WFG_RECORD_SIZE == 0 && whole > 0) {
      fseek(f, (long)(whole - 1) * WFG_RECORD_SIZE, SEEK_SET);
      if (fread(buf, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE && decode(buf, r) && r.h.type == REC_SESSION_END) {
        st_.close(f);
        continue;
      }
    }
    // Slow path: find the last valid record; everything after it is a torn tail.
    fseek(f, 0, SEEK_SET);
    int64_t last_valid = -1;
    uint32_t n_fix = 0, n_nofix = 0, n_ev = 0, n_clk = 0;
    bool first_ok = false;
    for (uint32_t k = 0; k < whole; k++) {
      if (fread(buf, 1, WFG_RECORD_SIZE, f) != WFG_RECORD_SIZE) break;
      if (decode(buf, r) && r.h.seq == k) {
        last_valid = k;
        if (k == 0 && r.h.type == REC_SESSION_START) first_ok = true;
      }
    }
    st_.close(f);
    RecoveryItem it;
    memset(&it, 0, sizeof(it));
    strncpy(it.name, name, sizeof(it.name) - 1);
    if (!first_ok) {
      // Unrecoverable header: keep the bytes for manual inspection; never delete.
      char bad[24];
      snprintf(bad, sizeof(bad), "%.7s.bad", name);
      st_.rename(name, bad);
      it.unrecoverable = true;
      if (items && recovered < max_items) items[recovered] = it;
      recovered++;
      continue;
    }
    long keep = (long)(last_valid + 1) * WFG_RECORD_SIZE;
    uint32_t torn = (uint32_t)(sz - keep);
    if (torn) st_.truncate(name, keep);
    // Recount and CRC the kept prefix (corrupt records in the middle are kept and counted as errors).
    f = st_.open(name, "rb");
    uint32_t crc = 0;
    uint32_t nrec = (uint32_t)(keep / WFG_RECORD_SIZE);
    for (uint32_t k = 0; f && k < nrec; k++) {
      if (fread(buf, 1, WFG_RECORD_SIZE, f) != WFG_RECORD_SIZE) break;
      crc = crc32_update(crc, buf, WFG_RECORD_SIZE);
      if (decode(buf, r)) {
        if (r.h.type == REC_FIX) n_fix++;
        else if (r.h.type == REC_NOFIX) n_nofix++;
        else if (r.h.type == REC_EVENT) n_ev++;
        else if (r.h.type == REC_CLOCK) n_clk++;
      }
    }
    if (f) st_.close(f);
    Record e;
    memset(&e, 0, sizeof(e));
    e.h.type = REC_SESSION_END;
    e.h.seq = nrec;
    e.h.mono_ms = 0;  // unknown: written after reboot, monotonic clock restarted
    e.end.reason = END_RECOVERED_ON_BOOT;
    e.end.n_records_before = nrec;
    e.end.n_fix = n_fix; e.end.n_nofix = n_nofix; e.end.n_events = n_ev; e.end.n_clock = n_clk;
    e.end.crc32_before = crc;
    e.end.torn_bytes_removed = torn;
    encode(e, buf);
    f = st_.open(name, "ab");
    bool closed = false;
    if (f) {
      closed = st_.write(f, buf, WFG_RECORD_SIZE) == WFG_RECORD_SIZE && st_.sync(f);
      st_.close(f);
      if (!closed) st_.truncate(name, keep);  // no room for END: leave OPEN, data intact
    }
    it.valid_records = nrec;
    it.torn_bytes_removed = torn;
    it.closed_now = closed;
    if (items && recovered < max_items) items[recovered] = it;
    recovered++;
  }
  return recovered;
}

// ---------- recording ----------
bool Logger::spaceOk() {
  if (++free_check_counter < cfg_.free_check_every_records) return true;
  free_check_counter = 0;
  return st_.freeBytes() >= cfg_.reserve_bytes;
}

bool Logger::append(Record& r, uint32_t mono_ms) {
  if (!f_) return false;
  bool is_end = r.h.type == REC_SESSION_END;
  if (!is_end && !spaceOk()) {
    stop(END_STORAGE_FULL, mono_ms);
    state_ = LS_FULL;
    return false;
  }
  r.h.seq = seq_;
  uint8_t buf[WFG_RECORD_SIZE];
  encode(r, buf);
  size_t w = st_.write(f_, buf, WFG_RECORD_SIZE);
  if (w != WFG_RECORD_SIZE) {
    // Out of space (or FS error) mid-record: cut the partial record off, then try to close cleanly.
    st_.close(f_);
    f_ = nullptr;
    st_.truncate(cur_name_, (long)seq_ * WFG_RECORD_SIZE);
    if (!is_end) {
      f_ = st_.open(cur_name_, "ab");
      if (f_) {
        Record e;
        memset(&e, 0, sizeof(e));
        e.h.type = REC_SESSION_END;
        e.h.mono_ms = mono_ms;
        e.end.reason = END_STORAGE_FULL;
        e.end.n_records_before = seq_;
        e.end.n_fix = n_fix_; e.end.n_nofix = n_nofix_; e.end.n_events = n_events_; e.end.n_clock = n_clock_;
        e.end.crc32_before = crc_all_;
        e.h.seq = seq_;
        encode(e, buf);
        if (st_.write(f_, buf, WFG_RECORD_SIZE) != WFG_RECORD_SIZE) {
          st_.close(f_); f_ = nullptr;
          st_.truncate(cur_name_, (long)seq_ * WFG_RECORD_SIZE);  // stays OPEN; recovered on next boot
        } else {
          st_.sync(f_); st_.close(f_); f_ = nullptr;
          if (rec_obs_) rec_obs_(buf, seq_, (uint32_t)((seq_ + 1) * WFG_RECORD_SIZE), rec_obs_ctx_);
        }
      }
    }
    state_ = LS_FULL;
    return false;
  }
  crc_all_ = crc32_update(crc_all_, buf, WFG_RECORD_SIZE);
  seq_++;
  switch (r.h.type) {
    case REC_FIX: n_fix_++; break;
    case REC_NOFIX: n_nofix_++; break;
    case REC_EVENT: n_events_++; break;
    case REC_CLOCK: n_clock_++; break;
    default: break;
  }
  if ((uint32_t)(mono_ms - last_sync_mono_) >= cfg_.sync_every_ms || r.h.type == REC_EVENT ||
      r.h.type == REC_SESSION_START) {
    st_.sync(f_);
    last_sync_mono_ = mono_ms;
  }
  if (rec_obs_) rec_obs_(buf, seq_ - 1, (uint32_t)(seq_ * WFG_RECORD_SIZE), rec_obs_ctx_);
  return true;
}

bool Logger::start(uint8_t mode, uint32_t mono_ms, uint8_t start_reason, uint32_t resumed_from, uint8_t reset_reason) {
  if (state_ == LS_RECORDING || state_ == LS_FULL) return false;
  if (st_.freeBytes() < cfg_.reserve_bytes + 8192) { state_ = LS_FULL; return false; }
  uint32_t no = next_session_no_;
  char name[20];
  snprintf(name, sizeof(name), "S%06u.wfg", (unsigned)no);
  while (st_.exists(name)) {  // never overwrite
    no++;
    snprintf(name, sizeof(name), "S%06u.wfg", (unsigned)no);
  }
  next_session_no_ = no + 1;
  saveMeta();
  f_ = st_.open(name, "wb");
  if (!f_) { state_ = LS_ERROR; return false; }
  strncpy(cur_name_, name, sizeof(cur_name_));
  makeSessionId(cfg_.device_id, no, cur_sid_, sizeof(cur_sid_));
  seq_ = 0; crc_all_ = 0; n_fix_ = n_nofix_ = n_events_ = n_clock_ = 0; n_status_ = 0;
  have_obs_ = false; have_fix_ = false; last_event_no_ = 0; last_obs_fix_ = false;
  have_epoch_row_ = false;
  last_row_mono_ = mono_ms;
  last_sync_mono_ = mono_ms;
  free_check_counter = 0;
  state_ = LS_RECORDING;
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_SESSION_START;
  r.h.mono_ms = mono_ms;
  r.start.device_id = cfg_.device_id;
  r.start.session_no = no;
  r.start.movement_mode = mode;
  r.start.board_rev = cfg_.board_rev;
  r.start.fw_version = cfg_.fw_version;
  r.start.log_interval_ms = cfg_.log_interval_ms;
  r.start.format_version = WFG_FORMAT_VERSION;
  r.start.record_size = WFG_RECORD_SIZE;
  r.start.boot_count = boot_count_;
  r.start.event_locate_max_age_ms = cfg_.event_locate_max_age_ms;
  r.start.start_reason = start_reason;
  r.start.resumed_from_session_no = resumed_from;
  r.start.reset_reason = reset_reason;
  if (!append(r, mono_ms)) { if (state_ == LS_RECORDING) state_ = LS_ERROR; return false; }
  if (have_offset_) {
    // UTC was already known before this session (GNSS keeps running while idle): restate it so each
    // session file is self-contained.
    Record c;
    memset(&c, 0, sizeof(c));
    c.h.type = REC_CLOCK;
    c.h.mono_ms = mono_ms;
    epoch_ms_to_utc(offset_ms_ + mono_ms, c.clk.utc_date, c.clk.utc_ms_of_day);
    c.clk.offset_ms = offset_ms_;
    c.clk.delta_ms = 0;
    c.clk.kind = CLOCK_FIRST_UTC;
    append(c, mono_ms);
  }
  if (state_ == LS_RECORDING) writeStatus(mono_ms);  // battery/storage at session start
  return state_ == LS_RECORDING;
}

void Logger::writeStatus(uint32_t mono_ms) {
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_STATUS;
  r.h.mono_ms = mono_ms;
  Status& t = r.st;
  t.vbat_mv = 0xFFFF;
  t.vbat_pin_mv = 0xFFFF;
  if (status_fn_) status_fn_(t, status_ctx_);
  uint64_t fr = st_.freeBytes(), tot = st_.totalBytes();
  t.fs_free_bytes = fr > 0xFFFFFFFFull ? 0xFFFFFFFFu : (uint32_t)fr;
  t.fs_total_bytes = tot > 0xFFFFFFFFull ? 0xFFFFFFFFu : (uint32_t)tot;
  if (nmea_) { t.nmea_ok = nmea_->sentences_ok; t.nmea_bad_checksum = nmea_->sentences_bad_checksum; }
  last_status_mono_ = mono_ms;
  if (append(r, mono_ms)) n_status_++;
}

void Logger::handleClock(const GnssEpoch& e, uint32_t mono_ms) {
  (void)mono_ms;
  // Only anchor UTC on receiver time that comes with a date and a valid solution: receivers can emit
  // a default/unsynchronised time before they have decoded satellite time. Raw NMEA time is still kept
  // on every observation row with its own validity bits.
  if (!(e.has_time && e.has_date && e.utc_date >= 20240101 && (e.rmc_active || e.pos_valid))) return;
  int64_t off = utc_epoch_ms(e.utc_date, e.utc_ms_of_day) - (int64_t)e.first_mono_ms;
  if (!have_offset_) {
    have_offset_ = true;
    offset_ms_ = off;
    if (state_ == LS_RECORDING) {
      Record c;
      memset(&c, 0, sizeof(c));
      c.h.type = REC_CLOCK;
      c.h.mono_ms = e.first_mono_ms;
      c.clk.utc_date = e.utc_date; c.clk.utc_ms_of_day = e.utc_ms_of_day;
      c.clk.offset_ms = off; c.clk.delta_ms = 0; c.clk.kind = CLOCK_FIRST_UTC;
      append(c, mono_ms);
    }
    return;
  }
  int64_t d = off - offset_ms_;
  if (d > (int64_t)cfg_.clock_jump_threshold_ms || d < -(int64_t)cfg_.clock_jump_threshold_ms) {
    offset_ms_ = off;
    if (state_ == LS_RECORDING) {
      Record c;
      memset(&c, 0, sizeof(c));
      c.h.type = REC_CLOCK;
      c.h.mono_ms = e.first_mono_ms;
      c.clk.utc_date = e.utc_date; c.clk.utc_ms_of_day = e.utc_ms_of_day;
      c.clk.offset_ms = off; c.clk.delta_ms = d; c.clk.kind = CLOCK_JUMP;
      append(c, mono_ms);
    }
  }
}

void Logger::onEpoch(const GnssEpoch& e, uint32_t mono_ms) {
  last_epoch_mono_ = mono_ms;
  have_epoch_ = true;
  handleClock(e, mono_ms);
  if (state_ != LS_RECORDING) return;
  // Rate limit to log_interval (tolerate 20 % jitter); if the receiver runs faster, extra epochs are skipped.
  if (have_epoch_row_ && (int32_t)(e.first_mono_ms - last_epoch_row_mono_) < (int32_t)(cfg_.log_interval_ms * 8 / 10))
    return;
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = e.pos_valid ? REC_FIX : REC_NOFIX;
  r.h.mono_ms = e.first_mono_ms;  // receive time of the epoch's first sentence
  uint32_t age10 = (mono_ms - e.first_mono_ms) / 10;
  r.h.flags0 = age10 > 255 ? 255 : (uint8_t)age10;
  Obs& o = r.obs;
  uint16_t v = 0;
  if (e.has_time) { v |= V_TIME; o.utc_ms_of_day = e.utc_ms_of_day; } else o.utc_ms_of_day = 0xFFFFFFFF;
  if (e.has_date) { v |= V_DATE; o.utc_date = e.utc_date; }
  if (e.pos_valid) { v |= V_POS; o.lat_e7 = e.lat_e7; o.lon_e7 = e.lon_e7; }
  if (e.pos_valid && e.alt_valid) { v |= V_ALT; o.alt_cm = e.alt_cm; }
  if (e.speed_valid) { v |= V_SPEED; o.speed_cmps = e.speed_cmps; }
  if (e.course_valid) { v |= V_COURSE; o.course_cdeg = e.course_cdeg; }
  if (e.hdop_valid) { v |= V_HDOP; o.hdop_x100 = e.hdop_x100; }
  if (e.sats_valid) { v |= V_SATS; o.sats = e.sats; }
  if (e.rmc_active) v |= V_RMC_ACTIVE;
  if (e.has_gsa) { v |= V_FIXTYPE; o.fix_type = e.fix_type; }
  if (e.cksum_err) v |= V_CKSUM_ERR;
  o.gga_quality = e.has_gga ? e.gga_quality : 0xFF;
  o.nofix_reason = e.pos_valid ? NOFIX_NA : NOFIX_RECEIVER;
  o.valid = v;
  if (append(r, mono_ms)) {
    have_obs_ = true;
    have_epoch_row_ = true;
    last_epoch_row_mono_ = e.first_mono_ms;
    if ((int32_t)(e.first_mono_ms - last_row_mono_) > 0) last_row_mono_ = e.first_mono_ms;
    last_obs_fix_ = e.pos_valid;
    if (e.pos_valid) {
      have_fix_ = true;
      last_fix_seq_ = seq_ - 1;
      last_fix_mono_ = e.first_mono_ms;
      last_fix_lat_ = e.lat_e7;
      last_fix_lon_ = e.lon_e7;
    }
  }
}

void Logger::writeFiller(uint32_t mono_ms, uint8_t reason) {
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_NOFIX;
  r.h.mono_ms = mono_ms;
  r.h.flags0 = 0xFF;  // no epoch -> age not applicable
  r.obs.utc_ms_of_day = 0xFFFFFFFF;
  r.obs.gga_quality = 0xFF;
  r.obs.nofix_reason = reason;
  r.obs.valid = (reason == NOFIX_CKSUM_ONLY) ? V_CKSUM_ERR : 0;
  if (append(r, mono_ms)) {
    have_obs_ = true;
    last_row_mono_ = mono_ms;
    last_obs_fix_ = false;
  }
}

void Logger::tick(uint32_t mono_ms, const NmeaParser* nmea) {
  if (nmea) nmea_ = nmea;
  if (state_ != LS_RECORDING) return;
  if (cfg_.status_every_ms && (uint32_t)(mono_ms - last_status_mono_) >= cfg_.status_every_ms) {
    writeStatus(mono_ms);
    if (state_ != LS_RECORDING) return;
  }
  // Gap filler: if no epoch produced a row for nodata_after_ms, write one NOFIX row per log interval so
  // the gap is explicit in the file. Never while an epoch is still arriving (keeps mono_ms ordered).
  uint32_t since_epoch = have_epoch_row_ ? mono_ms - last_epoch_row_mono_ : mono_ms - last_row_mono_;
  bool pending = nmea && nmea->epochPending();
  if (!pending && since_epoch >= cfg_.nodata_after_ms && (uint32_t)(mono_ms - last_row_mono_) >= cfg_.log_interval_ms) {
    uint8_t reason = NOFIX_NO_DATA;
    if (nmea) {
      bool talking = nmea->sentences_ok > 0 && (uint32_t)(mono_ms - nmea->last_sentence_mono_ms) < cfg_.nodata_after_ms;
      if (talking) reason = NOFIX_RECEIVER;  // valid NMEA but no timed solution (e.g. cold start)
      else if (nmea->bad_checksum_since_take) reason = NOFIX_CKSUM_ONLY;
    }
    writeFiller(mono_ms, reason);
  }
  if (state_ == LS_RECORDING && f_ && (uint32_t)(mono_ms - last_sync_mono_) >= cfg_.sync_every_ms) {
    st_.sync(f_);
    last_sync_mono_ = mono_ms;
  }
}

bool Logger::markEvent(uint32_t press_mono_ms, uint16_t dur, uint32_t now_mono_ms) {
  if (state_ != LS_RECORDING) return false;
  Record r;
  memset(&r, 0, sizeof(r));
  r.h.type = REC_EVENT;
  r.h.mono_ms = now_mono_ms;
  Event& e = r.ev;
  e.event_no = (uint32_t)(last_event_no_ + 1);
  e.press_mono_ms = press_mono_ms;
  e.press_duration_ms = dur;
  e.source = 1;
  e.ref_fix_seq = 0xFFFFFFFF;
  e.ref_fix_age_ms = 0xFFFFFFFF;
  // Only a fix received at or before the press counts (no look-ahead, no interpolation).
  if (have_fix_ && (int32_t)(press_mono_ms - last_fix_mono_) >= 0) {
    e.ref_fix_seq = last_fix_seq_;
    e.ref_fix_age_ms = press_mono_ms - last_fix_mono_;
    if (e.ref_fix_age_ms <= cfg_.event_locate_max_age_ms) {
      e.located = 1;
      e.lat_e7 = last_fix_lat_;
      e.lon_e7 = last_fix_lon_;
    }
  }
  if (!append(r, now_mono_ms)) return false;
  last_event_no_ = (int32_t)e.event_no;
  last_event_located_ = e.located;
  last_event_mono_ = now_mono_ms;
  return true;
}

bool Logger::stop(uint8_t reason, uint32_t mono_ms) {
  if (!f_ || state_ != LS_RECORDING) return false;
  Record e;
  memset(&e, 0, sizeof(e));
  e.h.type = REC_SESSION_END;
  e.h.mono_ms = mono_ms;
  e.end.reason = reason;
  e.end.n_records_before = seq_;
  e.end.n_fix = n_fix_; e.end.n_nofix = n_nofix_; e.end.n_events = n_events_; e.end.n_clock = n_clock_;
  e.end.crc32_before = crc_all_;
  bool ok = append(e, mono_ms);
  if (f_) { st_.sync(f_); st_.close(f_); f_ = nullptr; }
  state_ = (reason == END_STORAGE_FULL) ? LS_FULL : LS_IDLE;
  return ok;
}

// ---------- integrity ----------
bool IntegrityReport::ok() const {
  return readable && n_crc_errors == 0 && n_seq_errors == 0 && trailing_bytes == 0 && has_start && has_end &&
         end_counts_match && end_crc_match;
}

IntegrityReport Logger::checkSession(Storage& st, const char* name) {
  IntegrityReport rep;
  long sz = st.size(name);
  if (sz < 0) { strcpy(rep.status, "MISSING"); return rep; }
  if (sz == 0) { rep.readable = true; strcpy(rep.status, "EMPTY"); return rep; }
  FILE* f = st.open(name, "rb");
  if (!f) { strcpy(rep.status, "UNREADABLE"); return rep; }
  rep.readable = true;
  rep.trailing_bytes = (uint32_t)(sz % WFG_RECORD_SIZE);
  uint32_t whole = (uint32_t)(sz / WFG_RECORD_SIZE);
  uint8_t buf[WFG_RECORD_SIZE];
  Record r;
  uint32_t crc = 0;
  for (uint32_t k = 0; k < whole; k++) {
    if (fread(buf, 1, WFG_RECORD_SIZE, f) != WFG_RECORD_SIZE) break;
    uint32_t crc_before = crc;
    crc = crc32_update(crc, buf, WFG_RECORD_SIZE);
    rep.n_records++;
    if (!decode(buf, r)) {
      rep.n_crc_errors++;
      if (rep.first_bad_index < 0) rep.first_bad_index = (int32_t)k;
      continue;
    }
    if (r.h.seq != k) { rep.n_seq_errors++; if (rep.first_bad_index < 0) rep.first_bad_index = (int32_t)k; }
    switch (r.h.type) {
      case REC_SESSION_START: if (k == 0) rep.has_start = true; break;
      case REC_FIX: rep.n_fix++; break;
      case REC_NOFIX: rep.n_nofix++; break;
      case REC_EVENT: rep.n_events++; break;
      case REC_CLOCK: rep.n_clock++; break;
      case REC_STATUS: rep.n_status++; break;
      case REC_SESSION_END:
        if (k == whole - 1) {
          rep.has_end = true;
          rep.end_reason = r.end.reason;
          rep.end_counts_match = r.end.n_records_before == k && r.end.n_fix == rep.n_fix &&
                                 r.end.n_nofix == rep.n_nofix && r.end.n_events == rep.n_events &&
                                 r.end.n_clock == rep.n_clock;
          rep.end_crc_match = r.end.crc32_before == crc_before;
        } else {
          rep.n_seq_errors++;  // END not at the end
        }
        break;
    }
  }
  st.close(f);
  if (rep.ok()) strcpy(rep.status, rep.end_reason == END_RECOVERED_ON_BOOT ? "RECOVERED" : "OK");
  else if (rep.n_crc_errors == 0 && rep.n_seq_errors == 0 && rep.has_start && !rep.has_end)
    strcpy(rep.status, rep.trailing_bytes ? "TORN_TAIL" : "OPEN");  // both are repaired by boot recovery
  else strcpy(rep.status, "CORRUPT");
  return rep;
}

// ---------- listing / export ----------
bool Logger::sessionInfo(const char* name, SessionInfo& s) {
  memset(&s, 0, sizeof(s));
  if (!validName(name)) return false;
  long sz = st_.size(name);
  if (sz < 0) return false;
  strncpy(s.name, name, sizeof(s.name) - 1);
  s.size = sz;
  s.n_records = (uint32_t)(sz / WFG_RECORD_SIZE);
  s.session_no = (uint32_t)atoi(name + 1);
  FILE* f = st_.open(name, "rb");
  if (!f) return false;
  uint8_t buf[WFG_RECORD_SIZE];
  Record r;
  uint32_t dev = cfg_.device_id;
  if (fread(buf, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE && decode(buf, r) && r.h.type == REC_SESSION_START) {
    s.mode = r.start.movement_mode;
    dev = r.start.device_id;
    s.start_reason = r.start.start_reason;
    s.resumed_from_session_no = r.start.resumed_from_session_no;
  }
  if (s.n_records > 0 && sz % WFG_RECORD_SIZE == 0) {
    fseek(f, (long)(s.n_records - 1) * WFG_RECORD_SIZE, SEEK_SET);
    if (fread(buf, 1, WFG_RECORD_SIZE, f) == WFG_RECORD_SIZE && decode(buf, r) && r.h.type == REC_SESSION_END) {
      s.closed = 1;
      s.end_reason = r.end.reason;
    }
  }
  st_.close(f);
  makeSessionId(dev, s.session_no, s.session_id, sizeof(s.session_id));
  char sha[65];
  s.exported = isExportConfirmed(name, sha) ? 1 : 0;
  return true;
}

int Logger::forEachSession(void (*cb)(const SessionInfo&, void*), void* ctx) {
  std::vector<uint32_t> nums = sessionNumbers();
  int n = 0;
  SessionInfo info;
  for (uint32_t no : nums) {
    char name[20];
    snprintf(name, sizeof(name), "S%06u.wfg", (unsigned)no);
    if (sessionInfo(name, info)) { cb(info, ctx); n++; }
  }
  return n;
}

static void count_unexp_cb(const SessionInfo& s, void* ctx) { if (!s.exported) (*(int*)ctx)++; }
int Logger::countUnexported() {
  int n = 0;
  forEachSession(count_unexp_cb, &n);
  return n;
}

bool Logger::sha256File(const char* name, char hex[65], long* size_out) {
  FILE* f = st_.open(name, "rb");
  if (!f) return false;
  Sha256 h;
  uint8_t buf[512];
  long total = 0;
  size_t n;
  while ((n = fread(buf, 1, sizeof(buf), f)) > 0) { h.update(buf, n); total += (long)n; }
  st_.close(f);
  h.finishHex(hex);
  if (size_out) *size_out = total;
  return true;
}

bool Logger::isExportConfirmed(const char* name, char* sha_out, bool full_verify) {
  char okn[20];
  okName(name, okn, sizeof(okn));
  FILE* f = st_.open(okn, "rb");
  if (!f) return false;
  char line[100] = {0};
  size_t n = fread(line, 1, sizeof(line) - 1, f);
  st_.close(f);
  line[n] = 0;
  if (n < 64) return false;
  char want[65];
  memcpy(want, line, 64);
  want[64] = 0;
  long rec_size = -1;
  sscanf(line + 64, " %ld", &rec_size);   // ".ok" = "<sha256> <size> <via>"
  long cur_size = st_.size(name);
  if (cur_size < 0) return false;
  if (rec_size >= 0 && rec_size != cur_size) return false;  // file changed since confirmation
  if (full_verify || rec_size < 0) {
    char cur[65];
    if (!sha256File(name, cur)) return false;
    if (strcmp(want, cur) != 0) return false;  // content changed since confirmation -> not confirmed
  }
  if (sha_out) strcpy(sha_out, want);
  return true;
}

bool Logger::confirmExport(const char* name, const char* sha_hex, const char* via) {
  if (!validName(name) || !sha_hex || strlen(sha_hex) != 64) return false;
  if (state_ == LS_RECORDING && strcmp(name, cur_name_) == 0) return false;
  IntegrityReport rep = checkSession(st_, name);
  if (!rep.has_end) return false;  // only closed sessions can be confirmed
  char cur[65];
  if (!sha256File(name, cur)) return false;
  for (int i = 0; i < 64; i++) {
    char c = sha_hex[i];
    if (c >= 'A' && c <= 'F') c = (char)(c - 'A' + 'a');
    if (c != cur[i]) return false;
  }
  char okn[20];
  okName(name, okn, sizeof(okn));
  FILE* f = st_.open(okn, "wb");
  if (!f) return false;
  char line[100];
  int n = snprintf(line, sizeof(line), "%s %ld %s\n", cur, st_.size(name), via ? via : "unknown");
  bool ok = st_.write(f, (const uint8_t*)line, (size_t)n) == (size_t)n && st_.sync(f);
  st_.close(f);
  return ok;
}

bool Logger::deleteConfirmedSession(const char* name, const char* sha_hex) {
  if (!validName(name)) return false;
  if (state_ == LS_RECORDING && strcmp(name, cur_name_) == 0) return false;
  char sha[65];
  if (!isExportConfirmed(name, sha, true)) return false;  // full re-hash before deleting
  if (!sha_hex || strncmp(sha, sha_hex, 64) != 0) return false;
  if (!st_.remove(name)) return false;
  char okn[20];
  okName(name, okn, sizeof(okn));
  st_.remove(okn);
  if (state_ == LS_FULL && st_.freeBytes() >= cfg_.reserve_bytes + 8192) state_ = LS_IDLE;
  return true;
}

}  // namespace wfg
