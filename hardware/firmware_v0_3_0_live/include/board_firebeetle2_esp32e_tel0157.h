// Board header: FALLBACK architecture chosen by the sourcing lane (../sourcing/ORDER_NOW_draft.md):
//   DFRobot FireBeetle 2 ESP32-E (DFR0654-F, classic ESP32, 4 MB flash) + Gravity GNSS TEL0157 (UART)
//   + DFRobot GDI TFT (1.54" 240x240 IPS, ST7789 assumed). Selected with -DWFG_BOARD_FIREBEETLE2_E (env "fallback_fb2e").
// Sources (fetched 2026-10-03):
//  [FB] https://wiki.dfrobot.com/FireBeetle_Board_ESP32_E_SKU_DFR0654 : "User Button controlled by pin IO27/D4",
//       "LED controlled by pin IO2/D9", "Flash Memory 4 MB". GDI pin numbers NOT stated on that page.
//  [GN] https://wiki.dfrobot.com.cn/_SKU_TEL0157_Gravity_GNSS_Positioning_System (UART/I2C switch, NMEA)
// EVERY pin except the button/LED is UNVERIFIED and must be checked against the delivered boards' silkscreen and
// DFRobot GDI documentation before wiring. Wiring is jumper/Gravity cables only (no solder).
#pragma once

#define WFG_BOARD_NAME "FireBeetle2 ESP32-E + TEL0157 (fallback)"
#define WFG_BOARD_REV_CODE 80

#define WFG_PIN_BUTTON 27           // [FB] onboard user button IO27/D4: NOT a strap pin, so no boot-mode risk
#define WFG_BUTTON_ACTIVE_LOW 1     // UNVERIFIED polarity (firmware enables INPUT_PULLUP)

#define WFG_PIN_VEXT_CTRL (-1)      // TEL0157 powered from 3V3 directly (always on while the board is on)
#define WFG_VEXT_ON_LEVEL 1

#define WFG_PIN_GNSS_RX 16          // UNVERIFIED choice: ESP32 RX2 (IO16/D11?) <- TEL0157 "T"/TX (Gravity UART mode)
#define WFG_PIN_GNSS_TX 17          // UNVERIFIED choice: ESP32 TX2 (IO17/D10?) -> TEL0157 "R"/RX
#define WFG_PIN_GNSS_RST (-1)
#define WFG_GNSS_RST_ACTIVE_LEVEL 0
#define WFG_PIN_GNSS_PPS (-1)
#define WFG_GNSS_BAUD 9600          // UNVERIFIED: TEL0157 UART default; confirm on wiki/first boot (try 115200)
#define WFG_GNSS_MAX_RATE_HZ 10     // UNVERIFIED

#define WFG_TFT_PANEL_ST7735S 0
#define WFG_TFT_PANEL_ST7789 1      // UNVERIFIED controller for the GDI 1.54" 240x240 IPS
#define WFG_PIN_TFT_SCLK 18         // UNVERIFIED (expected GDI = VSPI 18/23/19 on FireBeetle)
#define WFG_PIN_TFT_MOSI 23         // UNVERIFIED
#define WFG_PIN_TFT_DC 25           // UNVERIFIED (GDI DC, D2?)
#define WFG_PIN_TFT_CS 14           // UNVERIFIED (GDI CS, D6?)
#define WFG_PIN_TFT_RST 26          // UNVERIFIED (GDI RES, D3?)
#define WFG_PIN_TFT_BL 13           // display BLK on D7 = IO13, as in CAD_v2_firebeetle's assembly guide. Never IO12
                                    // (D13): the module pulls BLK up through 10 k, and IO12 high at boot selects
                                    // 1.8 V flash, so the ESP32 does not start. UNVERIFIED on the delivered board.
#define WFG_TFT_BL_ON_LEVEL 1
#define WFG_TFT_WIDTH 240
#define WFG_TFT_HEIGHT 240
#define WFG_TFT_OFFSET_X 0
#define WFG_TFT_OFFSET_Y 0
#define WFG_TFT_INVERT 1            // typical for ST7789 IPS; UNVERIFIED
#define WFG_TFT_ROTATION 0
#define WFG_TFT_SPI_HOST VSPI_HOST
#define WFG_TFT_SPI_HZ 40000000

#define WFG_PIN_VBAT_ADC 34         // UNVERIFIED (FireBeetle VBAT divider on A2/IO34 expected)
#define WFG_PIN_VBAT_ADC_CTRL (-1)
#define WFG_VBAT_CTRL_USE_PULLUP 0
#define WFG_VBAT_DIVIDER_X1000 2000 // UNVERIFIED 1:2 divider; calibrate

#define WFG_PIN_LED 2               // [FB] IO2/D9; kept off
#define WFG_FLASH_MB 4              // [FB] 4 MB -> use partitions_4MB.csv
#define WFG_HAS_LORA 0
