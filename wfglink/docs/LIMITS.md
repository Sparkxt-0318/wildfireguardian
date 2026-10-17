# 한계 · Limits

The booth's limits card (key I, or a second display) and the printed A5 limits card in booth/placards/ show a short version of points 1 to 5; this page is the full version. Measured sizes of each effect are in results/NUMBERS.json once recorded.

The booth plays the clip files themselves (the setup change of 2026-10-15), so the earlier sixth limit about a re-filmed screen no longer applies. The LED turntable test was dropped by the booth change of 2026-10-15, so limit 5 no longer names it.

## 한국어

1. **카메라 하나로는 깊이를 알 수 없습니다.** 속도와 플럭스는 화면에 투영된 값입니다. m/초는 표시된 거리 범위에서만 맞고, 두 배 멀리 있는 불티는 화면에 보이는 것보다 두 배 빠릅니다. 불티 모드의 속도도 서는 자리(2.0 m)에서 잰 값이라, 그보다 가까이 든 휴대폰은 실제보다 빠르게, 멀리 든 휴대폰은 느리게 나옵니다.
2. **불티는 공기가 아닙니다.** 불티는 돌풍에 약 0.25~0.8초 늦게 반응하고(종단 속도 나누기 중력 가속도), 약 초속 2.5~8 m로 떨어집니다(Ellis 2010, 타지 않은 유칼립투스 껍질; 타는 불티는 더 가볍습니다). 그래서 화살표는 평활되고 지연된 바람 추정치이며, 세로 성분은 아래쪽으로 치우치고, 불티가 없는 곳에는 추정이 없습니다.
3. **보정에는 불확실성이 있습니다.** 도로 표시는 도로 면의 크기만 알려 줍니다. 높이 1.3 m 카메라에서 도로 위 1 m 높이의 불티를 도로 기준으로 계산하면 약 4.3배 멀리 있는 것으로 잘못 계산됩니다. 그래서 공중의 불티는 가정한 거리 범위로 계산하고 그 범위를 함께 표시합니다. 한국 차선 점선 길이는 도로 종류에 따라 3~10 m로 달라서(경찰청 매뉴얼) 길이를 가정하지 않습니다.
4. **빛나고 보이는 불티만 셉니다.** 개수는 최솟값입니다. 압축된 영상에서 어두운 불티는 사라지며, 검출 한계는 합성 검증에서 SNR로 측정합니다. 플럭스는 NIST처럼 제곱미터당 값이 아니라 화면 속 선의 길이당 값입니다.
5. **검증의 범위.** 검증은 합성 영상과 타당성 점검으로 했습니다. 실제 화재에서 NIST 장비와 나란히 비교하지는 않았습니다. 합성 영상에는 조정에 쓰지 않은 불일치 세트가 들어 있고, 타당성 점검은 실제 화재 영상에서 했습니다. 불티 모드의 휴대폰 점검(잰 1 m 길이를 따라 움직인 휴대폰)은 부스 자체의 측정을 확인할 뿐, 실제 불티 측정의 검증은 아닙니다.
6. **고정밀 모드는 아직 검증되지 않았습니다.** 고정밀 모드(--high-precision)는 선택 사항이고 기본값이 아닙니다. 후보 불티를 짧게 확인한 뒤 받아들인 불티만 셉니다. 목표(정밀도 99%, 독립 재현율 50%, 분당 오경보 0.1개 이하)는 낮추지 않았지만, 지금까지 이 목표를 충족한 후보는 없습니다. 모든 라벨과 검토는 에이전트가 만들었으므로 모든 정확도 수치는 잠정적(PROVISIONAL)입니다. 불티가 보이는 시험 영상이 적어 재현율은 증거 부족(INSUFFICIENT_EVIDENCE)으로 보고합니다.

## English

1. **One camera cannot see depth.** Speeds and flux are projections onto the picture. Meters per second hold only at the stated distance range; an ember twice as far away is twice as fast as shown. Ember mode speeds are likewise measured at the standing spot (2.0 m), so a phone held nearer shows faster than it moves, and one held farther away slower.
2. **Embers are not air.** They respond to gusts with a delay of roughly 0.25 to 0.8 s (terminal velocity divided by g) and fall at about 2.5 to 8 m/s (Ellis 2010, unburnt eucalypt bark; burning embers get lighter). So the arrows are a smoothed, lagged wind estimate; the vertical component is biased downward, and there is no estimate where there are no embers.
3. **Calibration is uncertain.** Road markings only scale the road surface. An ember 1 m above the road, seen by a camera 1.3 m high, would be placed about 4.3 times too far away. That is why airborne embers are scaled by an assumed distance range, shown with the result. Korean dashed lane lines vary from 3 to 10 m by road class (KNPA manual), so no dash length is assumed.
4. **Only what glows and is seen is counted,** so counts are lower bounds. Compression erases faint embers; the detection limit is measured as an SNR on synthetic video. Our flux is per length of a line in the picture, not NIST's per square meter.
5. **Scope of validation.** Validated on synthetic video and plausibility checks; not side by side with a NIST Emberometer in a real fire. The synthetic video includes a held-out mismatch suite never used for tuning, and the plausibility checks run on real fire clips. The phone checks of ember mode (a phone moved along a measured 1 m path) test the booth's own measurement, not the measurement of real embers.
6. **The high-precision mode is not validated.** The high-precision mode (--high-precision) is opt-in, never the default: it checks each candidate ember briefly and counts only the accepted ones. Its targets (99 percent precision, 50 percent independent recall, at most 0.1 false accepted tracks per minute) were never lowered, and no candidate has met them so far. Every label and review was made by agents, so every accuracy figure is PROVISIONAL; there are too few ember-positive test recordings to measure recall, which is reported as INSUFFICIENT_EVIDENCE.

Sources for the cited values: data/SOURCES.md (ellis2010, knpa_marking_manual, nist_tn2093).
