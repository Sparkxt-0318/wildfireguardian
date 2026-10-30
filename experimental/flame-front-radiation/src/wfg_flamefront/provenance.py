"""Sources and explicit scenario assumptions; no clinical route thresholds."""
from copy import deepcopy

LAW_VERSION="wfg.radiation.law/2-flamefront"
_DATA={
    "law_version":LAW_VERSION,
    "constants":{
        "heat_of_combustion_kj_kg":{"value":18608.,"source":"Selected export nominal heat content, FBFM40 convention; not Korean calorimetry"},
        "consumed_fuel_kg_m2":{"value":1.,"source":"Selected export scenario: 10 kg/m2 times consumed fraction 0.1"},
        "emissive_power_kw_m2":{"value":100.,"source":"Surface-fire scenario informed by Frankman et al. 2013; not an event-specific estimate","url":"https://doi.org/10.1071/WF11097"},
        "crown_emissive_power_kw_m2":{"value":200.,"source":"Butler et al. 2004, experimental crown-fire mean context","url":"https://doi.org/10.1139/x04-060"},
        "residence_s":{"value":11.52,"source":"Caller-overridable nominal point-residence scenario; coarse-cell duration must not be substituted silently"},
        "ros_max_m_s":{"value":3.,"source":"Declared numerical scenario cap, not a physical universal maximum"},
        "g_m_s2":{"value":9.80665,"source":"Conventional standard gravity"},
        "atmospheric_transmissivity":{"value":1.,"source":"No attenuation scenario"},
        "byram_coefficient":{"value":.0775,"source":"Byram 1959, as reproduced by Weise and Biging 1996 Eq. 5","url":"https://www.fs.usda.gov/psw/publications/weise/psw_1996_weise000.pdf"},
        "byram_exponent":{"value":.46,"source":"Same empirical relation; not universal across fuels"},
        "putnam_tilt_coefficient":{"value":1.4,"source":"Putnam 1965, reproduced by Weise and Biging 1996 Eq. 3","url":"https://www.fs.usda.gov/psw/publications/weise/psw_1996_weise000.pdf"},
    },
    "geometry":{"view_factor":"Projected solid angle via polygon edge-angle vectors","source":"Walton 2002 NISTIR 6925, Eq. 5, citing Hottel and Sarofim 1967 p.48","url":"https://doi.org/10.6028/NIST.IR.6925","front":"Polygonal approximation to leading and trailing isochrones between cell centres","receiver":"Each panel independently maximized, common receiver orientation is conservatively enclosed","distance_cutoff_m":None,"unknown":"UnsupportedGeometry by default","present_fire":"Explicit past ignition times required; scalar max-remaining envelope is insufficient"},
    "dose":{"linear_unit":"kJ/m2","tdu_unit":"(kW/m2)^(4/3) s","interpolation":"piecewise linear q; analytic integral of q^(4/3)","probit":{"a_kw":-14.9,"b":2.56,"a_w":-38.47847135225903,"source":"HSA 2023 TLUP guidance, Eisenberg model","url":"https://www.hsa.ie/media/4oap0mec/tlup-guidance-feb-2023-final.pdf","use":"Context only, not implemented as a clinical prediction or route threshold"},"injury_thresholds":{"status":"not located in a primary source during this run; prompt values 92,105,290,1000 not adopted as defaults"}},
    "bands":{"thresholds_kw_m2":[12.5,19.,29.,40.],"source":"AS 3959 construction exposure-band vocabulary","use":"Descriptive only; no vehicle-tenability or route-admission inference"},
    "omitted_processes":["convection","smoke toxicity and visibility","ember attack","vehicle shielding","terrain occlusion","parameter uncertainty"],
}


def provenance():
    return deepcopy(_DATA)
