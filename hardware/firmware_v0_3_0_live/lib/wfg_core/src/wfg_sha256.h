// Small portable SHA-256 (FIPS 180-4). Used on device to fingerprint exported files so the phone page
// and usb_export.py can confirm a byte-identical copy before deletion is allowed.
#pragma once
#include <stdint.h>
#include <stddef.h>

namespace wfg {

struct Sha256 {
  uint32_t h[8];
  uint8_t buf[64];
  uint64_t total;
  size_t blen;
  Sha256() { reset(); }
  void reset();
  void update(const uint8_t* data, size_t len);
  void update(const char* s, size_t len) { update((const uint8_t*)s, len); }
  void finish(uint8_t out[32]);
  void finishHex(char out[65]);  // lowercase hex, NUL-terminated
 private:
  void block(const uint8_t* p);
};

}  // namespace wfg
