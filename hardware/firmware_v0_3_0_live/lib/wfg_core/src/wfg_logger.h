// Session logger: append-only session files, recovery, integrity check, storage-full handling,
// export confirmation and guarded deletion. Hardware independent (uses wfg::Storage).
#pragma once
#include <stdint.h>
#include <vector>
#include "wfg_record.h"
#include "wfg_nmea.h"
#include "wfg_storage.h"

namespace wfg {

struct LoggerConfig {
  uint16_t log_interval_ms = 1000;        // one observation row per GNSS epoch, at most this often
  uint32_t nodata_after_ms = 1500;        // write NOFIX/NO_DATA row if no epoch for this long
  uint32_t sync_every_ms = 5000;          // fsync period: power loss loses at most ~5 rows
  uint32_t event_locate_max_age_ms = 2000;// event gets the preceding fix position only if that fix is this fresh
  uint32_t clock_jump_threshold_ms = 2000;// |offset change| above this writes a CLOCK_JUMP record
  uint32_t free_check_every_records = 32; // how often to query free space (LittleFS usedBytes is a traversal)
  uint32_t status_every_ms = 60000;       // STATUS record period while recording (first one right after START)
  uint64_t reserve_bytes = 32768;         // stop when free < this: room for END record, .ok markers, meta
  uint32_t device_id = 0;
  uint8_t board_rev = 0;
  uint16_t fw_version = 1;
};

enum LoggerState : uint8_t { LS_IDLE = 0, LS_RECORDING = 1, LS_FULL = 2, LS_ERROR = 3 };

struct SessionInfo {
  char name[20];          // "S000012.wfg"
  char session_id[32];    // "WFG-1A2B3C4D-000012"
  uint32_t session_no;
  long size;
  uint32_t n_records;
  uint8_t mode;
  uint8_t closed;         // SESSION_END present
  uint8_t end_reason;
  uint8_t exported;       // .ok marker present and matches current SHA-256
  uint8_t start_reason;   // StartReason
  uint32_t resumed_from_session_no;
};

// Battery/screen sample supplied by the hardware layer for STATUS records. Return false if unavailable.
typedef bool (*StatusFn)(Status& st, void* ctx);

// Record observer (fw 0.3.0, used for the LIVE "rec" lines): rec = the 48 bytes as written, seq = the record's seq,
// file_size = size of the session file after the write.
typedef void (*RecordObserverFn)(const uint8_t rec[WFG_RECORD_SIZE], uint32_t seq, uint32_t file_size, void* ctx);

struct IntegrityReport {
  bool readable = false;
  uint32_t n_records = 0;
  uint32_t n_crc_errors = 0;
  uint32_t n_seq_errors = 0;
  uint32_t trailing_bytes = 0;     // size % 48
  bool has_start = false;
  bool has_end = false;
  uint8_t end_reason = 0;
  bool end_counts_match = false;
  bool end_crc_match = false;
  uint32_t n_fix = 0, n_nofix = 0, n_events = 0, n_clock = 0, n_status = 0;
  int32_t first_bad_index = -1;
  char status[16] = "";            // OK, RECOVERED, OPEN, TORN_TAIL, CORRUPT, EMPTY, MISSING
  bool ok() const;
};

struct RecoveryItem {
  char name[20];
  uint32_t valid_records;
  uint32_t torn_bytes_removed;
  bool closed_now;
  bool unrecoverable;              // first record invalid: renamed to .bad, never deleted
};

class Logger {
 public:
  Logger(Storage& st, const LoggerConfig& cfg) : st_(st), cfg_(cfg) {}

  // Mount-time work: load/advance boot counter, recover unclosed sessions. Returns number recovered.
  int begin(RecoveryItem* items = nullptr, int max_items = 0);

  bool start(uint8_t mode, uint32_t mono_ms, uint8_t start_reason = START_OWNER_BUTTON,
             uint32_t resumed_from_session_no = 0, uint8_t reset_reason = 0);
  void setStatusSource(StatusFn fn, void* ctx) { status_fn_ = fn; status_ctx_ = ctx; }
  // Called after every record successfully written to the current session file, any type, including the
  // SESSION_END written when storage runs out. Not called for the END records boot recovery (begin()) adds to
  // older files. Optional; nullptr turns it off. It must not call back into the logger.
  void setRecordObserver(RecordObserverFn fn, void* ctx) { rec_obs_ = fn; rec_obs_ctx_ = ctx; }
  void onEpoch(const GnssEpoch& e, uint32_t mono_ms);
  // Call every loop iteration. Pass the parser so the gap filler can tell "receiver talking but no
  // timed solution" from "UART silent" and does not interleave with an epoch that is still arriving.
  void tick(uint32_t mono_ms, const NmeaParser* nmea = nullptr);
  // Event marker. press_mono_ms = when the button went down. Returns false if not recording.
  bool markEvent(uint32_t press_mono_ms, uint16_t press_duration_ms, uint32_t now_mono_ms);
  bool stop(uint8_t reason, uint32_t mono_ms);

  LoggerState state() const { return state_; }
  bool recording() const { return state_ == LS_RECORDING; }
  void clearFull() { if (state_ == LS_FULL) state_ = LS_IDLE; }
  const char* currentName() const { return cur_name_; }
  const char* currentSessionId() const { return cur_sid_; }
  uint32_t seq() const { return seq_; }
  uint32_t nFix() const { return n_fix_; }
  uint32_t nNofix() const { return n_nofix_; }
  uint32_t nEvents() const { return n_events_; }
  uint32_t bootCount() const { return boot_count_; }
  uint32_t nextSessionNo() const { return next_session_no_; }
  bool lastObsWasFix() const { return last_obs_fix_; }
  int32_t lastEventNo() const { return last_event_no_; }
  bool lastEventLocated() const { return last_event_located_; }
  uint32_t lastEventMono() const { return last_event_mono_; }
  bool utcKnown() const { return have_offset_; }
  int64_t utcOffsetMs() const { return offset_ms_; }

  // ---- export / housekeeping (static-ish helpers usable while idle) ----
  // Every session file, ascending session number, no count limit (review R4). Returns the number visited.
  // Names are collected first (4 bytes each), then each file is opened, so the callback may not delete files.
  int forEachSession(void (*cb)(const SessionInfo& s, void* ctx), void* ctx);
  int countUnexported();
  std::vector<uint32_t> sessionNumbers();  // sorted, every valid S??????.wfg
  bool sessionInfo(const char* name, SessionInfo& out);
  bool sha256File(const char* name, char hex_out[65], long* size_out = nullptr);
  // Writes <name>.ok holding the hash if it matches the file. via = "wifi" / "usb".
  bool confirmExport(const char* name, const char* sha_hex, const char* via);
  // quick (default): .ok marker exists and its recorded size equals the file size (used for listing).
  // full_verify: also re-hash the file (used before deleting).
  bool isExportConfirmed(const char* name, char* sha_out = nullptr, bool full_verify = false);
  // Delete only when export was confirmed AND the given hash equals the current file hash.
  // The firmware additionally requires a physical button hold before calling this.
  bool deleteConfirmedSession(const char* name, const char* sha_hex);

  static IntegrityReport checkSession(Storage& st, const char* name);
  static bool validName(const char* name);
  static void makeSessionId(uint32_t device_id, uint32_t session_no, char* out, size_t n);

  uint32_t free_check_counter = 0;
  uint32_t nStatus() const { return n_status_; }

 private:
  Storage& st_;
  LoggerConfig cfg_;
  LoggerState state_ = LS_IDLE;
  FILE* f_ = nullptr;
  char cur_name_[20] = "";
  char cur_sid_[32] = "";
  uint32_t seq_ = 0;
  uint32_t crc_all_ = 0;
  uint32_t n_fix_ = 0, n_nofix_ = 0, n_events_ = 0, n_clock_ = 0;
  uint32_t last_row_mono_ = 0;        // mono of last observation row of any kind (FIX/NOFIX/filler)
  uint32_t last_epoch_row_mono_ = 0;  // first_mono of the last epoch that produced a row (rate limiter)
  bool have_epoch_row_ = false;
  bool have_obs_ = false;
  uint32_t last_sync_mono_ = 0;
  uint32_t boot_count_ = 0;
  uint32_t next_session_no_ = 1;
  bool last_obs_fix_ = false;
  // last fix (for event location)
  bool have_fix_ = false;
  uint32_t last_fix_seq_ = 0;
  uint32_t last_fix_mono_ = 0;
  int32_t last_fix_lat_ = 0, last_fix_lon_ = 0;
  int32_t last_event_no_ = 0;
  bool last_event_located_ = false;
  uint32_t last_event_mono_ = 0;
  // clock
  bool have_offset_ = false;
  int64_t offset_ms_ = 0;
  bool start_written_utc_ = false;
  uint32_t last_epoch_mono_ = 0;
  bool have_epoch_ = false;

  StatusFn status_fn_ = nullptr;
  void* status_ctx_ = nullptr;
  RecordObserverFn rec_obs_ = nullptr;
  void* rec_obs_ctx_ = nullptr;
  uint32_t last_status_mono_ = 0;
  uint32_t n_status_ = 0;
  const NmeaParser* nmea_ = nullptr;
  void writeStatus(uint32_t mono_ms);
  bool append(Record& r, uint32_t mono_ms);
  bool spaceOk();
  void loadMeta();
  bool saveMeta();
  void writeFiller(uint32_t mono_ms, uint8_t reason);
  void handleClock(const GnssEpoch& e, uint32_t mono_ms);
  int recoverAll(RecoveryItem* items, int max_items);
};

int64_t utc_epoch_ms(uint32_t yyyymmdd, uint32_t ms_of_day);  // ms since 1970-01-01T00:00Z
void epoch_ms_to_utc(int64_t ms, uint32_t& yyyymmdd, uint32_t& ms_of_day);

}  // namespace wfg
