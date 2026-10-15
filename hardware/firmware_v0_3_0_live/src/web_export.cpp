// Wi-Fi export: SoftAP (WPA2) + plain HTTP on 192.168.4.1. Deliberately NO captive-portal DNS: the iOS
// captive-portal mini browser cannot save downloads, so the owner opens http://192.168.4.1 in Safari/Chrome.
#include "web_export.h"
#include "web_page.h"
#include "board.h"
#include "wfg_export.h"
#include "wfg_sha256.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_random.h>

using namespace wfg;

static WebServer* g_srv = nullptr;
static Logger* g_lg = nullptr;
static Storage* g_st = nullptr;
static Proto* g_proto = nullptr;
static uint32_t g_dev = 0;
static char g_ssid[24], g_pass[16], g_ip[16] = "192.168.4.1";
static bool g_active = false;

struct ShaSink : Sink {
  Sha256 h;
  uint32_t n = 0;
  bool write(const char* s, size_t len) override { h.update((const uint8_t*)s, len); n += len; return true; }
};
struct ClientSink : Sink {
  WiFiClient& c;
  char buf[1400];
  size_t used = 0;
  bool ok = true;
  explicit ClientSink(WiFiClient& cl) : c(cl) {}
  bool flush() {
    if (used && ok) ok = c.write((const uint8_t*)buf, used) == used;
    used = 0;
    return ok;
  }
  bool write(const char* s, size_t len) override {
    while (len && ok) {
      size_t n = sizeof(buf) - used;
      if (n > len) n = len;
      memcpy(buf + used, s, n);
      used += n; s += n; len -= n;
      if (used == sizeof(buf)) flush();
    }
    return ok;
  }
};

static bool parseFmt(const String& f, ExportFormat& out, bool& raw) {
  raw = false;
  if (f == "wfg") { raw = true; return true; }
  if (f == "csv") { out = FMT_CSV; return true; }
  if (f == "gpx") { out = FMT_GPX; return true; }
  if (f == "geojson") { out = FMT_GEOJSON; return true; }
  return false;
}

static bool exportable(const String& name) {
  if (!Logger::validName(name.c_str())) return false;
  if (g_lg->recording() && name == g_lg->currentName()) return false;
  return true;
}

static void sendJson(int code, const String& s) {
  g_srv->sendHeader("Cache-Control", "no-store");
  g_srv->send(code, "application/json", s);
}

static void hRoot() {
  g_srv->sendHeader("Cache-Control", "no-store");
  g_srv->send_P(200, "text/html; charset=utf-8", WFG_PAGE_HTML);
}

static void hStatus() {
  char b[400];
  snprintf(b, sizeof(b),
           "{\"device\":\"%08X\",\"board\":\"%s\",\"fw\":\"%s\",\"state\":\"%s\",\"used\":%llu,\"total\":%llu,"
           "\"last_delete\":\"%s\"}",
           (unsigned)g_dev, WFG_BOARD_NAME, WFG_FW_VERSION_STR, state_name(g_lg->state()),
           (unsigned long long)g_st->usedBytes(), (unsigned long long)g_st->totalBytes(), g_proto->lastDeleteResult());
  sendJson(200, b);
}

struct ListStream { bool first; };
static void listCb(const SessionInfo& si, void* ctx) {
  ListStream* ls = (ListStream*)ctx;
  char b[360];
  char ok_sha[65] = "";
  g_lg->isExportConfirmed(si.name, ok_sha);  // quick check (size + marker); full re-hash happens before delete
  bool active = g_lg->recording() && !strcmp(si.name, g_lg->currentName());
  snprintf(b, sizeof(b),
           "%s{\"name\":\"%s\",\"session_id\":\"%s\",\"mode\":\"%s\",\"size\":%ld,\"records\":%u,\"closed\":%s,"
           "\"end_reason\":\"%s\",\"exported\":%s,\"ok_sha\":\"%s\",\"active\":%s,\"start_reason\":\"%s\"}",
           ls->first ? "" : ",", si.name, si.session_id, mode_name(si.mode), si.size, (unsigned)si.n_records,
           si.closed ? "true" : "false", si.closed ? end_reason_name(si.end_reason) : "", si.exported ? "true" : "false",
           ok_sha, active ? "true" : "false", start_reason_name(si.start_reason));
  ls->first = false;
  g_srv->sendContent(b);
}

static void hList() {
  // Chunked streaming: every session is listed, however many there are (review R4).
  g_srv->sendHeader("Cache-Control", "no-store");
  g_srv->setContentLength(CONTENT_LENGTH_UNKNOWN);
  g_srv->send(200, "application/json", "");
  g_srv->sendContent("[");
  ListStream ls{true};
  g_lg->forEachSession(listCb, &ls);
  g_srv->sendContent("]");
  g_srv->sendContent("");  // end of chunked response
}

static bool hashOf(const String& name, const String& fmt, char hex[65], uint32_t& size) {
  ExportFormat f;
  bool raw;
  if (!parseFmt(fmt, f, raw)) return false;
  if (raw) {
    long sz = 0;
    if (!g_lg->sha256File(name.c_str(), hex, &sz)) return false;
    size = (uint32_t)sz;
    return true;
  }
  ShaSink s;
  if (!export_session(*g_st, name.c_str(), f, s)) return false;
  s.h.finishHex(hex);
  size = s.n;
  return true;
}

static void hSha() {
  String name = g_srv->arg("name"), fmt = g_srv->arg("fmt");
  if (!exportable(name)) { sendJson(400, "{\"error\":\"bad-or-active-session\"}"); return; }
  char hex[65];
  uint32_t size = 0;
  if (!hashOf(name, fmt, hex, size)) { sendJson(404, "{\"error\":\"not-found\"}"); return; }
  char b[160];
  snprintf(b, sizeof(b), "{\"sha256\":\"%s\",\"size\":%u}", hex, (unsigned)size);
  sendJson(200, b);
}

static void hDownload() {
  String name = g_srv->arg("name"), fmt = g_srv->arg("fmt");
  if (!exportable(name)) { g_srv->send(400, "text/plain", "bad or active session"); return; }
  ExportFormat f;
  bool raw;
  if (!parseFmt(fmt, f, raw)) { g_srv->send(400, "text/plain", "bad fmt"); return; }
  char hex[65];
  uint32_t size = 0;
  if (!hashOf(name, fmt, hex, size)) { g_srv->send(404, "text/plain", "not found"); return; }
  const char* type = raw ? "application/octet-stream" : f == FMT_CSV ? "text/csv" : f == FMT_GPX ? "application/gpx+xml"
                                                                                               : "application/geo+json";
  String fn = name.substring(0, 7) + "." + fmt;
  g_srv->sendHeader("Content-Disposition", "attachment; filename=\"" + fn + "\"");
  g_srv->sendHeader("X-WFG-SHA256", hex);
  g_srv->sendHeader("Cache-Control", "no-store");
  g_srv->setContentLength(size);
  g_srv->send(200, type, "");
  WiFiClient c = g_srv->client();
  ClientSink cs(c);
  if (raw) {
    FILE* fp = g_st->open(name.c_str(), "rb");
    if (!fp) return;
    char buf[1024];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), fp)) > 0 && cs.write(buf, n)) {}
    g_st->close(fp);
  } else {
    export_session(*g_st, name.c_str(), f, cs);
  }
  cs.flush();
}

static void hConfirm() {
  String name = g_srv->arg("name"), sha = g_srv->arg("sha");
  bool ok = g_lg->confirmExport(name.c_str(), sha.c_str(), "wifi");
  sendJson(ok ? 200 : 409, ok ? "{\"ok\":true}" : "{\"ok\":false,\"why\":\"hash-mismatch-or-open-session\"}");
}

static void hDelete() {
  String name = g_srv->arg("name"), sha = g_srv->arg("sha");
  char why[40] = "";
  bool ok = g_proto->requestDelete(name.c_str(), sha.c_str(), millis(), why, sizeof(why));
  char b[120];
  snprintf(b, sizeof(b), "{\"ok\":%s,\"why\":\"%s\"}", ok ? "true" : "false", why);
  sendJson(ok ? 200 : 409, b);
}

void web_begin(Logger* lg, Storage* st, Proto* proto, uint32_t device_id) {
  if (g_active) return;
  g_lg = lg; g_st = st; g_proto = proto; g_dev = device_id;
  // Fresh random SSID suffix and WPA2 password every time export mode is entered (review R19). Nothing is derived
  // from the chip ID. Unambiguous alphabet (no 0/O, 1/l/I). esp_random() is a true RNG while the radio is on;
  // it is called after WiFi.mode() for that reason.
  WiFi.mode(WIFI_AP);
  static const char* A = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  static const char* a = "abcdefghjkmnpqrstuvwxyz23456789";
  char sfx[5];
  for (int i = 0; i < 4; i++) sfx[i] = A[esp_random() % 31];
  sfx[4] = 0;
  snprintf(g_ssid, sizeof(g_ssid), "WFG-LOGGER-%s", sfx);
  for (int i = 0; i < 10; i++) g_pass[i] = a[esp_random() % 31];  // 10 chars, ~49 bits
  g_pass[10] = 0;
  setCpuFrequencyMhz(240);  // faster CSV/GPX generation while exporting (not recording)
  WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
  WiFi.softAP(g_ssid, g_pass, 6, 0, 2);
  strncpy(g_ip, WiFi.softAPIP().toString().c_str(), sizeof(g_ip) - 1);
  g_srv = new WebServer(80);
  g_srv->on("/", HTTP_GET, hRoot);
  g_srv->on("/api/status", HTTP_GET, hStatus);
  g_srv->on("/api/list", HTTP_GET, hList);
  g_srv->on("/api/sha", HTTP_GET, hSha);
  g_srv->on("/dl", HTTP_GET, hDownload);
  g_srv->on("/api/confirm", HTTP_POST, hConfirm);
  g_srv->on("/api/delete", HTTP_POST, hDelete);
  g_srv->onNotFound([]() { g_srv->send(404, "text/plain", "Open http://192.168.4.1/"); });
  g_srv->begin();
  g_active = true;
}

void web_stop() {
  if (!g_active) return;
  g_srv->stop();
  delete g_srv;
  g_srv = nullptr;
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_OFF);
  setCpuFrequencyMhz(80);
  g_active = false;
}

void web_loop() { if (g_active) g_srv->handleClient(); }
bool web_active() { return g_active; }
const char* web_ssid() { return g_ssid; }
const char* web_password() { return g_pass; }
const char* web_ip() { return g_ip; }
uint32_t web_clients() { return g_active ? WiFi.softAPgetStationNum() : 0; }
