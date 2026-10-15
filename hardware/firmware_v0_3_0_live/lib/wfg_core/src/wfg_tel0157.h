// Bounded nonblocking adapter for DFRobot TEL0157 UART register protocol.
// Based on DFRobot_GNSS getGnssLen/getAllGnss/readReg/writeReg (MIT),
// https://github.com/DFRobot/DFRobot_GNSS . Physical transport NOT RUN.
#pragma once
#include <stdint.h>
namespace wfg {
class Tel0157 {
 public:
  // Caller sends these bytes on GNSS UART. Reader passes received bytes to feed().
  typedef void (*Send)(const uint8_t*, unsigned, void*);
  typedef void (*Data)(char, uint32_t, void*);
  Tel0157(Send send, Data data, void* ctx): send_(send), data_(data), ctx_(ctx) {}
  uint32_t errors = 0, captures = 0;
  bool busy() const { return state_ != IDLE; }
  void tick(uint32_t now) {
    if (state_ == IDLE && (uint32_t)(now-capture_start_) >= 1000 && (uint32_t)(now-last_) >= 300) {
      uint8_t cmd[] = {uint8_t(29|0x80),0x55}; send_(cmd,2,ctx_);
      state_=WAIT_CAPTURE; last_=now; capture_start_=now;
    } else if (state_ == WAIT_CAPTURE && (uint32_t)(now-last_) >= 100) {
      uint8_t cmd[]={31,2}; send_(cmd,2,ctx_); state_=LENGTH; last_=now; got_=0;
    } else if ((state_ == LENGTH || state_ == DATA) && (uint32_t)(now-last_) >= 500) {
      errors++; state_=IDLE; last_=now; // fail closed: next capture replaces timed-out snapshot
    }
  }
  void feed(uint8_t b,uint32_t now) {
    if (state_ == LENGTH) {
      if (got_++ == 0) high_=b;
      else {
        remaining_=uint16_t(high_)*256+b;
        if (!remaining_ || remaining_>1224) { if (remaining_) errors++; state_=IDLE; last_=now; }
        else request(now);
      }
    } else if (state_ == DATA) {
      data_(b ? char(b) : '\n',now,ctx_);
      if (++got_ == wanted_) {
        remaining_-=wanted_;
        if (remaining_) request(now);
        else { captures++; state_=IDLE; last_=now; }
      }
    } // unsolicited/extra bytes discarded without array writes
  }
 private:
  enum {IDLE,WAIT_CAPTURE,LENGTH,DATA} state_=IDLE;
  Send send_; Data data_; void* ctx_; uint32_t last_=0, capture_start_=0;
  uint16_t remaining_=0; unsigned got_=0, wanted_=0; uint8_t high_=0;
  void request(uint32_t now) {
    wanted_=remaining_>250 ? 250 : remaining_;
    uint8_t cmd[]={33,uint8_t(wanted_)}; send_(cmd,2,ctx_);
    got_=0; last_=now; state_=DATA;
  }
};
}
