// Auto-resume after an unexpected reset (review R3). Hardware independent; host-tested.
//
// The firmware keeps a small "recording intent" record in NVS:
//   active=1, mode, session_no  written when a session STARTS (button or auto-resume)
//   active=0                    written on EVERY clean end (owner stop, STORAGE_FULL, LOW_BATTERY, FS error)
// If the board resets while active=1 (brownout, battery connector bounce, watchdog, panic, RST pin), boot recovery
// first closes the cut session as RECOVERED_ON_BOOT (unchanged behaviour), then decide_resume() says whether to
// start a NEW session with the same movement mode. The new session's SESSION_START carries
// start_reason=AUTO_RESUMED_AFTER_RESET, resumed_from_session_no and the reset reason. Sessions are never merged.
//
// Reboot-loop guard: quick_fail_count counts auto-resumes that did not reach resume_stable_ms of recording.
// After max_quick_fails consecutive quick failures the firmware stops auto-resuming and shows a message.
#pragma once
#include <stdint.h>

namespace wfg {

struct ResumeNvs {
  bool active = false;
  uint8_t mode = 0;
  uint32_t session_no = 0;
  uint8_t quick_fail_count = 0;
};

enum ResumeAction : uint8_t {
  RA_NONE = 0,            // nothing was recording: normal idle boot
  RA_RESUME = 1,          // start a new session with nv.mode, attributed as auto-resumed
  RA_GIVE_UP_LOOP = 2,    // too many quick consecutive resets: clear intent, stay idle, tell the owner
  RA_BLOCKED_FS = 3,      // filesystem not mounted: cannot record; keep intent so a later fixed boot can resume
  RA_BLOCKED_FULL = 4,    // storage full: clear intent, stay idle (FULL shown)
  RA_BLOCKED_LOW_BATT = 5,// battery reading below the low-battery stop level: clear intent, stay idle
};

struct ResumeInputs {
  bool fs_ok = true;
  bool storage_full = false;
  int batt_mv = -1;              // -1 = unknown (USB power or no sense): does not block
  int low_batt_mv = 3400;
  uint8_t max_quick_fails = 3;
};

inline ResumeAction decide_resume(const ResumeNvs& nv, const ResumeInputs& in) {
  if (!nv.active) return RA_NONE;
  if (!in.fs_ok) return RA_BLOCKED_FS;
  if (nv.quick_fail_count >= in.max_quick_fails) return RA_GIVE_UP_LOOP;
  if (in.storage_full) return RA_BLOCKED_FULL;
  if (in.batt_mv > 0 && in.batt_mv < in.low_batt_mv) return RA_BLOCKED_LOW_BATT;
  return RA_RESUME;
}

inline const char* resume_action_name(ResumeAction a) {
  switch (a) {
    case RA_NONE: return "NONE"; case RA_RESUME: return "RESUME"; case RA_GIVE_UP_LOOP: return "GIVE_UP_LOOP";
    case RA_BLOCKED_FS: return "BLOCKED_FS"; case RA_BLOCKED_FULL: return "BLOCKED_FULL";
    case RA_BLOCKED_LOW_BATT: return "BLOCKED_LOW_BATT";
  }
  return "?";
}

}  // namespace wfg
