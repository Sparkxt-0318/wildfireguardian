# What a wind-aloft trigger would add to the gust rule

# 상층풍 기준은 돌풍 기준에 무엇을 더해 주는가

*kcf-aloft, 2026-11-18. 규칙은 결과를 계산하기 전에 `PROTOCOL.md`(9802a32)에 고정했습니다. 수치는 모두 `numbers.json`에 있습니다.*

## 한국어

**결과.** 검증할 수 있었던 한국 산불에서는, 같은 비용이라면 더해 주는 것이 없었습니다. 850 hPa(고도 약 1.4~1.5 km) 예보 풍속으로
울리는 기준을 돌풍 기준(예보 최대순간풍속 20 m/s 이상이 연속 2시간)과 같은 빈도로 울리도록 맞추면, 급속 확산을 더 많이 잡지도,
일관되게 더 일찍 잡지도 못했습니다.

- **돌풍 기준(예보).** 급속 확산이 있었던 9일 가운데 4일은 확산이 시작되는 시각에 이미 울린 상태였습니다(0, 1, 12, 21시간
  전부터). 확산이 없던 34일에는 한 번도 울리지 않았습니다. 봄철(2월 1일~5월 15일) 한 지점에서 평균 3.7일 울립니다.
- **같은 빈도로 맞춘 상층풍 기준(29.7 m/s).** 9일 중 3일.
- **상층풍 25 m/s.** 돌풍 기준과 같은 4일을 1~2시간 일찍 잡지만, 울리는 날이 3배(한 지점 11.3일)입니다.
- **캘리포니아 산불로 정한 값(15.2 m/s).** 9일 중 8일을 잡지만 봄철 104일 가운데 55일을 울립니다. 기준으로 쓸 수 없습니다.
- **관측 돌풍 기준(산불에서 50 km 안 기상청 종관관측소의 20 m/s 이상 돌풍).** 9일 중 1일(강릉 2022년 3월 5일)만 확산이
  시작될 때 울린 상태였습니다. 울진 2022년 3월 4~5일에는 50 km 안 어느 관측소도 14 m/s를 넘지 않았습니다.
- **2025년 3월 25일.** 예보 돌풍 기준은 09시부터 울려, 첫 급속 확산 시각(10시)보다 1시간 앞섰습니다. 상층풍 30 m/s 기준과 같은
  시각입니다. 50 km 안 관측소에서 20 m/s 돌풍이 처음 기록된 것은 14시 48분(구미)으로, 확산이 시작되고 거의 5시간 뒤였습니다.
  그날 차이를 만든 것은 지상이냐 상층이냐가 아니라 관측이냐 예보냐였습니다.

**표본.** 시간별 확산 거리가 있는 한국 산불 12건, 43일(산불 한 건의 하루를 1일로 셈). 급속 확산(5시간 확산 거리 3.75 km 초과)은
4건(의성, 울진, 강릉, 산청)의 9일뿐입니다. 울리는 빈도는 강원·경북 10개 지점에서 2022~2025년 봄철 전체와 2021년 봄철 일부로
셌습니다. 산불이 10건에 못 미치므로 비율은 내지 않고 건수만 적었습니다.

**이 결과가 보여 주지 않는 것.**

- 상층풍이 더 나쁘다는 뜻이 아닙니다. 9일 중 4일과 3일은 산불 4건으로는 구별할 수 없습니다.
- 9일 중 5일(의성 2025년 3월 22·23·26일, 산청 3월 22일, 울진 2022년 3월 10일)은 돌풍 기준도, 25 m/s 이상의 상층풍 기준도
  울리지 않았습니다. 바람 기준만으로는 잡히지 않는 확산입니다.
- 실제 운영 기준을 그대로 검증한 것이 아닙니다. 기상청 예보가 아니라 미국 GFS 예보를 썼고, '지속'은 이 연구가 정한 정의(예보값
  연속 2시간)이며, 공식 문서는 확인하지 못했습니다.
- 관측 돌풍 기준은 종관관측소(ASOS)만으로 계산했습니다(산불 위치에서 50 km 안 2~10곳, 1 m/s 단위). 더 촘촘한 자동기상관측소
  (AWS)는 읽지 못했으므로, 담당자가 실제로 보는 관측보다 성깁니다. 지점별로 봄철에 며칠 울리는지는 아직 집계하지 못했습니다(관측 자료를 받는 중).
- 2019~2020년 봄철은 당시 발표된 예보를 구할 수 없어 정해진 방식으로 세지 못했습니다(거친 대체 자료만 따로 제시).
- 3월 25일은 독립된 검증이 아닙니다. 850 hPa 바람이 그날을 가려낸다는 것은 규칙을 정하기 전에 이미 알려져 있었습니다. 그날을
  빼면 돌풍 기준은 8일 중 3일, 같은 빈도의 상층풍 기준은 8일 중 2일입니다.
- 두 번째 예보 모델(ECMWF)은 2023·2025년 산불에만 있습니다. 이 모델은 3월 25일 상층풍을 27.6 m/s로 예보해(GFS는
  32~33 m/s) 30 m/s 기준에 닿지 않았습니다.
- 누가 무엇을 했어야 했는지에 대한 판단이 아닙니다.

## English

**Result.** In the Korean fires that could be tested, nothing at the same cost. A trigger on the forecast wind at
850 hPa (about 1.4-1.5 km up), set to fire as often as the gust rule (forecast gust of 20 m/s or more for two
consecutive hours), warned no more fast runs and was not consistently earlier.

- **Gust rule, from forecasts.** On 4 of the 9 days with a fast run it was already firing when the run began (0, 1,
  12 and 21 h ahead). It never fired on the 34 days without a run. It fires on 3.7 days per place per spring
  (1 February to 15 May).
- **Wind aloft at the same alarm frequency (29.7 m/s).** 3 of 9.
- **Wind aloft at 25 m/s.** The same 4 days as the gust rule, 1-2 h earlier, for three times the alarm days
  (11.3 per place).
- **The threshold set on California fires (15.2 m/s).** 8 of 9, but it fires on 55 of the 104 days of a spring.
  Not usable as a trigger.
- **Observed-gust rule (a gust of 20 m/s or more at a KMA synoptic station within 50 km of the fire).** Firing
  when the run began on 1 of 9 days (Gangneung, 5 March 2022). At Uljin on 4-5 March 2022 no station within 50 km
  recorded more than 14 m/s.
- **25 March 2025.** The forecast gust rule fired from 09:00, one hour before the first run hour (10:00), at the
  same hour as wind aloft at 30 m/s. The first 20 m/s gust at a station within 50 km was recorded at 14:48 (Gumi),
  almost five hours after the run began. What mattered that day was forecast against observation, not surface
  against aloft.

**The n.** 12 Korean fires with an hourly reach, 43 fire-days. Only 4 fires (Uiseong, Uljin, Gangneung, Sancheong)
had a fast run (5 h reach above 3.75 km), on 9 days. Alarm frequency was counted at ten points in Gangwon and
Gyeongbuk over the springs of 2022-2025 and part of 2021. Fewer than 10 fires, so counts only, no rates.

**What it does not show.**

- Not that wind aloft is worse. 4 of 9 and 3 of 9 cannot be told apart with 4 fires.
- 5 of the 9 run days (Uiseong 22, 23 and 26 March 2025, Sancheong 22 March, Uljin 10 March 2022) had no alarm from
  the gust rule or from wind aloft at 25 m/s or more. A wind trigger of either kind does not catch those runs.
- Not the rule as operated. The forecasts are the US GFS, not KMA's; "persist" is this study's definition (two
  consecutive forecast hours); the official text was not read.
- The observed-gust rule uses KMA synoptic (ASOS) stations only: 2 to 10 within 50 km of a fire, in whole m/s.
  The denser AWS network was not read, so this is sparser than what an official sees. How many days per spring it fires at the ten points is not counted yet (station data still being fetched).
- Springs 2019-2020 could not be counted as specified: forecasts as issued were not reachable (a coarse
  substitute is reported separately).
- 25 March is not an independent test. The 850 hPa wind was known to flag it before the rules were written.
  Without it: gust rule 3 of 8, wind aloft at the same frequency 2 of 8.
- A second model (ECMWF) exists only for the 2023 and 2025 fires. It forecast 27.6 m/s aloft on 25 March where GFS
  had 32-33 m/s, below a 30 m/s trigger.
- Nothing here says what anyone should have done.

Details: `RESULTS.md`, `numbers.json`, `fig/lead_time.png`.
