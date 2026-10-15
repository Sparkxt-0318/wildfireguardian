// Board header: Heltec Wireless Tracker V2 (ESP32-S3FN8 + UC6580 + SX1262 + KCT8103L FEM, 0.96" TFT)
// Selected with build flag -DWFG_BOARD_HELTEC_TRACKER_V2 (platformio env "tracker_v2").
//
// Sources (fetched 2026-10-03):
//  [DS2]  Heltec Wireless Tracker V2 datasheet Rev 1.1 (Mar 2026), pin tables p.8-9, power p.11-12, GNSS p.13
//         https://resource.heltec.cn/download/Wireless_Tracker_V2/Wireless_Tracker_v2_Datasheet/Wireless%20Tracker%20v2.pdf
//  [WIKI2] https://wiki.heltec.org/docs/devices/open-source-hardware/esp32-series/lora-32/wireless-tracker-v2/
//  [MT2]  Meshtastic variants/esp32s3/heltec_wireless_tracker_v2/variant.h (master, 2026-10-03)
//         https://github.com/meshtastic/firmware/blob/master/variants/esp32s3/heltec_wireless_tracker_v2/variant.h
//  [HTLIB] Heltec_ESP32 src/HT_st7735.cpp: "#if defined(WIRELESS_TRACKER_V2) st7735_invert_colors(false)"
//  The V2 schematic link on [WIKI2] (HTIT-Tracker_V2.3.pdf) returned "Not Found" to this lane on 2026-10-03.
//  [SRC] The sourcing lane reports reading the V2 schematic/pinmap (../sourcing/HARDWARE_COMPATIBILITY_draft.md):
//        S2 "USER_SW" active LOW with 10k pull-up R21; VBAT divider 390k/100k (x4.9); GPIO7 FEM LDO pulled up.
#pragma once

#define WFG_BOARD_NAME "Heltec Wireless Tracker V2"
#define WFG_BOARD_REV_CODE 20

#define WFG_PIN_BUTTON 0            // [DS2 p.9 "GPIO0 USER_SW"], [MT2 BUTTON_PIN 0]
#define WFG_BUTTON_ACTIVE_LOW 1     // [SRC] R21 10k pull-up to 3V3, S2 to GND. Not read by this lane directly.

#define WFG_PIN_VEXT_CTRL 3         // [DS2 p.9 "GPIO3 ... Vext_Ctrl"], [MT2 VEXT_ENABLE 3]
#define WFG_VEXT_ON_LEVEL 1         // [MT2 VEXT_ON_VALUE HIGH]

#define WFG_PIN_GNSS_RX 33          // [MT2 GPS_RX_PIN 33], [DS2 p.8 GPIO33 "GNSS_TX" = module TX]
#define WFG_PIN_GNSS_TX 34          // [MT2 GPS_TX_PIN 34], [DS2 p.8 GPIO34 "GNSS_RX"]
#define WFG_PIN_GNSS_RST 35         // [DS2 p.8 GNSS_RST], [MT2]
#define WFG_GNSS_RST_ACTIVE_LEVEL 0
#define WFG_PIN_GNSS_PPS 36         // [DS2 p.8 PPS]
#define WFG_GNSS_BAUD 115200        // [MT2 GPS_BAUDRATE 115200]
#define WFG_GNSS_MAX_RATE_HZ 10     // [DS2 Table 3-7 "Update frequency Max 10 Hz"]

#define WFG_TFT_PANEL_ST7735S 1     // [MT2 ST7735S]; [DS2] says "0.96-inch 80x160 RGB TFT-LCD" (controller not named)
#define WFG_PIN_TFT_CS 38           // [DS2 p.9 TFT_CS], [MT2]
#define WFG_PIN_TFT_RST 39          // [DS2 p.9 TFT_RES], [MT2]
#define WFG_PIN_TFT_DC 40           // [DS2 p.9 TFT_RS], [MT2]
#define WFG_PIN_TFT_SCLK 41         // [DS2 p.9 TFT_SCLK], [MT2]
#define WFG_PIN_TFT_MOSI 42         // [DS2 p.9 TFT_SDIN], [MT2]
#define WFG_PIN_TFT_BL 21           // [DS2 p.8 "GPIO21 TFT_LED_K"], [MT2 TFT_BL 21]
#define WFG_TFT_BL_ON_LEVEL 1       // UNVERIFIED (see V1.1 header note)
#define WFG_TFT_WIDTH 80
#define WFG_TFT_HEIGHT 160
#define WFG_TFT_OFFSET_X 24         // [MT2 TFT_OFFSET_X 24]  differs from V1.1 (26). UNVERIFIED on delivered panel
#define WFG_TFT_OFFSET_Y 0          // [MT2 TFT_OFFSET_Y 0]
#define WFG_TFT_INVERT 0            // [MT2 TFT_INVERT false], [HTLIB invert_colors(false) for V2]
#define WFG_TFT_ROTATION 1          // landscape 160x80; UNVERIFIED (use 3 if upside down in the enclosure)
#define WFG_TFT_SPI_HOST SPI3_HOST
#define WFG_TFT_SPI_HZ 40000000

#define WFG_PIN_VBAT_ADC 1          // [DS2 p.9 "GPIO1 ... Vbat_Read"], [MT2 BATTERY_PIN 1]
#define WFG_PIN_VBAT_ADC_CTRL 2     // [DS2 p.9 "GPIO2 ... ADC_Ctrl"], [MT2 ADC_CTRL 2]
#define WFG_VBAT_CTRL_USE_PULLUP 1  // [MT2 ADC_USE_PULLUP]
#define WFG_VBAT_DIVIDER_X1000 4900 // [SRC] schematic R22 390k / 100k = 4.9 nominal. UNVERIFIED: owner calibrates with USB 'CALVBAT <mV>'
                                    // (Meshtastic's extra x1.045 belongs to ADC_ATTEN_DB_2_5, not used here)

#define WFG_PIN_LED 18              // [DS2 p.8 "GPIO18 ... LED_Write_Ctrl"], [MT2 LED_POWER 18]
#define WFG_FLASH_MB 8              // [DS2 "ESP32-S3FN8"]
#define WFG_HAS_LORA 1
#define WFG_PIN_LORA_CS 8           // [MT2]
#define WFG_PIN_LORA_RST 12
#define WFG_PIN_LORA_SCK 9           // [MT] LORA_SCK 9 / MISO 11 / MOSI 10 / BUSY(DIO2 label) 13
#define WFG_PIN_LORA_MISO 11
#define WFG_PIN_LORA_MOSI 10
#define WFG_PIN_LORA_BUSY 13          // used only to put the unused SX1262 into sleep (UNVERIFIED current saving)         // [MT2]
#define WFG_PIN_LORA_FEM_POWER 7    // [MT2 LORA_PA_POWER 7: KCT8103L LDO enable]; [SRC] pulled UP on board, so the
                                    // firmware drives it LOW to keep the unused FEM LDO off (saving UNVERIFIED)
