#include "wfg_proto.h"
#include <string.h>
#include <stdio.h>

namespace wfg {

const char* state_name(uint8_t s) {
  switch (s) {
    case LS_IDLE: return "IDLE"; case LS_RECORDING: return "RECORDING"; case LS_FULL: return "FULL";
    default: return "ERROR";
  }
}

bool Proto::requestDelete(const char* name, const char* sha, uint32_t now, char* why, size_t n) {
  if (!Logger::validName(name)) { snprintf(why, n, "bad-name"); return false; }
  if (!sha || strlen(sha) != 64) { snprintf(why, n, "bad-sha"); return false; }
  if (lg_.recording()) { snprintf(why, n, "recording-active"); return false; }  // keeps LONG press unambiguous
  char cur[65];
  if (!lg_.isExportConfirmed(name, cur)) { snprintf(why, n, "not-export-confirmed"); return false; }
  if (strncmp(cur, sha, 64) != 0) { snprintf(why, n, "sha-mismatch"); return false; }
  strncpy(pend_name_, name, sizeof(pend_name_) - 1);
  strncpy(pend_sha_, sha, 64);
  pend_sha_[64] = 0;
  pend_deadline_ = now + delete_timeout_ms;
  pend_ = true;
  snprintf(last_del_, sizeof(last_del_), "PENDING %s", name);
  return true;
}

bool Proto::hasPendingDelete(uint32_t now) {
  if (pend_ && (int32_t)(now - pend_deadline_) > 0) {
    pend_ = false;
    snprintf(last_del_, sizeof(last_del_), "TIMEOUT %s", pend_name_);
    out_.printf("ERR DELETE %s timeout-no-button-confirmation\n", pend_name_);
  }
  return pend_;
}

void Proto::confirmPendingDelete(uint32_t now) {
  if (!hasPendingDelete(now)) return;
  pend_ = false;
  if (lg_.deleteConfirmedSession(pend_name_, pend_sha_)) {
    snprintf(last_del_, sizeof(last_del_), "DELETED %s", pend_name_);
    out_.printf("OK DELETE %s\n", pend_name_);
  } else {
    snprintf(last_del_, sizeof(last_del_), "FAILED %s", pend_name_);
    out_.printf("ERR DELETE %s delete-failed\n", pend_name_);
  }
}

static void hexline(const uint8_t* b, size_t n, char* out) {
  static const char* hx = "0123456789abcdef";
  for (size_t i = 0; i < n; i++) { out[2 * i] = hx[b[i] >> 4]; out[2 * i + 1] = hx[b[i] & 15]; }
  out[2 * n] = 0;
}

void Proto::listCb(const SessionInfo& s, void* ctx) {
  Proto* p = (Proto*)ctx;
  char sha[65] = "-";
  if (!(p->lg_.recording() && !strcmp(s.name, p->lg_.currentName()))) p->lg_.sha256File(s.name, sha);
  p->out_.printf("SESS %s %ld %u %s %d %s %d %s\n", s.name, s.size, (unsigned)s.n_records, mode_name(s.mode), s.closed,
                 s.closed ? end_reason_name(s.end_reason) : "-", s.exported, sha);
}

void Proto::handleLine(const char* line, uint32_t now, uint8_t mode) {
  char cmd[16] = "", a1[40] = "", a2[80] = "";
  int n = sscanf(line, "%15s %39s %79s", cmd, a1, a2);
  if (n < 1) return;
  if (!strcmp(cmd, "HELLO")) {
    out_.printf("OK HELLO fw=%s board=\"%s\" device=%08X fmt=%d recsize=%d state=%s\n", fw_, board_, (unsigned)dev_,
                WFG_FORMAT_VERSION, WFG_RECORD_SIZE, state_name(lg_.state()));
  } else if (!strcmp(cmd, "STATUS")) {
    out_.printf("OK STATUS state=%s mode=%s session=%s seq=%u free=%llu total=%llu\n", state_name(lg_.state()),
                mode_name(mode), lg_.recording() ? lg_.currentName() : "-", (unsigned)lg_.seq(),
                (unsigned long long)st_.freeBytes(), (unsigned long long)st_.totalBytes());
  } else if (!strcmp(cmd, "LIST")) {
    // Streams every session (no count limit, review R4).
    int k = lg_.forEachSession(listCb, this);
    out_.printf("OK LIST %d\n", k);
  } else if (!strcmp(cmd, "CHECK")) {
    if (!Logger::validName(a1)) { out_.printf("ERR CHECK bad-name\n"); return; }
    IntegrityReport r = Logger::checkSession(st_, a1);
    out_.printf("OK CHECK %s %s rec=%u crc_err=%u seq_err=%u trailing=%u fix=%u nofix=%u events=%u status=%u\n", a1,
                r.status, (unsigned)r.n_records, (unsigned)r.n_crc_errors, (unsigned)r.n_seq_errors,
                (unsigned)r.trailing_bytes, (unsigned)r.n_fix, (unsigned)r.n_nofix, (unsigned)r.n_events,
                (unsigned)r.n_status);
  } else if (!strcmp(cmd, "DUMP")) {
    if (!Logger::validName(a1)) { out_.printf("ERR DUMP bad-name\n"); return; }
    if (lg_.recording() && !strcmp(a1, lg_.currentName())) { out_.printf("ERR DUMP session-active\n"); return; }
    char sha[65];
    long size = 0;
    if (!lg_.sha256File(a1, sha, &size)) { out_.printf("ERR DUMP not-found\n"); return; }
    FILE* f = st_.open(a1, "rb");
    if (!f) { out_.printf("ERR DUMP open-failed\n"); return; }
    out_.printf("BEGIN %s %ld %s\n", a1, size, sha);
    uint8_t b[WFG_RECORD_SIZE];
    char hx[2 * WFG_RECORD_SIZE + 1];
    uint32_t idx = 0;
    size_t got;
    while ((got = fread(b, 1, WFG_RECORD_SIZE, f)) > 0) {
      hexline(b, got, hx);
      if (got == WFG_RECORD_SIZE) out_.printf("R %u %s\n", (unsigned)idx++, hx);
      else out_.printf("T %s\n", hx);
    }
    st_.close(f);
    out_.printf("OK DUMP %s %u\n", a1, (unsigned)idx);
  } else if (!strcmp(cmd, "CONFIRM")) {
    if (lg_.confirmExport(a1, a2, "usb")) out_.printf("OK CONFIRM %s\n", a1);
    else out_.printf("ERR CONFIRM %s sha-mismatch-or-not-closed\n", a1);
  } else if (!strcmp(cmd, "DELETE")) {
    char why[40];
    if (requestDelete(a1, a2, now, why, sizeof(why)))
      out_.printf("PENDING DELETE %s hold-button-ms=2500 timeout-ms=%u\n", a1, (unsigned)delete_timeout_ms);
    else
      out_.printf("ERR DELETE %s %s\n", a1, why);
  } else {
    out_.printf("ERR %s unknown-command\n", cmd);
  }
}

}  // namespace wfg
