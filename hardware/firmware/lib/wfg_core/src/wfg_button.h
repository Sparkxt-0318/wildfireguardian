// Single-button gesture decoder. Hardware independent: feed it the debounced-or-raw pressed level and
// a millisecond clock. Gestures:
//   SHORT      release before long_ms                    (emitted immediately, or after the double window
//                                                         when double detection is enabled)
//   DOUBLE     two SHORT presses within double_gap_ms    (only when double detection enabled)
//   LONG       release between long_ms and very_long_ms  (start/stop recording; delete confirm in export)
//   VERY_LONG  release after very_long_ms                (enter/exit export mode)
// While held, holdMs() lets the UI draw a countdown to the next threshold.
// If the button is already down when begin() is called (e.g. held through reset), it is ignored until
// released, so a stuck plunger can never trigger an action.
#pragma once
#include <stdint.h>

namespace wfg {

enum Gesture : uint8_t { G_NONE = 0, G_SHORT, G_DOUBLE, G_LONG, G_VERY_LONG };

struct ButtonConfig {
  uint16_t debounce_ms = 30;
  uint16_t long_ms = 2500;
  uint16_t very_long_ms = 6000;
  uint16_t double_gap_ms = 400;
};

class Button {
 public:
  explicit Button(const ButtonConfig& c = ButtonConfig()) : cfg_(c) {}
  void begin(bool pressed_now, uint32_t now) {
    stable_ = raw_ = pressed_now; raw_since_ = now; lockout_ = pressed_now; pending_short_ = false;
  }
  void setDoubleEnabled(bool en) { double_en_ = en; }
  // Returns a gesture when one completes.
  Gesture update(bool pressed, uint32_t now);
  bool isDown() const { return stable_ && !lockout_; }
  uint32_t holdMs(uint32_t now) const { return isDown() ? now - down_at_ : 0; }
  uint32_t lastDownAt() const { return down_at_; }
  uint32_t lastPressDuration() const { return last_dur_; }
  const ButtonConfig& cfg() const { return cfg_; }

 private:
  ButtonConfig cfg_;
  bool raw_ = false, stable_ = false, lockout_ = false;
  uint32_t raw_since_ = 0, down_at_ = 0, last_dur_ = 0;
  bool double_en_ = false;
  bool pending_short_ = false;
  uint32_t pending_since_ = 0, pending_down_at_ = 0, pending_dur_ = 0;
};

inline Gesture Button::update(bool pressed, uint32_t now) {
  if (pressed != raw_) { raw_ = pressed; raw_since_ = now; }
  Gesture g = G_NONE;
  if (raw_ != stable_ && (uint32_t)(now - raw_since_) >= cfg_.debounce_ms) {
    stable_ = raw_;
    if (stable_) {  // press
      if (!lockout_) down_at_ = raw_since_;
    } else {        // release
      if (lockout_) { lockout_ = false; return G_NONE; }
      uint32_t dur = raw_since_ - down_at_;
      last_dur_ = dur;
      if (dur >= cfg_.very_long_ms) { pending_short_ = false; return G_VERY_LONG; }
      if (dur >= cfg_.long_ms) { pending_short_ = false; return G_LONG; }
      if (!double_en_) return G_SHORT;
      if (pending_short_ && (uint32_t)(down_at_ - pending_since_) <= cfg_.double_gap_ms) {
        pending_short_ = false;
        return G_DOUBLE;
      }
      pending_short_ = true;
      pending_since_ = raw_since_;
      pending_down_at_ = down_at_;
      pending_dur_ = dur;
      return G_NONE;
    }
  }
  if (pending_short_ && !stable_ && (uint32_t)(now - pending_since_) > cfg_.double_gap_ms) {
    pending_short_ = false;
    down_at_ = pending_down_at_;  // report the original press time for the delayed SHORT
    last_dur_ = pending_dur_;
    g = G_SHORT;
  }
  return g;
}

}  // namespace wfg
