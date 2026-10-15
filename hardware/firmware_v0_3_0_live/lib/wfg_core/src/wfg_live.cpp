#include "wfg_live.h"
#include "wfg_proto.h"  // state_name()
#include <stdio.h>
#include <string.h>

namespace wfg {

// ---------------------------------------------------------------- helpers
static bool is_space(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' || c == '\f'; }

struct Tok {
  const char* p;
  size_t n;
};
// Splits on whitespace like the protocol's sscanf("%s"). Fills at most max tokens, returns the total count.
static int split_tokens(const char* s, Tok* t, int max) {
  int k = 0;
  while (*s) {
    while (*s && is_space(*s)) s++;
    if (!*s) break;
    const char* b = s;
    while (*s && !is_space(*s)) s++;
    if (k < max) { t[k].p = b; t[k].n = (size_t)(s - b); }
    k++;
  }
  return k;
}
static bool tok_is(const Tok& t, const char* w) {
  size_t n = strlen(w);
  return t.n == n && memcmp(t.p, w, n) == 0;
}

// snprintf result -> line length, or 0 (and an empty buffer) if it failed, was cut or is longer than kLiveMaxLine.
static size_t finish(char* buf, int n, size_t cap) {
  if (n <= 0 || (size_t)n >= cap || (size_t)n > kLiveMaxLine) {
    if (cap) buf[0] = 0;
    return 0;
  }
  return (size_t)n;
}

// Hundredths -> one decimal, rounded half away from zero ("-0.0" is written as "0.0").
static void fmt_tenths_from_centi(char* o, size_t n, int64_t centi) {
  bool neg = centi < 0;
  uint64_t a = neg ? (uint64_t)(-(centi + 1)) + 1u : (uint64_t)centi;
  uint64_t t = (a + 5u) / 10u;
  if (t == 0) neg = false;
  snprintf(o, n, "%s%llu.%llu", neg ? "-" : "", (unsigned long long)(t / 10u), (unsigned long long)(t % 10u));
}

// Course in 0.01 degree -> degrees with one decimal, rounded; 360.0 is written as 0.0.
static void fmt_course(char* o, size_t n, uint16_t cdeg) {
  uint32_t t = ((uint32_t)cdeg + 5u) / 10u;
  if (t == 3600u) t = 0;
  snprintf(o, n, "%u.%u", (unsigned)(t / 10u), (unsigned)(t % 10u));
}

static const char* fix_type_name(uint8_t ft) {
  switch (ft) {
    case 1: return "NONE";
    case 2: return "2D";
    case 3: return "3D";
    default: return nullptr;
  }
}

// ---------------------------------------------------------------- formatters
size_t Live::fmtEpoch(char* buf, size_t cap, const GnssEpoch& e, uint8_t logger_state, int32_t session_no,
                      uint8_t mode) {
  char utc[48] = "null", q[8] = "null", ft[8] = "null", su[8] = "null", hd[32] = "null";
  char la[24] = "null", lo[24] = "null", al[32] = "null", sp[32] = "null", co[16] = "null";
  char nr[24] = "null", ss[16] = "null";
  if (e.has_time && e.has_date) {
    char t[40];
    fmt_iso(e.utc_date, e.utc_ms_of_day, t);
    snprintf(utc, sizeof(utc), "\"%s\"", t);
  }
  if (e.has_gga && e.gga_quality != 0xFF) snprintf(q, sizeof(q), "%u", (unsigned)e.gga_quality);
  const char* ftn = e.has_gsa ? fix_type_name(e.fix_type) : nullptr;
  if (ftn) snprintf(ft, sizeof(ft), "\"%s\"", ftn);
  if (e.sats_valid) snprintf(su, sizeof(su), "%u", (unsigned)e.sats);
  if (e.hdop_valid) fmt_tenths_from_centi(hd, sizeof(hd), e.hdop_x100);
  if (e.pos_valid) {
    fmt_e7(e.lat_e7, la);
    fmt_e7(e.lon_e7, lo);
    if (e.alt_valid) fmt_tenths_from_centi(al, sizeof(al), e.alt_cm);  // the logger stores altitude only with a fix
  }
  if (e.speed_valid) fmt_centi(e.speed_cmps, sp);
  if (e.course_valid) fmt_course(co, sizeof(co), e.course_cdeg);
  if (!e.pos_valid) snprintf(nr, sizeof(nr), "\"%s\"", nofix_reason_name(NOFIX_RECEIVER));  // as Logger::onEpoch
  if (session_no >= 0) snprintf(ss, sizeof(ss), "%ld", (long)session_no);
  int n = snprintf(buf, cap,
                   "#J {\"v\":1,\"t\":\"ep\",\"ms\":%lu,\"utc\":%s,\"fix\":%d,\"q\":%s,\"ft\":%s,\"su\":%s,\"hd\":%s,"
                   "\"la\":%s,\"lo\":%s,\"al\":%s,\"sp\":%s,\"co\":%s,\"nr\":%s,\"rs\":\"%s\",\"ss\":%s,\"md\":\"%s\"}\n",
                   (unsigned long)e.first_mono_ms, utc, e.pos_valid ? 1 : 0, q, ft, su, hd, la, lo, al, sp, co, nr,
                   state_name(logger_state), ss, mode_name(mode));
  return finish(buf, n, cap);
}

size_t Live::fmtRecord(char* buf, size_t cap, const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size) {
  static const char digits[] = "0123456789abcdef";
  char hx[2 * WFG_RECORD_SIZE + 1];
  for (size_t i = 0; i < WFG_RECORD_SIZE; i++) {
    hx[2 * i] = digits[rec[i] >> 4];
    hx[2 * i + 1] = digits[rec[i] & 15];
  }
  hx[2 * WFG_RECORD_SIZE] = 0;
  // The record's CRC-32 is the u32 (little-endian) at bytes 44..47.
  uint32_t crc = (uint32_t)rec[44] | ((uint32_t)rec[45] << 8) | ((uint32_t)rec[46] << 16) | ((uint32_t)rec[47] << 24);
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"rec\",\"seq\":%lu,\"ty\":%u,\"b\":%lu,\"crc\":\"%08lx\",\"hx\":\"%s\"}\n",
                   (unsigned long)seq, (unsigned)rec[2], (unsigned long)file_size, (unsigned long)crc, hx);
  return finish(buf, n, cap);
}

size_t Live::fmtStatus(char* buf, size_t cap, int32_t vbat_mv, int64_t free_bytes) {
  char vb[16] = "null", ff[16] = "null";
  if (vbat_mv >= 0) snprintf(vb, sizeof(vb), "%ld", (long)vbat_mv);
  // capped at 4294967295 like the STATUS record's fs_free_bytes field
  if (free_bytes >= 0)
    snprintf(ff, sizeof(ff), "%lu", (unsigned long)(free_bytes > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)free_bytes));
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"st\",\"vb\":%s,\"ff\":%s}\n", vb, ff);
  return finish(buf, n, cap);
}

size_t Live::fmtEvent(char* buf, size_t cap, uint32_t event_no, bool located) {
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"ev\",\"n\":%lu,\"loc\":%d}\n", (unsigned long)event_no, located ? 1 : 0);
  return finish(buf, n, cap);
}

size_t Live::fmtSessionStart(char* buf, size_t cap, uint32_t session_no, uint8_t mode, uint8_t start_reason) {
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"ss\",\"ss\":%lu,\"md\":\"%s\",\"sr\":\"%s\"}\n",
                   (unsigned long)session_no, mode_name(mode), start_reason_name(start_reason));
  return finish(buf, n, cap);
}

size_t Live::fmtSessionEnd(char* buf, size_t cap, uint32_t session_no, int end_reason, uint32_t n_records) {
  char er[40] = "null";
  if (end_reason >= 0) snprintf(er, sizeof(er), "\"%s\"", end_reason_name((uint8_t)end_reason));
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"se\",\"ss\":%lu,\"er\":%s,\"n\":%lu}\n", (unsigned long)session_no, er,
                   (unsigned long)n_records);
  return finish(buf, n, cap);
}

size_t Live::fmtDrop(char* buf, size_t cap, uint32_t count) {
  int n = snprintf(buf, cap, "#J {\"v\":1,\"t\":\"drop\",\"n\":%lu}\n", (unsigned long)count);
  return finish(buf, n, cap);
}

size_t Live::fmtNmea(char* buf, size_t cap, const char* sentence) {
  if (!sentence) return finish(buf, 0, cap);
  size_t len = 0;
  for (const char* p = sentence; *p; p++, len++) {
    uint8_t u = (uint8_t)*p;
    if (u < 0x20 || u > 0x7E || len >= kLiveNmeaMax) return finish(buf, 0, cap);
  }
  if (len == 0) return finish(buf, 0, cap);
  int n = snprintf(buf, cap, "#N %s\n", sentence);
  return finish(buf, n, cap);
}

// ---------------------------------------------------------------- commands
bool Live::handleCommand(const char* line, Sink& reply) {
  if (!line) return false;
  Tok t[4];
  int k = split_tokens(line, t, 4);
  if (k < 1 || !tok_is(t[0], "LIVE")) return false;
  if (k == 2 && tok_is(t[1], "ON")) {
    if (!on_) drops_ = 0;  // a new stream starts without an old count
    on_ = true;
    reply.puts("OK LIVE ON\n");
  } else if (k == 2 && tok_is(t[1], "OFF")) {
    on_ = false;
    drops_ = 0;
    reply.puts("OK LIVE OFF\n");
  } else if (k == 3 && tok_is(t[1], "NMEA") && tok_is(t[2], "ON")) {
    nmea_ = true;
    reply.puts("OK LIVE NMEA ON\n");
  } else if (k == 3 && tok_is(t[1], "NMEA") && tok_is(t[2], "OFF")) {
    nmea_ = false;
    reply.puts("OK LIVE NMEA OFF\n");
  } else {
    reply.puts("ERR LIVE bad-argument\n");
  }
  return true;
}

// ---------------------------------------------------------------- output with the drop rule
void Live::countDrop() {
  if (drops_ != 0xFFFFFFFFu) drops_++;
  if (dropped_total_ != 0xFFFFFFFFu) dropped_total_++;
}

bool Live::emit(const char* line, size_t n) {
  if (n == 0 || n > kLiveMaxLine) {  // cannot be formatted within the limit: never sent, so counted
    countDrop();
    return false;
  }
  size_t avail = out_.availableForWrite();
  if (drops_) {
    char d[48];
    size_t dn = fmtDrop(d, sizeof(d), drops_);
    if (dn == 0 || avail < dn || avail - dn < n) {
      countDrop();
      return false;
    }
    if (!out_.write(d, dn)) {
      countDrop();
      return false;
    }
    drops_ = 0;
  } else if (avail < n) {
    countDrop();
    return false;
  }
  if (!out_.write(line, n)) {
    countDrop();
    return false;
  }
  if (sent_ != 0xFFFFFFFFu) sent_++;
  return true;
}

bool Live::epoch(const GnssEpoch& e, uint8_t logger_state, int32_t session_no, uint8_t mode) {
  if (!on_) return false;
  size_t n = fmtEpoch(line_, sizeof(line_), e, logger_state, session_no, mode);
  return emit(line_, n);
}

bool Live::status(int32_t vbat_mv, int64_t free_bytes) {
  if (!on_) return false;
  size_t n = fmtStatus(line_, sizeof(line_), vbat_mv, free_bytes);
  return emit(line_, n);
}

bool Live::event(uint32_t event_no, bool located) {
  if (!on_) return false;
  size_t n = fmtEvent(line_, sizeof(line_), event_no, located);
  return emit(line_, n);
}

bool Live::nmea(const char* sentence) {
  if (!on_ || !nmea_) return false;
  size_t n = fmtNmea(line_, sizeof(line_), sentence);
  return emit(line_, n);
}

// ---------------------------------------------------------------- records and sessions
void Live::finishSession() {
  announced_ = false;
  bool same = cur_valid_ && cur_no_ == announced_no_;
  int er = same ? cur_end_reason_ : -1;
  uint32_t n_records = same ? cur_last_seq_ + 1u : 0u;
  if (!on_) return;
  size_t n = fmtSessionEnd(line_, sizeof(line_), announced_no_, er, n_records);
  emit(line_, n);
}

void Live::onRecord(const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size) {
  Record r;
  bool ok = decode(rec, r);
  if (ok && r.h.type == REC_SESSION_START) {
    if (announced_) finishSession();  // a new session file means the previous session is over
    cur_valid_ = true;
    cur_no_ = r.start.session_no;
    cur_end_reason_ = -1;
  }
  if (cur_valid_) {
    cur_last_seq_ = seq;
    if (ok && r.h.type == REC_SESSION_END) cur_end_reason_ = r.end.reason;
  }
  if (!on_) return;
  size_t n = fmtRecord(line_, sizeof(line_), rec, seq, file_size);
  emit(line_, n);
  if (ok && r.h.type == REC_STATUS) {
    int32_t vb = ((r.st.flags & ST_BATT_VALID) && r.st.vbat_mv != 0xFFFF) ? (int32_t)r.st.vbat_mv : -1;
    n = fmtStatus(line_, sizeof(line_), vb, (int64_t)r.st.fs_free_bytes);
    emit(line_, n);
  }
}

void Live::sessionStarted(uint32_t session_no, uint8_t mode, uint8_t start_reason) {
  if (announced_) finishSession();
  announced_ = true;
  announced_no_ = session_no;
  if (!on_) return;
  size_t n = fmtSessionStart(line_, sizeof(line_), session_no, mode, start_reason);
  emit(line_, n);
}

void Live::sessionCheck(bool recording) {
  if (announced_ && !recording) finishSession();
}

void live_record_observer(const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size, void* ctx) {
  if (ctx) static_cast<Live*>(ctx)->onRecord(rec, seq, file_size);
}

// ---------------------------------------------------------------- raw NMEA sentences
bool NmeaLineCollector::feed(char c) {
  uint8_t u = (uint8_t)c;
  if (u == '\r' || u == '\n') {
    bool ready = active_ && !bad_;
    if (active_ && bad_) discarded_++;
    buf_[len_] = 0;
    active_ = false;
    bad_ = false;
    len_ = 0;
    return ready;
  }
  if (u == '$') {
    if (active_) discarded_++;  // cut short by the next sentence (no CR/LF)
    active_ = true;
    bad_ = false;
    buf_[0] = '$';
    len_ = 1;
    return false;
  }
  if (!active_ || bad_) return false;
  if (u < 0x20 || u > 0x7E || len_ >= kLiveNmeaMax) {
    bad_ = true;
    return false;
  }
  buf_[len_++] = (char)u;
  return false;
}

// ---------------------------------------------------------------- transmit queue estimate
void TxQueueModel::drain(uint64_t now_us) {
  if (!have_time_) {
    have_time_ = true;
    last_us_ = now_us;
    return;
  }
  if (now_us <= last_us_) return;
  uint64_t dt = now_us - last_us_;
  last_us_ = now_us;
  if (dt >= 60000000ull) {  // a minute without writes: everything has been sent
    queued_ub_ = 0;
    return;
  }
  uint64_t d = dt * (uint64_t)rate_;  // bytes x 1e6
  queued_ub_ = queued_ub_ > d ? queued_ub_ - d : 0;
}

uint32_t TxQueueModel::queuedBytes(uint64_t now_us) {
  drain(now_us);
  return (uint32_t)((queued_ub_ + 999999ull) / 1000000ull);
}

uint32_t TxQueueModel::freeBytes(uint64_t now_us) {
  uint32_t q = queuedBytes(now_us);
  return q >= cap_ ? 0u : cap_ - q;
}

void TxQueueModel::add(size_t n, uint64_t now_us) {
  drain(now_us);
  queued_ub_ += ((uint64_t)n + overhead_) * 1000000ull;
}

}  // namespace wfg
