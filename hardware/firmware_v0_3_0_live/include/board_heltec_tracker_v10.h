// Board header: Heltec Wireless Tracker V1.0 (first release, 2023-06). NOT RECOMMENDED TO BUY.
// Selected with -DWFG_BOARD_HELTEC_TRACKER_V10 (platformio env "tracker_v10"). Provided only so a V1.0 board
// that arrives by mistake can still be tested. Every value is UNVERIFIED on hardware.
//
// Sources (fetched 2026-10-03):
//  [MT10] Meshtastic variants/esp32s3/heltec_wireless_tracker_V1_0/variant.h (support level 3, "not actively supported")
//         https://github.com/meshtastic/firmware/blob/master/variants/esp32s3/heltec_wireless_tracker_V1_0/variant.h
//  [LOG]  Heltec hardware update log: V1.1 "Fixed an issue where the GNSS module loses power when LoRa starts";
//         V1.1 removed the separate GNSS Ctrl pin.
#pragma once

#define WFG_BOARD_NAME "Heltec Wireless Tracker V1.0 (UNVERIFIED)"
#define WFG_BOARD_REV_CODE 10

#define WFG_PIN_BUTTON 0            // [MT10 BUTTON_PIN 0]
#define WFG_BUTTON_ACTIVE_LOW 1

#define WFG_PIN_VEXT_CTRL 3         // [MT10 VEXT_ENABLE Vext (=3 in arduino-esp32 pins_arduino.h)]
#define WFG_VEXT_ON_LEVEL 0         // [MT10 VEXT_ON_VALUE LOW]  - OPPOSITE polarity to V1.1/V2
#define WFG_PIN_GNSS_EN 37          // [MT10 PIN_GPS_EN 37, GPS_EN_ACTIVE LOW]
#define WFG_GNSS_EN_ON_LEVEL 0
#define WFG_PIN_TFT_PWR 46          // [MT10 VTFT_CTRL 46 "needs this pulled low for TFT"]
#define WFG_TFT_PWR_ON_LEVEL 0

#define WFG_PIN_GNSS_RX 33          // [MT10]
#define WFG_PIN_GNSS_TX 34
#define WFG_PIN_GNSS_RST 35
#define WFG_GNSS_RST_ACTIVE_LEVEL 0
#define WFG_PIN_GNSS_PPS 36
#define WFG_GNSS_BAUD 115200
#define WFG_GNSS_MAX_RATE_HZ 10

#define WFG_TFT_PANEL_ST7735S 1
#define WFG_PIN_TFT_CS 38
#define WFG_PIN_TFT_RST 39
#define WFG_PIN_TFT_DC 40
#define WFG_PIN_TFT_SCLK 41
#define WFG_PIN_TFT_MOSI 42
#define WFG_PIN_TFT_BL 45           // [MT10 TFT_BL 45]  - differs from V1.1/V2 (21)
#define WFG_TFT_BL_ON_LEVEL 1
#define WFG_TFT_WIDTH 80
#define WFG_TFT_HEIGHT 160
#define WFG_TFT_OFFSET_X 26
#define WFG_TFT_OFFSET_Y (-1)
#define WFG_TFT_INVERT 1
#define WFG_TFT_ROTATION 1          // UNVERIFIED
#define WFG_TFT_SPI_HOST SPI3_HOST
#define WFG_TFT_SPI_HZ 40000000

#define WFG_PIN_VBAT_ADC 1          // [MT10 BATTERY_PIN 1]; V1.0 has no ADC_CTRL in [MT10]
#define WFG_PIN_VBAT_ADC_CTRL (-1)
#define WFG_VBAT_CTRL_USE_PULLUP 0
#define WFG_VBAT_DIVIDER_X1000 4900 // nominal 4.9 (Meshtastic base factor). UNVERIFIED: owner calibrates with USB 'CALVBAT <mV>'
                                    // (Meshtastic's extra x1.045 belongs to ADC_ATTEN_DB_2_5, not used here)

#define WFG_PIN_LED 18
#define WFG_FLASH_MB 8
#define WFG_HAS_LORA 1
#define WFG_PIN_LORA_CS 8
#define WFG_PIN_LORA_RST 12
#define WFG_PIN_LORA_SCK 9           // [MT] LORA_SCK 9 / MISO 11 / MOSI 10 / BUSY(DIO2 label) 13
#define WFG_PIN_LORA_MISO 11
#define WFG_PIN_LORA_MOSI 10
#define WFG_PIN_LORA_BUSY 13          // used only to put the unused SX1262 into sleep (UNVERIFIED current saving)
