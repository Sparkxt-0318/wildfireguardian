// LIVE lines (firmware 0.3.0): an optional output stream over the USB serial link, so a laptop can follow the
// device while it records. Hardware independent (no Arduino headers): src/main.cpp and the host fake device
// (test/host/fake_device.cpp) share the command parser, the line formats and the drop rule.
//
// Commands (host -> device), each answered with one line:
//   LIVE ON          OK LIVE ON          start LIVE lines
//   LIVE OFF         OK LIVE OFF         stop all LIVE lines (the NMEA setting is kept)
//   LIVE NMEA ON     OK LIVE NMEA ON     also send raw NMEA (#N) whenever LIVE is on
//   LIVE NMEA OFF    OK LIVE NMEA OFF
//   LIVE <other>     ERR LIVE bad-argument
// Default after boot: LIVE OFF and NMEA OFF, nothing is sent, so tools that do not know LIVE see no change.
//
// Lines (device -> host): one line each, ASCII, at most 320 bytes including the '\n'. Every line starts with '#',
// so tools that do not know them ignore them like any other log line.
//   #J {"v":1,"t":"ep",...}      one per GNSS epoch, idle or recording
//   #J {"v":1,"t":"rec",...}     every record written to the session file
//   #J {"v":1,"t":"st",...}      with every STATUS record while recording, every 10 s while idle
//   #J {"v":1,"t":"ev",...}      button mark
//   #J {"v":1,"t":"ss",...}      session start
//   #J {"v":1,"t":"se",...}      session end
//   #J {"v":1,"t":"drop","n":N}  N lines before this one were not sent
//   #N <sentence>                raw NMEA sentence as received (only while LIVE and LIVE NMEA are both on)
// Field by field: ../../../README.md, "LIVE lines".
//
// Never blocks: a line is written only when LiveSink::availableForWrite() covers the whole line. Otherwise it is
// dropped and counted. While the count is not 0, the next line is written only if the drop line and that line both
// fit; then the drop line goes first and the count restarts at 0. If they do not both fit, that line is dropped
// and counted too, so every gap is reported by a drop line at the place where it happened.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "wfg_export.h"  // Sink (protocol replies)
#include "wfg_nmea.h"    // GnssEpoch
#include "wfg_record.h"

namespace wfg {

static const size_t kLiveMaxLine = 320;   // bytes per line including the '\n'
static const size_t kLiveNmeaMax = 100;   // longest raw sentence forwarded as #N (characters, without CR/LF)

// Where LIVE lines go. write() is called only with n <= availableForWrite(), so it never has to wait.
class LiveSink {
 public:
  virtual ~LiveSink() {}
  virtual size_t availableForWrite() = 0;
  virtual bool write(const char* s, size_t n) = 0;
};

class Live {
 public:
  explicit Live(LiveSink& out) : out_(out) {}

  // USB line. Returns true if its first word is "LIVE" (the reply has then been written to `reply`), false if the
  // line is not a LIVE command (nothing written).
  bool handleCommand(const char* line, Sink& reply);
  bool on() const { return on_; }
  bool nmeaOn() const { return nmea_; }

  // Emitters. They do nothing while LIVE is off and return true if the line was written.
  // epoch: session_no < 0 means not recording (null); mode is the current movement mode.
  bool epoch(const GnssEpoch& e, uint8_t logger_state, int32_t session_no, uint8_t mode);
  // status: vbat_mv < 0 or free_bytes < 0 means not known (null). Used every 10 s while idle.
  bool status(int32_t vbat_mv, int64_t free_bytes);
  bool event(uint32_t event_no, bool located);
  bool nmea(const char* sentence);

  // Record observer: pass live_record_observer and this object to Logger::setRecordObserver(). Emits rec for every
  // record and st for every STATUS record. It also follows the session for se, also while LIVE is off.
  void onRecord(const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size);
  // Call after Logger::start() succeeded (owner start or auto-resume): emits ss. If the previous session that had an
  // ss has not had its se yet, that se is emitted first.
  void sessionStarted(uint32_t session_no, uint8_t mode, uint8_t start_reason);
  // Call after anything that can end a session (stop, or a logger call that may stop by itself when storage runs
  // out). Emits se once when the session that had an ss is no longer recording.
  void sessionCheck(bool recording);

  // Counters
  uint32_t pendingDrops() const { return drops_; }      // lines dropped since the last drop line
  uint32_t linesSent() const { return sent_; }          // LIVE lines written (drop lines not counted)
  uint32_t linesDropped() const { return dropped_total_; }

  // Line formatters, also used by the host tests. Each writes one complete line ("#J ...\n" or "#N ...\n") and a
  // terminating NUL into buf and returns its length in bytes, or 0 if the line would be longer than kLiveMaxLine
  // or does not fit into cap.
  static size_t fmtEpoch(char* buf, size_t cap, const GnssEpoch& e, uint8_t logger_state, int32_t session_no,
                         uint8_t mode);
  static size_t fmtRecord(char* buf, size_t cap, const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size);
  static size_t fmtStatus(char* buf, size_t cap, int32_t vbat_mv, int64_t free_bytes);
  static size_t fmtEvent(char* buf, size_t cap, uint32_t event_no, bool located);
  static size_t fmtSessionStart(char* buf, size_t cap, uint32_t session_no, uint8_t mode, uint8_t start_reason);
  // end_reason < 0: no SESSION_END record was written (null)
  static size_t fmtSessionEnd(char* buf, size_t cap, uint32_t session_no, int end_reason, uint32_t n_records);
  static size_t fmtDrop(char* buf, size_t cap, uint32_t n);
  // Only printable ASCII, at most kLiveNmeaMax characters; anything else gives 0.
  static size_t fmtNmea(char* buf, size_t cap, const char* sentence);

 private:
  bool emit(const char* line, size_t n);
  void countDrop();
  void finishSession();  // se for the session that had an ss
  LiveSink& out_;
  bool on_ = false;
  bool nmea_ = false;
  uint32_t drops_ = 0;
  uint32_t sent_ = 0;
  uint32_t dropped_total_ = 0;
  char line_[kLiveMaxLine + 64];
  // session following for se
  bool announced_ = false;     // ss given, se not yet
  uint32_t announced_no_ = 0;
  bool cur_valid_ = false;     // a SESSION_START record has been seen
  uint32_t cur_no_ = 0;        // its session number
  uint32_t cur_last_seq_ = 0;  // seq of the last record seen since then
  int cur_end_reason_ = -1;    // reason of the SESSION_END record seen since then, -1 if none
};

// Logger record observer that forwards to Live::onRecord(); ctx is the Live object.
void live_record_observer(const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size, void* ctx);

// Collects the bytes read from the GNSS UART into sentences for #N lines. A sentence starts at '$' (a '$' always
// starts a new one, as in NmeaParser) and ends before CR or LF. Sentences longer than kLiveNmeaMax characters or
// with bytes outside printable ASCII are discarded, so #N lines are always clean ASCII.
class NmeaLineCollector {
 public:
  // Returns true when a complete sentence is ready in line(); it stays valid until the next feed().
  bool feed(char c);
  const char* line() const { return buf_; }
  uint32_t discarded() const { return discarded_; }

 private:
  char buf_[kLiveNmeaMax + 1] = {0};
  size_t len_ = 0;
  bool active_ = false;
  bool bad_ = false;
  uint32_t discarded_ = 0;
};

// Estimate of the bytes still waiting in a UART transmit queue that sends at a steady rate (no flow control).
// Writes add their size plus a fixed per-write overhead; the queue drains at drain_bytes_per_s. src/main.cpp uses
// it on the classic ESP32, where HardwareSerial::availableForWrite() does not count writes that are already queued.
class TxQueueModel {
 public:
  TxQueueModel(uint32_t capacity, uint32_t drain_bytes_per_s, uint32_t per_write_overhead)
      : cap_(capacity), rate_(drain_bytes_per_s), overhead_(per_write_overhead) {}
  uint32_t freeBytes(uint64_t now_us);   // capacity minus the estimated queue, never below 0
  uint32_t queuedBytes(uint64_t now_us); // estimated queue, rounded up
  void add(size_t n, uint64_t now_us);   // a write of n bytes was queued now

 private:
  void drain(uint64_t now_us);
  uint32_t cap_, rate_, overhead_;
  uint64_t queued_ub_ = 0;  // queued bytes x 1e6
  uint64_t last_us_ = 0;
  bool have_time_ = false;
};

}  // namespace wfg
