// HOST SIMULATION ONLY: runs the real wfg_core USB protocol (Proto + Logger + PosixStorage) over stdin/stdout
// against a directory of session files, so phone_export/usb_export.py can be tested end-to-end through a
// pseudo-terminal. A line "!BUTTON_LONG" simulates the owner holding the device button (delete confirmation).
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "wfg_logger.h"
#include "wfg_proto.h"

using namespace wfg;

struct StdoutSink : Sink {
  bool write(const char* s, size_t n) override { bool ok = fwrite(s, 1, n, stdout) == n; fflush(stdout); return ok; }
};

static uint32_t now_ms() {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

int main(int argc, char** argv) {
  if (argc < 2) { fprintf(stderr, "usage: fake_device DIR\n"); return 2; }
  PosixStorage st(argv[1]);
  LoggerConfig c;
  c.device_id = 0x1A2B3C4D;
  Logger lg(st, c);
  lg.begin();
  StdoutSink out;
  Proto pr(lg, st, out, "HOST-FAKE-DEVICE", c.device_id, "0.1.0-host");
  printf("# fake device ready\n");
  fflush(stdout);
  char line[256];
  while (fgets(line, sizeof(line), stdin)) {
    size_t n = strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
    if (!n) continue;
    if (!strcmp(line, "!BUTTON_LONG")) { pr.confirmPendingDelete(now_ms()); continue; }
    if (!strcmp(line, "!QUIT")) break;
    pr.handleLine(line, now_ms(), MODE_WALK);
  }
  return 0;
}
