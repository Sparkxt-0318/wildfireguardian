// Streaming converters: session .wfg -> CSV / GPX 1.1 / GeoJSON (RFC 7946).
// All numbers are formatted from integers (no floating point) so the device output, host tests and
// phone_export/usb_export.py produce byte-identical files.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "wfg_record.h"
#include "wfg_storage.h"

namespace wfg {

class Sink {
 public:
  virtual ~Sink() {}
  virtual bool write(const char* s, size_t n) = 0;
  bool puts(const char* s);
  bool printf(const char* fmt, ...);
};

enum ExportFormat : uint8_t { FMT_CSV = 0, FMT_GPX = 1, FMT_GEOJSON = 2 };

struct ExportStats {
  uint32_t records = 0, bad_records = 0, fix_rows = 0, nofix_rows = 0, events = 0, events_located = 0;
  uint32_t segments = 0;
};

// Returns false if the file cannot be opened or the sink fails. Records that fail CRC are skipped and
// counted in stats.bad_records (CSV gets a row with record_type=CORRUPT so the gap stays visible).
bool export_session(Storage& st, const char* name, ExportFormat fmt, Sink& out, ExportStats* stats = nullptr);

// Helpers shared with tests
void fmt_e7(int32_t v, char* out);          // 1234567890 -> "123.4567890"
void fmt_centi(int64_t v, char* out);       // 1234 -> "12.34", -5 -> "-0.05"
void fmt_iso(uint32_t ymd, uint32_t ms_of_day, char* out);  // 2026-10-03T03:12:17.000Z
extern const char* kCsvHeader;

}  // namespace wfg
