// HOST SIMULATION ONLY: runs the real wfg_core USB protocol (Proto + Logger + PosixStorage + Live) over stdin/stdout
// against a directory of session files, so phone_export/usb_export.py and a desktop app can be tested end to end
// through a pseudo-terminal. Lines starting with '!' stand in for the hardware:
//   !BUTTON_LONG                    owner holds the device button (confirms a pending delete)
//   !NMEA <sentence>                one sentence from the GNSS UART, fed byte by byte (plus CR LF) to the real
//                                   NmeaParser; epochs go to Logger::onEpoch and to the LIVE "ep" line
//   !START [WALK|VEHICLE|UNKNOWN]   owner starts a recording (default: the current mode, WALK at start)
//   !STOP                           owner stops the recording
//   !MARK                           short press while recording: event marker
//   !QUIT                           exit
// !START while recording, and !STOP or !MARK while not recording, do nothing (a note goes to stderr).
// Every other line is a USB command, handled in the same order as src/main.cpp: DUMP, LIST and CHECK are refused
// while recording, LIVE commands go to wfg::Live, the rest to wfg::Proto. HELLO keeps this program's own board and
// firmware strings. VBAT, CALVBAT and FORMAT exist only in main.cpp, so here they get "ERR <CMD> unknown-command".
// The '#' lines for start, stop and marks are the ones main.cpp prints. Time is the host's monotonic clock in ms.
// As on the device, an epoch is committed after 250 ms without a sentence; while recording the gap filler writes
// NOFIX rows and a STATUS record follows every 60 s; a delete request expires after 30 s without !BUTTON_LONG.
// There is no battery: "vb" is always null.
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "wfg_live.h"
#include "wfg_logger.h"
#include "wfg_nmea.h"
#include "wfg_proto.h"

using namespace wfg;

struct StdoutSink : Sink {
  bool write(const char* s, size_t n) override { bool ok = fwrite(s, 1, n, stdout) == n; fflush(stdout); return ok; }
};

// stdout has no transmit buffer that could fill up here, so every LIVE line fits.
struct StdoutLiveSink : LiveSink {
  size_t availableForWrite() override { return 4096; }
  bool write(const char* s, size_t n) override { bool ok = fwrite(s, 1, n, stdout) == n; fflush(stdout); return ok; }
};

static uint32_t now_ms() {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

struct FakeDevice {
  PosixStorage st;
  LoggerConfig cfg;
  Logger lg;
  StdoutSink out;
  StdoutLiveSink live_out;
  Live live;
  Proto pr;
  NmeaParser nmea;
  NmeaLineCollector nmea_line;
  uint8_t mode = MODE_WALK;
  uint32_t last_idle_status_ms = 0;

  FakeDevice(const char* dir, const LoggerConfig& c)
      : st(dir), cfg(c), lg(st, cfg), live(live_out), pr(lg, st, out, "HOST-FAKE-DEVICE", cfg.device_id, "0.1.0-host") {}

  void banner(const char* msg) {  // as banner() in main.cpp
    printf("# %s\n", msg);
    fflush(stdout);
  }
  int32_t sessionNo() { return lg.recording() ? (int32_t)atoi(lg.currentName() + 1) : -1; }
  void onEpoch(uint32_t now) {
    GnssEpoch e = nmea.takeEpoch();
    live.epoch(e, lg.state(), sessionNo(), mode);
    lg.onEpoch(e, now);
    live.sessionCheck(lg.recording());
  }
  void feedNmea(const char* sentence, uint32_t now) {
    size_t n = strlen(sentence);
    for (size_t i = 0; i < n + 2; i++) {
      char c = i < n ? sentence[i] : (i == n ? '\r' : '\n');
      if (nmea.feed(c, now) && nmea.hasEpoch()) onEpoch(now);
      if (nmea_line.feed(c)) live.nmea(nmea_line.line());
    }
  }
  void start(const char* arg, uint32_t now) {
    if (lg.recording()) { fprintf(stderr, "fake_device: !START ignored, already recording\n"); return; }
    if (arg) {
      if (!strcmp(arg, "WALK")) mode = MODE_WALK;
      else if (!strcmp(arg, "VEHICLE")) mode = MODE_VEHICLE;
      else if (!strcmp(arg, "UNKNOWN")) mode = MODE_UNKNOWN;
      else { fprintf(stderr, "fake_device: !START needs WALK, VEHICLE or UNKNOWN\n"); return; }
    }
    if (lg.state() == LS_FULL) { banner("FULL: export+delete first"); return; }
    if (lg.start(mode, now, START_OWNER_BUTTON, 0, 0)) {
      live.sessionStarted((uint32_t)atoi(lg.currentName() + 1), mode, START_OWNER_BUTTON);
      char b[40];
      snprintf(b, sizeof(b), "REC %s %s", lg.currentName(), mode_name(mode));
      banner(b);
    } else {
      banner(lg.state() == LS_FULL ? "FULL: cannot start" : "START FAILED");
    }
  }
  void stop(uint32_t now) {
    if (!lg.recording()) { fprintf(stderr, "fake_device: !STOP ignored, not recording\n"); return; }
    lg.stop(END_USER_STOP, now);
    live.sessionCheck(lg.recording());
    banner("STOPPED - saved");
  }
  void mark(uint32_t now) {
    if (!lg.recording()) { fprintf(stderr, "fake_device: !MARK ignored, not recording\n"); return; }
    const uint16_t press_ms = 150;  // a short press, released now
    if (lg.markEvent(now - press_ms, press_ms, now)) {
      live.event((uint32_t)lg.lastEventNo(), lg.lastEventLocated());
      char b[40];
      snprintf(b, sizeof(b), "EVENT %d %s", (int)lg.lastEventNo(), lg.lastEventLocated() ? "marked" : "(NO POSITION)");
      banner(b);
    }
    live.sessionCheck(lg.recording());
  }
  // Returns false on !QUIT.
  bool handleLine(const char* line, uint32_t now) {
    if (!strcmp(line, "!QUIT")) return false;
    if (!strcmp(line, "!BUTTON_LONG")) { pr.confirmPendingDelete(now); return true; }
    if (!strncmp(line, "!NMEA ", 6)) { feedNmea(line + 6, now); return true; }
    if (!strcmp(line, "!START")) { start(nullptr, now); return true; }
    if (!strncmp(line, "!START ", 7)) { start(line + 7, now); return true; }
    if (!strcmp(line, "!STOP")) { stop(now); return true; }
    if (!strcmp(line, "!MARK")) { mark(now); return true; }
    bool heavy = !strncmp(line, "DUMP", 4) || !strncmp(line, "LIST", 4) || !strncmp(line, "CHECK", 5);
    if (heavy && lg.recording()) {  // as main.cpp
      printf("ERR %.5s recording-active (stop recording first)\n", line);
      fflush(stdout);
      return true;
    }
    if (!live.handleCommand(line, out)) pr.handleLine(line, now, mode);
    return true;
  }
  // What the firmware loop does between input lines.
  void tick(uint32_t now) {
    if (nmea.poll(now) && nmea.hasEpoch()) onEpoch(now);
    lg.tick(now, &nmea);
    live.sessionCheck(lg.recording());
    pr.hasPendingDelete(now);
    if (!lg.recording() && (uint32_t)(now - last_idle_status_ms) >= 10000) {
      last_idle_status_ms = now;
      live.status(-1, (int64_t)st.freeBytes());
    }
  }
};

int main(int argc, char** argv) {
  if (argc < 2) { fprintf(stderr, "usage: fake_device DIR\n"); return 2; }
  LoggerConfig c;
  c.device_id = 0x1A2B3C4D;
  FakeDevice d(argv[1], c);
  d.lg.begin();
  d.lg.setRecordObserver(live_record_observer, &d.live);
  d.last_idle_status_ms = now_ms();
  printf("# fake device ready\n");
  fflush(stdout);
  char line[512];
  size_t len = 0;
  bool run = true;
  while (run) {
    struct pollfd p;
    p.fd = 0;
    p.events = POLLIN;
    p.revents = 0;
    int r = poll(&p, 1, 20);
    if (r < 0 && errno != EINTR) break;
    if (r > 0) {
      char buf[256];
      ssize_t n = read(0, buf, sizeof(buf));
      if (n == 0) break;  // end of input
      if (n < 0) {
        if (errno == EINTR || errno == EAGAIN) continue;
        break;
      }
      for (ssize_t i = 0; i < n && run; i++) {
        char ch = buf[i];
        if (ch == '\r' || ch == '\n') {
          line[len] = 0;
          len = 0;
          if (line[0]) run = d.handleLine(line, now_ms());
        } else if (len < sizeof(line) - 1) {
          line[len++] = ch;
        }
      }
    }
    if (run) d.tick(now_ms());
  }
  return 0;
}
