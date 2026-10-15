// Wi-Fi export mode: device-hosted access point + plain-HTTP download page (no internet, no HTTPS possible).
#pragma once
#include <stdint.h>
#include "wfg_logger.h"
#include "wfg_proto.h"

void web_begin(wfg::Logger* lg, wfg::Storage* st, wfg::Proto* proto, uint32_t device_id);
void web_stop();
void web_loop();
bool web_active();
const char* web_ssid();
const char* web_password();
const char* web_ip();
uint32_t web_clients();
