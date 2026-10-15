// WildfireGuardian field route logger - binary record format (format version 1).
// Hardware independent: compiled both into the ESP32 firmware and into host unit tests.
//
// Format version 2 (fw 0.2.0): adds REC_STATUS and resume attribution in SESSION_START. Readers decode v1 and v2.
// Every record is exactly WFG_RECORD_SIZE (48) bytes, little-endian, and ends with a CRC-32
// (IEEE 802.3, reflected, poly 0xEDB88320) over bytes 0..43. Session files are append-only
// sequences of records. See ../../../DATA_SCHEMA_draft.md for the field-by-field schema.
#pragma once
#include <stdint.h>
#include <stddef.h>

#define WFG_RECORD_SIZE 48
#define WFG_FORMAT_VERSION 2
#define WFG_MAGIC 0x4657u  // bytes 'W','F' on disk

namespace wfg {

enum RecType : uint8_t {
  REC_SESSION_START = 1,
  REC_FIX = 2,          // observation row with a valid position
  REC_NOFIX = 3,        // observation row without a valid position (gap preserved explicitly)
  REC_EVENT = 4,        // owner pressed the button (event marker)
  REC_CLOCK = 5,        // GNSS UTC first appeared or jumped relative to the monotonic clock
  REC_SESSION_END = 6,  // footer / close record
  REC_STATUS = 7,       // periodic device status (battery, storage, NMEA counters); format v2+
};

enum StartReason : uint8_t {   // SESSION_START header.flags0 (v1 files: always 0)
  START_OWNER_BUTTON = 0,
  START_AUTO_RESUMED_AFTER_RESET = 1,  // previous session was cut by a reset/brownout; this is a NEW session
};

enum StatusFlags : uint8_t {
  ST_BATT_VALID = 1u << 0,   // vbat fields hold a plausible reading
  ST_SCREEN_ON = 1u << 1,
  ST_GNSS_SEEN = 1u << 2,    // valid NMEA within the last 3 s
  ST_LOW_BATT_PENDING = 1u << 3,
};

enum MovementMode : uint8_t { MODE_UNKNOWN = 0, MODE_WALK = 1, MODE_VEHICLE = 2 };

enum NoFixReason : uint8_t {
  NOFIX_NA = 0,           // used on FIX rows
  NOFIX_RECEIVER = 1,     // GNSS sentences arrived but reported no valid position
  NOFIX_NO_DATA = 2,      // no complete NMEA epoch arrived within 1.5 x log interval
  NOFIX_CKSUM_ONLY = 3,   // only checksum-failed NMEA arrived in that window
};

enum EndReason : uint8_t {
  END_USER_STOP = 1,
  END_STORAGE_FULL = 2,
  END_LOW_BATTERY = 3,
  END_RECOVERED_ON_BOOT = 4,  // session was found unclosed at boot (power loss / crash)
  END_FS_ERROR = 5,
};

enum ClockKind : uint8_t { CLOCK_FIRST_UTC = 1, CLOCK_JUMP = 2 };

// Observation validity bits (u16 at offset 42 of FIX/NOFIX rows)
enum ObsValid : uint16_t {
  V_TIME = 1u << 0,         // utc_ms_of_day valid (from GGA or RMC)
  V_DATE = 1u << 1,         // utc_date valid (from RMC)
  V_POS = 1u << 2,          // lat/lon valid
  V_ALT = 1u << 3,          // altitude (MSL, from GGA) valid
  V_SPEED = 1u << 4,        // speed over ground valid (RMC, only when RMC status = A)
  V_COURSE = 1u << 5,       // course over ground valid (RMC field present and status = A)
  V_HDOP = 1u << 6,         // HDOP present (GGA)
  V_SATS = 1u << 7,         // satellites-used count present (GGA)
  V_RMC_ACTIVE = 1u << 8,   // RMC status was 'A'
  V_RAW_NMEA = 1u << 9,     // raw NMEA retained in sidecar (always 0 in format v1 firmware)
  V_FIXTYPE = 1u << 10,     // fix_type field derived from a GSA sentence
  V_CKSUM_ERR = 1u << 11,   // at least one checksum-failed sentence since the previous row
};

struct Header {
  uint8_t type;
  uint8_t flags0;    // per-type: OBS = epoch age in 10 ms units (0xFF = >= 2.55 s)
  uint32_t seq;      // 0-based, strictly +1 per record within a session file
  uint32_t mono_ms;  // ms since boot (esp_timer / millis); wraps after 49.7 days
};

struct SessionStart {
  uint32_t device_id;
  uint32_t session_no;
  uint8_t movement_mode;
  uint8_t board_rev;
  uint16_t fw_version;
  uint16_t log_interval_ms;
  uint8_t format_version;
  uint8_t record_size;
  uint32_t boot_count;
  uint32_t utc_date;        // v1 only: YYYYMMDD, 0 if unknown at start (v2 relies on the CLOCK record instead)
  uint32_t utc_ms_of_day;   // v1 only: 0xFFFFFFFF if unknown
  uint32_t resumed_from_session_no;  // v2: session cut by the reset, 0 = not a resume
  uint8_t reset_reason;     // v2: ESP-IDF esp_reset_reason_t at boot (1 POWERON, 3 SW, 4 PANIC, 6 TASK_WDT, 9 BROWNOUT ...), 0 unknown
  uint8_t start_reason;     // StartReason, stored in header.flags0
  uint32_t event_locate_max_age_ms;
};

struct Status {
  uint16_t vbat_mv;          // battery mV = pin mV x factor; 0xFFFF unknown
  uint16_t vbat_pin_mv;      // ADC pin mV (eFuse-calibrated analogReadMilliVolts), before the divider; 0xFFFF unknown
  uint16_t vbat_factor_x1000;// effective factor used (nominal divider x owner calibration) x 1000
  uint8_t flags;             // StatusFlags
  uint32_t fs_free_bytes;
  uint32_t fs_total_bytes;
  uint32_t nmea_ok;          // valid sentences since boot
  uint32_t nmea_bad_checksum;// checksum-failed sentences since boot
  uint32_t free_heap;        // bytes, 0 on host
};

struct Obs {  // FIX and NOFIX
  uint32_t utc_date;       // YYYYMMDD or 0
  uint32_t utc_ms_of_day;  // or 0xFFFFFFFF
  int32_t lat_e7;          // degrees * 1e7, WGS84 as received from GNSS (not filtered, not map-matched)
  int32_t lon_e7;
  int32_t alt_cm;          // altitude above mean sea level (GGA field 9), cm
  uint16_t speed_cmps;     // speed over ground, cm/s
  uint16_t course_cdeg;    // course over ground, 0.01 deg true
  uint16_t hdop_x100;      // HDOP * 100 (unitless dilution factor, NOT metres)
  uint8_t sats;            // satellites used in solution (GGA field 7)
  uint8_t gga_quality;     // GGA fix quality 0..8, 0xFF unknown
  uint8_t fix_type;        // GSA: 1 none, 2 = 2D, 3 = 3D, 0 unknown
  uint8_t nofix_reason;    // NoFixReason
  uint16_t valid;          // ObsValid bits
};

struct Event {
  uint32_t event_no;        // 1-based within the session
  uint32_t ref_fix_seq;     // seq of most recent FIX row before the press, 0xFFFFFFFF if none
  int32_t lat_e7;           // only meaningful when located == 1, else 0
  int32_t lon_e7;
  uint32_t ref_fix_age_ms;  // press time minus receive time of that fix, 0xFFFFFFFF if none
  uint32_t press_mono_ms;   // mono time of the press (header mono_ms = time written)
  uint16_t press_duration_ms;
  uint8_t located;          // 1 if ref_fix_age_ms <= event_locate_max_age_ms
  uint8_t source;           // 1 = device button
};

struct Clock {
  uint32_t utc_date;
  uint32_t utc_ms_of_day;
  int64_t offset_ms;  // utc_epoch_ms - mono_ms (new)
  int64_t delta_ms;   // new offset - previous offset (0 for FIRST_UTC)
  uint8_t kind;       // ClockKind
};

struct SessionEnd {
  uint8_t reason;
  uint32_t n_records_before;  // records preceding this one (incl. start)
  uint32_t n_fix;
  uint32_t n_nofix;
  uint32_t n_events;
  uint32_t crc32_before;      // CRC-32 over all file bytes preceding this record
  uint32_t torn_bytes_removed;
  uint32_t n_clock;
};

struct Record {
  Header h;
  union {
    SessionStart start;
    Obs obs;
    Event ev;
    Clock clk;
    SessionEnd end;
    Status st;
  };
};

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len);  // start with 0
inline uint32_t crc32(const uint8_t* data, size_t len) { return crc32_update(0, data, len); }

void encode(const Record& r, uint8_t out[WFG_RECORD_SIZE]);
// Returns false if magic or CRC is wrong or the type is unknown.
bool decode(const uint8_t in[WFG_RECORD_SIZE], Record& r);

const char* mode_name(uint8_t m);       // "UNKNOWN" / "WALK" / "VEHICLE"
const char* rec_type_name(uint8_t t);   // "SESSION_START", ...
const char* end_reason_name(uint8_t r);
const char* nofix_reason_name(uint8_t r);
const char* start_reason_name(uint8_t r);  // "OWNER_BUTTON" / "AUTO_RESUMED_AFTER_RESET"

}  // namespace wfg
