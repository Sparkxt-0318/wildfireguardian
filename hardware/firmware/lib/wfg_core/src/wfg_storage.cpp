#include "wfg_storage.h"
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#if !defined(ARDUINO)
#include <sys/statvfs.h>
#endif

namespace wfg {

static const uint64_t kBlock = 4096;

PosixStorage::PosixStorage(const char* root, uint64_t sim_capacity, UsageFn total_fn, UsageFn used_fn)
    : sim_cap_(sim_capacity), total_fn_(total_fn), used_fn_(used_fn) {
  strncpy(root_, root, sizeof(root_) - 1);
  root_[sizeof(root_) - 1] = 0;
}

void PosixStorage::path(const char* name, char* out, size_t n) { snprintf(out, n, "%s/%s", root_, name); }

FILE* PosixStorage::open(const char* name, const char* mode) {
  char p[224];
  path(name, p, sizeof(p));
  return fopen(p, mode);
}

size_t PosixStorage::write(FILE* f, const uint8_t* data, size_t len) {
  if (!f) return 0;
  size_t allow = len;
  if (fail_after_bytes >= 0) {
    if ((long)allow > fail_after_bytes) allow = (size_t)fail_after_bytes;
    fail_after_bytes -= (long)allow;
  }
  if (sim_cap_) {
    // Simulated ENOSPC: refuse bytes that would push block usage over capacity.
    fflush(f);
    long pos = ftell(f);
    uint64_t used = usedBytes();
    uint64_t cur_blocks = (pos + kBlock - 1) / kBlock;
    uint64_t new_blocks = (pos + allow + kBlock - 1) / kBlock;
    uint64_t extra = (new_blocks - cur_blocks) * kBlock;
    if (used + extra > sim_cap_) {
      uint64_t room_in_block = cur_blocks * kBlock - (uint64_t)pos;
      uint64_t free_blocks = (sim_cap_ - (used > sim_cap_ ? sim_cap_ : used)) / kBlock;
      uint64_t maxb = room_in_block + free_blocks * kBlock;
      if (allow > maxb) allow = (size_t)maxb;
    }
  }
  if (allow == 0) return 0;
  return fwrite(data, 1, allow, f);
}

bool PosixStorage::sync(FILE* f) {
  if (!f) return false;
  if (fflush(f) != 0) return false;
  return fsync(fileno(f)) == 0;
}

void PosixStorage::close(FILE* f) {
  if (f) fclose(f);
}

long PosixStorage::size(const char* name) {
  char p[224];
  path(name, p, sizeof(p));
  struct stat st;
  if (stat(p, &st) != 0) return -1;
  return (long)st.st_size;
}

bool PosixStorage::remove(const char* name) {
  char p[224];
  path(name, p, sizeof(p));
  return ::remove(p) == 0;
}

bool PosixStorage::rename(const char* from, const char* to) {
  char a[224], b[224];
  path(from, a, sizeof(a));
  path(to, b, sizeof(b));
  return ::rename(a, b) == 0;
}

bool PosixStorage::truncate(const char* name, long len) {
  char p[224];
  path(name, p, sizeof(p));
  if (::truncate(p, len) == 0) return true;
  // Fallback for VFS drivers without truncate(): copy the prefix and rename.
  truncate_fallback_used = true;
  char tmpn[64];
  snprintf(tmpn, sizeof(tmpn), "%s.tmp", name);
  FILE* in = open(name, "rb");
  FILE* out = open(tmpn, "wb");
  if (!in || !out) { if (in) fclose(in); if (out) fclose(out); return false; }
  uint8_t buf[256];
  long left = len;
  bool ok = true;
  while (left > 0) {
    size_t n = fread(buf, 1, left > (long)sizeof(buf) ? sizeof(buf) : (size_t)left, in);
    if (n == 0) { ok = false; break; }
    if (fwrite(buf, 1, n, out) != n) { ok = false; break; }
    left -= (long)n;
  }
  fclose(in);
  ok = ok && sync(out);
  fclose(out);
  if (!ok) { remove(tmpn); return false; }
  if (!remove(name)) return false;
  return rename(tmpn, name);
}

bool PosixStorage::list(void (*cb)(const char*, long, void*), void* ctx) {
  DIR* d = opendir(root_);
  if (!d) return false;
  struct dirent* e;
  while ((e = readdir(d)) != nullptr) {
    if (e->d_name[0] == '.') continue;
    long s = size(e->d_name);
    if (s < 0) continue;
    cb(e->d_name, s, ctx);
  }
  closedir(d);
  return true;
}

struct UsageAcc { uint64_t bytes; };
static void acc_cb(const char*, long s, void* ctx) {
  UsageAcc* a = (UsageAcc*)ctx;
  a->bytes += ((uint64_t)s + kBlock - 1) / kBlock * kBlock + kBlock;  // + 1 metadata block per file (approx.)
}

uint64_t PosixStorage::totalBytes() {
  if (sim_cap_) return sim_cap_;
  if (total_fn_) return total_fn_();
#if !defined(ARDUINO)
  struct statvfs v;
  if (statvfs(root_, &v) == 0) return (uint64_t)v.f_blocks * v.f_frsize;
#endif
  return 0;
}

uint64_t PosixStorage::usedBytes() {
  if (sim_cap_) {
    UsageAcc a{2 * kBlock};  // superblock pair
    list(acc_cb, &a);
    return a.bytes;
  }
  if (used_fn_) return used_fn_();
#if !defined(ARDUINO)
  struct statvfs v;
  if (statvfs(root_, &v) == 0) return (uint64_t)(v.f_blocks - v.f_bavail) * v.f_frsize;
#endif
  return 0;
}

}  // namespace wfg
