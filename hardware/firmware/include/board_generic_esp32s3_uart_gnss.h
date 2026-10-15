// Board header TEMPLATE: fallback architecture = generic ESP32-S3 dev board (8 MB+ flash) + separate UART
// GNSS module (e.g. DFRobot TEL0157 Gravity GNSS in UART mode, or any NMEA-0183 module) + optional SPI ST7735
// 160x80 display. Selected with -DWFG_BOARD_GENERIC_ESP32S3 (platformio env "generic_esp32s3").
//
// ALL PIN VALUES BELOW ARE PLACEHOLDERS (UNVERIFIED). Fill them in from the actual boards bought and the
// wiring chosen by the sourcing lane. The logging core does not change; only this file does.
// Avoid ESP32-S3 strapping pins (0, 3, 45, 46) and USB pins (19, 20) for new wiring.
#pragma once

#define WFG_BOARD_NAME "Generic ESP32-S3 + UART GNSS (template)"
#define WFG_BOARD_REV_CODE 90

#define WFG_PIN_BUTTON 0            // BOOT button on most ESP32-S3 dev boards (strap pin: same rules as Heltec)
#define WFG_BUTTON_ACTIVE_LOW 1

#define WFG_PIN_VEXT_CTRL (-1)      // no switched rail: GNSS powered from 3V3 directly
#define WFG_VEXT_ON_LEVEL 1

#define WFG_PIN_GNSS_RX 18          // PLACEHOLDER: ESP32 RX  <- GNSS TX
#define WFG_PIN_GNSS_TX 17          // PLACEHOLDER: ESP32 TX  -> GNSS RX
#define WFG_PIN_GNSS_RST (-1)
#define WFG_GNSS_RST_ACTIVE_LEVEL 0
#define WFG_PIN_GNSS_PPS (-1)
#define WFG_GNSS_BAUD 9600          // PLACEHOLDER: TEL0157 UART default per DFRobot wiki - verify
#define WFG_GNSS_MAX_RATE_HZ 1      // PLACEHOLDER

#define WFG_TFT_PANEL_ST7735S 1     // set to 0 to run headless (serial status only)
#define WFG_PIN_TFT_CS 10           // PLACEHOLDERS
#define WFG_PIN_TFT_RST 9
#define WFG_PIN_TFT_DC 8
#define WFG_PIN_TFT_SCLK 12
#define WFG_PIN_TFT_MOSI 11
#define WFG_PIN_TFT_BL 7
#define WFG_TFT_BL_ON_LEVEL 1
#define WFG_TFT_WIDTH 80
#define WFG_TFT_HEIGHT 160
#define WFG_TFT_OFFSET_X 26
#define WFG_TFT_OFFSET_Y 1
#define WFG_TFT_INVERT 1
#define WFG_TFT_ROTATION 1
#define WFG_TFT_SPI_HOST SPI2_HOST
#define WFG_TFT_SPI_HZ 27000000

#define WFG_PIN_VBAT_ADC (-1)       // no battery sense wired -> battery shows "--"
#define WFG_PIN_VBAT_ADC_CTRL (-1)
#define WFG_VBAT_CTRL_USE_PULLUP 0
#define WFG_VBAT_DIVIDER_X1000 2000

#define WFG_PIN_LED (-1)
#define WFG_FLASH_MB 8
#define WFG_HAS_LORA 0
