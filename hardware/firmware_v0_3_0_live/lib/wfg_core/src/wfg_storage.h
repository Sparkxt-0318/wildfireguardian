// Storage abstraction. PosixStorage works on any POSIX/newlib VFS:
//   - on the ESP32 it is rooted at the LittleFS VFS mount point "/littlefs";
//   - on the host it is rooted at a temp directory and can simulate a capacity limit (ENOSPC)
//     so storage-full behaviour is testable without hardware.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

namespace wfg {

class Storage {
 public:
  virtual ~Storage() {}
  virtual FILE* open(const char* name, const char* mode) = 0;  // name relative to root
  // write() returns bytes written; may be short when the filesystem is full.
  virtual size_t write(FILE* f, const uint8_t* data, size_t len) = 0;
  virtual bool sync(FILE* f) = 0;  // fflush + fsync
  virtual void close(FILE* f) = 0;
  virtual long size(const char* name) = 0;  // -1 if missing
  virtual bool exists(const char* name) { return size(name) >= 0; }
  virtual bool remove(const char* name) = 0;
  virtual bool rename(const char* from, const char* to) = 0;
  virtual bool truncate(const char* name, long len) = 0;
  // Calls cb for every regular file in the root. Returns false on error.
  virtual bool list(void (*cb)(const char* name, long size, void* ctx), void* ctx) = 0;
  virtual uint64_t totalBytes() = 0;
  virtual uint64_t usedBytes() = 0;
  uint64_t freeBytes() { uint64_t t = totalBytes(), u = usedBytes(); return u >= t ? 0 : t - u; }
};

// Usage-reporting callbacks let the ESP32 build plug in LittleFS.totalBytes()/usedBytes().
typedef uint64_t (*UsageFn)();

class PosixStorage : public Storage {
 public:
  // root: directory prefix without trailing slash.
  // sim_capacity: 0 = use total_fn/used_fn; >0 = host simulation with that many bytes, 4096-byte blocks.
  PosixStorage(const char* root, uint64_t sim_capacity = 0, UsageFn total_fn = nullptr, UsageFn used_fn = nullptr);
  FILE* open(const char* name, const char* mode) override;
  size_t write(FILE* f, const uint8_t* data, size_t len) override;
  bool sync(FILE* f) override;
  void close(FILE* f) override;
  long size(const char* name) override;
  bool remove(const char* name) override;
  bool rename(const char* from, const char* to) override;
  bool truncate(const char* name, long len) override;
  bool list(void (*cb)(const char* name, long size, void* ctx), void* ctx) override;
  uint64_t totalBytes() override;
  uint64_t usedBytes() override;

  // Host-test fault injection: after this many more bytes, write() becomes short (simulated power cut
  // mid-record when combined with abandoning the logger without close). -1 = disabled.
  long fail_after_bytes = -1;
  bool truncate_fallback_used = false;

 private:
  char root_[160];
  uint64_t sim_cap_;
  UsageFn total_fn_, used_fn_;
  void path(const char* name, char* out, size_t n);
};

}  // namespace wfg
