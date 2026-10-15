#include "display.h"
#include "board.h"
#include <Arduino.h>

#define WFG_HAS_TFT (WFG_TFT_PANEL_ST7735S || WFG_TFT_PANEL_ST7789)
#if WFG_HAS_TFT
#include <LovyanGFX.hpp>

class LGFX_WFG : public lgfx::LGFX_Device {
#if WFG_TFT_PANEL_ST7789
  lgfx::Panel_ST7789 panel_;
#else
  lgfx::Panel_ST7735S panel_;
#endif
  lgfx::Bus_SPI bus_;

 public:
  LGFX_WFG() {
    {
      auto cfg = bus_.config();
      cfg.spi_host = WFG_TFT_SPI_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = WFG_TFT_SPI_HZ;
      cfg.freq_read = 16000000;
      cfg.spi_3wire = false;
      cfg.use_lock = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      cfg.pin_sclk = WFG_PIN_TFT_SCLK;
      cfg.pin_mosi = WFG_PIN_TFT_MOSI;
      cfg.pin_miso = -1;
      cfg.pin_dc = WFG_PIN_TFT_DC;
      bus_.config(cfg);
      panel_.setBus(&bus_);
    }
    {
      auto cfg = panel_.config();
      cfg.pin_cs = WFG_PIN_TFT_CS;
      cfg.pin_rst = WFG_PIN_TFT_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = WFG_TFT_WIDTH;
      cfg.panel_height = WFG_TFT_HEIGHT;
      cfg.memory_width = WFG_TFT_WIDTH;
      cfg.memory_height = WFG_TFT_HEIGHT;
      cfg.offset_x = WFG_TFT_OFFSET_X;
      cfg.offset_y = WFG_TFT_OFFSET_Y;
      cfg.offset_rotation = 0;
      cfg.readable = false;
      cfg.invert = WFG_TFT_INVERT;
      cfg.rgb_order = false;
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      panel_.config(cfg);
    }
    setPanel(&panel_);
  }
};

static LGFX_WFG tft;
static LGFX_Sprite fb(&tft);  // UI is laid out for 160x80 (16 bpp = 25.6 KB) -> flicker-free redraw
static float g_zoom = 1.0f;   // larger panels (fallback 240x240) get the same layout scaled up
#endif

static bool g_on = false;

static void backlight(bool on) {
  if (WFG_PIN_TFT_BL >= 0) {
    pinMode(WFG_PIN_TFT_BL, OUTPUT);
    digitalWrite(WFG_PIN_TFT_BL, on ? WFG_TFT_BL_ON_LEVEL : !WFG_TFT_BL_ON_LEVEL);
  }
}

void display_begin() {
#if WFG_HAS_TFT
  if (WFG_PIN_TFT_PWR >= 0) {
    pinMode(WFG_PIN_TFT_PWR, OUTPUT);
    digitalWrite(WFG_PIN_TFT_PWR, WFG_TFT_PWR_ON_LEVEL);
  }
  tft.init();
  tft.setRotation(WFG_TFT_ROTATION);
  tft.fillScreen(TFT_BLACK);
  fb.setColorDepth(16);
  fb.createSprite(160, 80);
  g_zoom = tft.width() >= 240 ? (float)tft.width() / 160.0f : 1.0f;
  fb.setTextSize(1);
#endif
  backlight(true);
  g_on = true;
}

bool display_is_on() { return g_on; }

void display_power(bool on) {
  if (on == g_on) return;
  g_on = on;
#if WFG_HAS_TFT
  if (on) { tft.wakeup(); backlight(true); }
  else { backlight(false); tft.sleep(); }
#else
  backlight(on);
#endif
}

void display_draw(const UiState& s) {
#if WFG_HAS_TFT
  if (!g_on) return;
  const uint16_t C_BG = TFT_BLACK, C_FG = TFT_WHITE, C_DIM = 0x8410, C_OK = TFT_GREEN, C_WARN = TFT_YELLOW,
                 C_BAD = TFT_RED;
  fb.fillScreen(C_BG);
  fb.setFont(&fonts::Font0);  // 6x8 px
  char b[40];
  // Row 0: state + mode (size 2 for the state)
  fb.setTextSize(2);
  uint16_t sc = s.recording ? C_BAD : (!strcmp(s.rec_state, "FULL") || !strcmp(s.rec_state, "FS ERR")) ? C_WARN : C_FG;
  fb.setTextColor(sc, C_BG);
  fb.setCursor(0, 0);
  fb.print(s.rec_state);
  if (s.recording && (millis() / 500) % 2) fb.fillCircle(fb.getCursorX() + 6, 7, 5, C_BAD);  // blinking dot
  fb.setTextSize(1);
  fb.setTextColor(C_FG, C_BG);
  fb.setCursor(104, 0);
  fb.print(s.mode);
  if (s.unexported) {
    fb.setCursor(104, 8);
    fb.setTextColor(C_WARN, C_BG);
    snprintf(b, sizeof(b), "%u unexp", (unsigned)s.unexported);
    fb.print(b);
  }
  // Row 2 (y=18): GNSS
  fb.setCursor(0, 18);
  if (!s.gnss_seen) { fb.setTextColor(C_BAD, C_BG); fb.print("GNSS: no data"); }
  else if (!s.fix) {
    fb.setTextColor(C_WARN, C_BG);
    if (s.sats >= 0) snprintf(b, sizeof(b), "NO FIX  sats %d", s.sats); else snprintf(b, sizeof(b), "NO FIX");
    fb.print(b);
  } else {
    fb.setTextColor(C_OK, C_BG);
    const char* ft = s.fix_type == 3 ? "3D" : s.fix_type == 2 ? "2D" : "FIX";
    if (s.hdop_x10 >= 0) snprintf(b, sizeof(b), "%s sats %d HDOP %d.%d", ft, s.sats, s.hdop_x10 / 10, s.hdop_x10 % 10);
    else snprintf(b, sizeof(b), "%s sats %d", ft, s.sats);
    fb.print(b);
  }
  // Row 3 (y=28): battery + storage
  fb.setTextColor(C_FG, C_BG);
  fb.setCursor(0, 28);
  if (s.batt_pct >= 0) snprintf(b, sizeof(b), "BAT %3d%% %d.%02dV", s.batt_pct, s.batt_mv / 1000, (s.batt_mv % 1000) / 10);
  else snprintf(b, sizeof(b), "BAT --");
  if (s.batt_pct >= 0 && s.batt_pct < 15) fb.setTextColor(C_BAD, C_BG);
  fb.print(b);
  fb.setTextColor(C_FG, C_BG);
  fb.setCursor(0, 38);
  uint32_t pct = s.fs_total_kb ? (s.fs_used_kb * 100 / s.fs_total_kb) : 0;
  snprintf(b, sizeof(b), "MEM %u%% used ~%uh left", (unsigned)pct, (unsigned)(s.hours_left + 0.5f));
  if (pct >= 90) fb.setTextColor(C_WARN, C_BG);
  fb.print(b);
  fb.setTextColor(C_FG, C_BG);
  // Row 5 (y=48): session / export
  fb.setCursor(0, 48);
  if (s.export_line1) { fb.setTextColor(TFT_CYAN, C_BG); fb.print(s.export_line1); }
  else if (s.session_no) {
    snprintf(b, sizeof(b), "S%06u  #%u%s", (unsigned)s.session_no, (unsigned)s.seq, s.resumed ? " RESUMED" : "");
    fb.print(b);
  }
  else { fb.setTextColor(C_DIM, C_BG); fb.print("hold 2.5s = start"); }
  fb.setCursor(0, 58);
  if (s.export_line2) { fb.setTextColor(TFT_CYAN, C_BG); fb.print(s.export_line2); }
  else if (s.last_event_no) {
    fb.setTextColor(C_FG, C_BG);
    snprintf(b, sizeof(b), "EVT %d %s %us ago", (int)s.last_event_no, s.last_event_located ? "loc" : "NO POS",
             (unsigned)s.last_event_age_s);
    fb.print(b);
  }
  // Bottom row (y=70): hold countdown or banner
  if (s.hold_text) {
    fb.fillRect(0, 69, 160, 11, 0x2104);
    fb.fillRect(0, 69, (160 * s.hold_progress) / 100, 11, 0x03EF);
    fb.setTextColor(C_FG);
    fb.setCursor(2, 71);
    fb.print(s.hold_text);
  } else if (s.banner) {
    fb.fillRect(0, 69, 160, 11, 0x0320);
    fb.setTextColor(C_FG);
    fb.setCursor(2, 71);
    fb.print(s.banner);
  }
  if (g_zoom == 1.0f) fb.pushSprite(0, 0);
  else fb.pushRotateZoom(tft.width() / 2, (int)(40 * g_zoom), 0, g_zoom, g_zoom);
#else
  (void)s;
#endif
}
