"""Phase 2 item 3: battery life and deployment cost. Inputs and sources: configs/phase2.json -> economics,
documented in docs/PARAMETERS_PHASE2.md. Costs in US dollars. Results are estimates, not quotes.
"""
from __future__ import annotations

import math


def lora_time_on_air_s(payload_bytes, sf, bw_hz=125_000, cr=1, preamble=8, explicit_header=True, crc=True,
                       low_dr_opt=None):
    """LoRa time on air (Semtech AN1200.13 / SX1262 datasheet formula). cr=1 means 4/5."""
    t_sym = (2 ** sf) / bw_hz
    de = (sf >= 11 and bw_hz == 125_000) if low_dr_opt is None else low_dr_opt
    ih = 0 if explicit_header else 1
    n_payload = 8 + max(math.ceil((8 * payload_bytes - 4 * sf + 28 + 16 * int(crc) - 20 * ih)
                                  / (4 * (sf - 2 * int(de)))) * (cr + 4), 0)
    return (preamble + 4.25) * t_sym + n_payload * t_sym


def battery_life_years(e):
    """Average current from sleep plus per-beacon charge, then usable capacity over average current."""
    if e["radio"] == "lora":
        toa = lora_time_on_air_s(e["payload_bytes"], e["lora_sf"])
        q_tx = e["lora_tx_ma"] * toa  # mA*s per beacon
        q_beacon = q_tx + e["mcu_active_ma"] * e["mcu_active_s"]
    else:
        toa = float("nan")
        q_beacon = e["ble_adv_uc"] / 1000.0 + e["mcu_active_ma"] * e["mcu_active_s"]  # uC -> mA*s
    i_avg_ma = e["sleep_ua"] / 1000.0 + q_beacon / e["beacon_interval_s"]
    usable_mah = e["battery_mah"] * e["battery_usable_fraction"]
    hours = usable_mah / i_avg_ma
    years_no_sd = hours / 8766.0
    # Self-discharge as a constant annual loss of nominal capacity.
    years = usable_mah / (i_avg_ma * 8766.0 + e["battery_self_discharge_per_year"] * e["battery_mah"])
    return {"time_on_air_ms": toa * 1000, "avg_current_ua": i_avg_ma * 1000, "life_years": years,
            "life_years_no_self_discharge": years_no_sd}


def tag_unit_cost(e):
    parts = e["tag_parts_usd"]
    return float(sum(parts.values()))


def cost_per_km(tags_per_km, gateways_per_km, e, years=None):
    """Up-front cost per km (tags, gateways, install) and per year (battery replacement, backhaul)."""
    tag = tag_unit_cost(e) + e["tag_install_usd"]
    gw = e["gateway_usd"] + e["gateway_install_usd"]
    upfront = tags_per_km * tag + gateways_per_km * gw
    life = years if years is not None else battery_life_years(e)["life_years"]
    annual = (tags_per_km * (e["tag_parts_usd"].get("battery", 0.0) + e["tag_service_usd"]) / max(life, 0.1)
              + gateways_per_km * e["gateway_backhaul_usd_per_year"])
    return {"upfront_usd_per_km": upfront, "annual_usd_per_km": annual, "tag_unit_usd": tag, "gateway_unit_usd": gw}
