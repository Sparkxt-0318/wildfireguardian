// USB serial line protocol (mandatory export fallback). Hardware independent: the firmware feeds it lines
// from USB CDC; the host test "fake device" feeds it stdin. Every device->host protocol line starts with an
// uppercase keyword; free-form log lines from the firmware start with '#', so hosts ignore them.
//
// host -> device                     device -> host
// HELLO                              OK HELLO fw=<v> board=<name> device=<hex> fmt=1 recsize=48 state=<s>
// STATUS                             OK STATUS state=<s> mode=<m> session=<name|-> seq=<n> free=<bytes> total=<bytes>
// LIST (all sessions, no limit)      SESS <name> <size> <records> <mode> <closed 0/1> <end_reason> <exported 0/1> <sha256>
//                                    ... OK LIST <count>
// CHECK <name>                       OK CHECK <name> <status> rec=<n> crc_err=<n> seq_err=<n> trailing=<n> fix=<n> nofix=<n> events=<n>
// DUMP <name>                        BEGIN <name> <size> <sha256>
//                                    R <index> <96 hex chars>          (one per whole 48-byte record)
//                                    T <hex>                           (trailing partial bytes, if any)
//                                    OK DUMP <name> <records>
// CONFIRM <name> <sha256>            OK CONFIRM <name> | ERR CONFIRM <reason>
// DELETE <name> <sha256>             PENDING DELETE <name> hold-button-ms=<n> timeout-ms=<n>
//                                    later: OK DELETE <name> | ERR DELETE <reason>
// any error                          ERR <CMD> <reason>
#pragma once
#include <stdint.h>
#include "wfg_logger.h"
#include "wfg_export.h"

namespace wfg {

class Proto {
 public:
  Proto(Logger& lg, Storage& st, Sink& out, const char* board_name, uint32_t device_id, const char* fw)
      : lg_(lg), st_(st), out_(out), board_(board_name), dev_(device_id), fw_(fw) {}
  void handleLine(const char* line, uint32_t now_ms, uint8_t mode);
  // Physical confirmation from the button (long press) for a pending delete (USB or Wi-Fi originated).
  bool hasPendingDelete(uint32_t now_ms);
  const char* pendingDeleteName() const { return pend_name_; }
  void confirmPendingDelete(uint32_t now_ms);
  // Wi-Fi page uses the same pending-delete path.
  bool requestDelete(const char* name, const char* sha, uint32_t now_ms, char* why, size_t why_n);
  const char* lastDeleteResult() const { return last_del_; }
  uint32_t delete_timeout_ms = 30000;

 private:
  static void listCb(const SessionInfo& s, void* ctx);
  Logger& lg_;
  Storage& st_;
  Sink& out_;
  const char* board_;
  uint32_t dev_;
  const char* fw_;
  char pend_name_[20] = "";
  char pend_sha_[65] = "";
  uint32_t pend_deadline_ = 0;
  bool pend_ = false;
  char last_del_[48] = "";
};

const char* state_name(uint8_t s);

}  // namespace wfg
