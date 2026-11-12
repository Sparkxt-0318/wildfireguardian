| Mission | Arrival (s) | Published clearance (m) | Limit | Crop distance (m) | Margin bracket at same arrival (m) | +≤60 s | +≤300 s | +≤600 s | Horizon | Time-equivalent at 341 m/h (min) |
|---|---:|---:|---|---:|---|---|---|---|---|---:|
| hongseong_2023__20230402T140000Z_FW2 | 1459 | 295.0 | CROP/ORIGIN | 46 | [295, 295] | 295 m @ +0 s | 295 m @ +0 s | 295 m @ +0 s | 295 m @ +0 s | 52 |
| hongseong_2023__20230402T230000Z_FD1 | 531 | 857.5 | CROP | 303 | [858, 858] | 858 m @ +0 s | 858 m @ +0 s | 858 m @ +0 s | 858 m @ +0 s | 151 |
| miryang_2022__20220531T100000Z_FN1 | 1142 | 592.1 | CROP | 27 | [592, 593] | 592 m @ +0 s | 833 m @ +148 s | 833 m @ +148 s | 833 m @ +148 s | 104 |
| miryang_2022__20220601T020000Z_FW1 | 1270 | 1610.5 | CROP | 3 | [1780, 1781] | 1781 m @ +0 s | 1781 m @ +0 s | 1781 m @ +0 s | 1781 m @ +0 s | 283 |
| uiseong_andong_2025__20250323T010000Z_FD1 | 2460 | 3122.7 | CROP | 1239 | [3123, 3123] | 3123 m @ +0 s | 3123 m @ +0 s | 3123 m @ +0 s | 3123 m @ +0 s | 549 |
| uiseong_andong_2025__20250323T010000Z_FX2 | 2540 | 111.5 | FIRE | 3462 | [112, 112] | 112 m @ +0 s | 112 m @ +0 s | 112 m @ +0 s | 112 m @ +0 s | 20 |
| uiseong_andong_2025__20250324T090000Z_FL2 | 2143 | 287.0 | FIRE | 1266 | [287, 287] | 287 m @ +0 s | 287 m @ +0 s | 287 m @ +0 s | 287 m @ +0 s | 51 |
| uiseong_andong_2025__20250325T170000Z_FW1 | 1064 | 1490.7 | FIRE | 8757 | [1530, 1531] | 1531 m @ +0 s | 1531 m @ +0 s | 1531 m @ +0 s | 1531 m @ +0 s | 262 |
| uljin_2022__20220304T030000Z_FD1 | 1589 | 3166.2 | CROP | 2811 | [3166, 3166] | 3166 m @ +0 s | 3166 m @ +0 s | 3166 m @ +0 s | 3166 m @ +0 s† | 557 |
| uljin_2022__20220304T030000Z_FX1 | 3119 | 506.5 | FIRE | 860 | [506, 507] | 506 m @ +0 s | 680 m @ +140 s† | 680 m @ +140 s† | 680 m @ +140 s† | 89 |
| uljin_2022__20220304T060000Z_FL1 | 2067 | 1617.8 | CROP | 915 | [1618, 1618] | 1622 m @ +1 s | 1622 m @ +1 s | 1622 m @ +1 s | 1622 m @ +1 s | 285 |
| uljin_2022__20220304T120000Z_FW2 | 1655 | 179.9 | FIRE | 5520 | [180, 412] | 412 m @ +19 s | 412 m @ +19 s | 412 m @ +19 s | 412 m @ +19 s | 32 |
| yeongdeok_2025__20250325T190000Z_FX2 | 2512 | 503.7 | FIRE | 3057 | [504, 504] | 504 m @ +0 s | 504 m @ +0 s | 504 m @ +0 s | 504 m @ +0 s | 89 |
| yeongdeok_2025__20250325T230000Z_FL2 | 1922 | 640.8 | FIRE | 3668 | [641, 641] | 641 m @ +0 s | 641 m @ +0 s | 641 m @ +0 s | 641 m @ +0 s | 113 |
| yeongdeok_2025__20250326T080000Z_FW1 | 896 | 12870.8 | CROP | 12 | [12871, ≥6000 (cap)] | 12871 m @ +0 s | 12871 m @ +0 s | 12871 m @ +0 s | 12871 m @ +0 s | 2265 |

{
 "missions": 15,
 "fire_limited": 7,
 "crop_or_domain_limited": 8,
 "published_clearance_under_600m": 7,
 "later_route_with_much_larger_clearance": [
  {
   "mission": "miryang_2022__20220531T100000Z_FN1",
   "earliest_m": 592.0815894947435,
   "later_m": 832.7962859098334,
   "extra_s": 148,
   "deadline": "a0+300"
  },
  {
   "mission": "uljin_2022__20220304T030000Z_FX1",
   "earliest_m": 506.4893474072676,
   "later_m": 680.0988354479664,
   "extra_s": 140,
   "deadline": "a0+300"
  },
  {
   "mission": "uljin_2022__20220304T120000Z_FW2",
   "earliest_m": 179.90219814237207,
   "later_m": 411.86394262729397,
   "extra_s": 19,
   "deadline": "a0+60"
  }
 ],
 "time_shift_contact_margin_finite": 1
}
