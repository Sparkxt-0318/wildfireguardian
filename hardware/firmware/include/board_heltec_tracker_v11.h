// Board header: Heltec Wireless Tracker V1.1 (HTIT-Tracker, ESP32-S3FN8 + UC6580 + SX1262 + 0.96" ST7735S)
// Selected with build flag -DWFG_BOARD_HELTEC_TRACKER_V11 (platformio env "tracker_v11").
//
// Sources (fetched 2026-10-03):
//  [DS11]  Heltec Wireless Tracker V1.1 datasheet, Rev 1.1.1 (2024-10-10), pin tables p.6-8, power p.10-11
//          https://resource.heltec.cn/download/Wireless_Tracker/Wireless%20Tracker1.1.pdf
//  [SCH11] Schematic HTIT-Tracker_V0.5 (V1.1)
//          https://resource.heltec.cn/download/Wireless_Tracker/Wireless_Tacker1.1/HTIT-Tracker_V0.5.pdf
//  [LOG]   Hardware update log: "set GPIO 3 HIGH to enable GNSS power source" (V1.1)
//          https://wiki.heltec.org/docs/devices/open-source-hardware/esp32-series/lora-32/wireless-tracker/hardware-update-log
//  [MT11]  Meshtastic variants/esp32s3/heltec_wireless_tracker/variant.h (master, 2026-10-03)
//          https://github.com/meshtastic/firmware/blob/master/variants/esp32s3/heltec_wireless_tracker/variant.h
//  [HTLIB] Heltec_ESP32 Arduino library src/HT_st7735.h + examples/GPS/GPSDisplayOnTFT (V1.x example)
//          https://github.com/HelTecAutomation/Heltec_ESP32
//
// Anything marked UNVERIFIED must be checked on the delivered board (see firmware/README.md).
#pragma once

#define WFG_BOARD_NAME "Heltec Wireless Tracker V1.1"
#define WFG_BOARD_REV_CODE 11

// ---- User button ----
#define WFG_PIN_BUTTON 0            // [DS11 p.6 "GPIO0, USER_SW"], [MT11 BUTTON_PIN 0]
#define WFG_BUTTON_ACTIVE_LOW 1     // [SCH11] USER_SW to GND with pull-up (ESP32-S3 strap pin). UNVERIFIED on board.
// GPIO0 is the ESP32-S3 boot strap: LOW at reset/power-up = ROM download mode (Espressif ESP32-S3 datasheet,
// "Strapping Pins"). Firmware never requires holding it at boot and ignores a press held through reset.

// ---- Vext rail: powers GNSS (UC6580 + LNA) and TFT on V1.1 ----
#define WFG_PIN_VEXT_CTRL 3         // [DS11 p.6 "GPIO3, Vext Ctrl"], [LOG], [MT11 VEXT_ENABLE 3]
#define WFG_VEXT_ON_LEVEL 1         // HIGH = on. [LOG], [MT11 VEXT_ON_VALUE HIGH], [HTLIB example VGNSS_CTRL HIGH]

// ---- GNSS (UC6580) UART ----
// Naming: WFG_PIN_GNSS_RX is the ESP32 pin that RECEIVES from the GNSS module.
#define WFG_PIN_GNSS_RX 33          // [MT11 GPS_RX_PIN 33], [HTLIB Serial1.begin(115200,SERIAL_8N1,33,34)]
#define WFG_PIN_GNSS_TX 34          // [MT11 GPS_TX_PIN 34]. [DS11] labels GPIO33 "GNSS_TX" (module's TX) - consistent.
#define WFG_PIN_GNSS_RST 35         // [DS11 p.7 GNSS_RST], [MT11 PIN_GPS_RESET 35, active LOW]
#define WFG_GNSS_RST_ACTIVE_LEVEL 0
#define WFG_PIN_GNSS_PPS 36         // [DS11 p.7 GNSS_PPS], [MT11 PIN_GPS_PPS 36] (not used by logger v1)
#define WFG_GNSS_BAUD 115200        // [MT11 GPS_BAUDRATE 115200], [HTLIB example]. Factory NMEA rate: UNVERIFIED (expect 1 Hz).
#define WFG_GNSS_MAX_RATE_HZ 10     // [DS11 GNSS table "Update frequency Max 10 Hz"] (V2 DS shows the same)

// ---- TFT ST7735S 160x80 (0.96") on SPI ----
#define WFG_TFT_PANEL_ST7735S 1     // [MT11 ST7735S], [DS11 "0.96-inch 80(H) x 160(V) RGB TFT-LCD"]
#define WFG_PIN_TFT_CS 38           // [DS11 p.8], [MT11], [HTLIB]
#define WFG_PIN_TFT_RST 39          // [DS11 p.8], [MT11], [HTLIB]
#define WFG_PIN_TFT_DC 40           // [DS11 p.8 "TFT_RS"], [MT11 ST7735_RS 40]
#define WFG_PIN_TFT_SCLK 41         // [DS11 p.8], [MT11], [HTLIB]
#define WFG_PIN_TFT_MOSI 42         // [DS11 p.8 "TFT_SDIN"], [MT11 ST7735_SDA 42]
#define WFG_PIN_TFT_BL 21           // [DS11 p.6 "GPIO21, TFT_LED_K"], [MT11 TFT_BL 21 "V1.1 PCB marking"]
#define WFG_TFT_BL_ON_LEVEL 1       // UNVERIFIED: [HTLIB] drives LED_K HIGH to light the panel; Meshtastic uses an
                                    // inverted PWM config. Check visually on first boot; flip here if dark.
#define WFG_TFT_WIDTH 80            // panel native (portrait) width
#define WFG_TFT_HEIGHT 160
#define WFG_TFT_OFFSET_X 26         // [MT11 TFT_OFFSET_X 26]  UNVERIFIED on delivered panel (edge garbage = wrong)
#define WFG_TFT_OFFSET_Y (-1)       // [MT11 TFT_OFFSET_Y -1]  UNVERIFIED
#define WFG_TFT_INVERT 1            // [MT11 default TFT_INVERT true for this variant] UNVERIFIED
#define WFG_TFT_ROTATION 1          // landscape 160x80; UNVERIFIED (use 3 if upside down in the enclosure)
#define WFG_TFT_SPI_HOST SPI3_HOST  // [MT11]
#define WFG_TFT_SPI_HZ 40000000     // [MT11 SPI_FREQUENCY]

// ---- Battery sense ----
#define WFG_PIN_VBAT_ADC 1          // [DS11 p.6 "GPIO1, Vbat_Read"], [MT11 BATTERY_PIN 1]
#define WFG_PIN_VBAT_ADC_CTRL 2     // [DS11 p.6 "GPIO2, ADC Ctrl"], [MT11 ADC_CTRL 2]
#define WFG_VBAT_CTRL_USE_PULLUP 1  // [MT11 ADC_USE_PULLUP: enable = INPUT_PULLUP, disable = INPUT_PULLDOWN]
#define WFG_VBAT_DIVIDER_X1000 4900 // nominal 4.9 (390k/100k, same as Meshtastic base factor 4.9). UNVERIFIED: owner calibrates with USB 'CALVBAT <mV>'
                                    // (Meshtastic's extra x1.045 belongs to ADC_ATTEN_DB_2_5, not used here)

// ---- Other ----
#define WFG_PIN_LED 18              // [DS11/MT11 LED_POWER 18] white LED; kept OFF to save power
#define WFG_FLASH_MB 8              // [DS11 "ESP32-S3FN8" = 8 MB in-package flash]; no PSRAM in FN8
#define WFG_HAS_LORA 1              // SX1262 present; logger keeps it in reset/sleep (not used)
#define WFG_PIN_LORA_CS 8           // [MT11] held HIGH so the radio stays deselected
#define WFG_PIN_LORA_RST 12
#define WFG_PIN_LORA_SCK 9           // [MT] LORA_SCK 9 / MISO 11 / MOSI 10 / BUSY(DIO2 label) 13
#define WFG_PIN_LORA_MISO 11
#define WFG_PIN_LORA_MOSI 10
#define WFG_PIN_LORA_BUSY 13          // used only to put the unused SX1262 into sleep (UNVERIFIED current saving)         // [MT11]
