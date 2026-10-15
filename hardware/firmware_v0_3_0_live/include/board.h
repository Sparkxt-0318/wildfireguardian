// Board selection. Exactly one WFG_BOARD_* flag must be set in platformio.ini build_flags.
#pragma once
#if defined(WFG_BOARD_HELTEC_TRACKER_V11)
#include "board_heltec_tracker_v11.h"
#elif defined(WFG_BOARD_HELTEC_TRACKER_V2)
#include "board_heltec_tracker_v2.h"
#elif defined(WFG_BOARD_HELTEC_TRACKER_V10)
#include "board_heltec_tracker_v10.h"
#elif defined(WFG_BOARD_FIREBEETLE2_E)
#include "board_firebeetle2_esp32e_tel0157.h"
#elif defined(WFG_BOARD_GENERIC_ESP32S3)
#include "board_generic_esp32s3_uart_gnss.h"
#else
#error "No board selected: set one WFG_BOARD_* flag (HELTEC_TRACKER_V2/_V11/_V10, FIREBEETLE2_E, GENERIC_ESP32S3)"
#endif

#ifndef WFG_TFT_PANEL_ST7789
#define WFG_TFT_PANEL_ST7789 0
#endif
#ifndef WFG_PIN_GNSS_EN
#define WFG_PIN_GNSS_EN (-1)
#define WFG_GNSS_EN_ON_LEVEL 0
#endif
#ifndef WFG_PIN_TFT_PWR
#define WFG_PIN_TFT_PWR (-1)
#define WFG_TFT_PWR_ON_LEVEL 0
#endif
#ifndef WFG_PIN_LORA_FEM_POWER
#define WFG_PIN_LORA_FEM_POWER (-1)
#endif
#ifndef WFG_PIN_LORA_CS
#define WFG_PIN_LORA_CS (-1)
#define WFG_PIN_LORA_RST (-1)
#endif

// Low-battery clean stop: battery reading (divider x calibration) below this for 3 consecutive 10 s samples.
// UNVERIFIED until the ADC is calibrated against a multimeter (see README "Battery calibration").
#ifndef WFG_LOW_BATT_MV
#define WFG_LOW_BATT_MV 3400
#endif

#define WFG_FW_VERSION 3           // bump when record semantics change (also bump WFG_FORMAT_VERSION if layout changes)
#define WFG_FW_VERSION_STR "0.3.0" // 0.3.0: LIVE lines over USB; record format unchanged (WFG_FORMAT_VERSION 2)
