# Night-1 weather run (13 Nov 2026, from 00:12 UTC)

`weather_night.py` calls `research/forecast-v2/scripts/rebuild_environment.slim_weather` (3 variables, ECMWF IFS through the Open-Meteo archive API) for each event, in the order given by `plan_night1.template.json`:

1. the 3 S-D9 pilots;
2. the 6 US2024 fires;
3. AlderCreek;
4. part-a, 490 events.

Dry-run estimate (`--estimate`, 12 Nov 16:35Z), in weighted calls:

| step | weighted calls |
|---|---|
| pilots | 103 |
| US2024 | 663 |
| AlderCreek | 71 |
| part-a | 6,150 |
| **total** | **6,986** |

## Resumability and budget

- **No re-sent requests.** Every response is cached per request signature, and each event writes `ecmwf_ifs_complete.json`. A relaunch therefore re-sends nothing that already succeeded, so no call is spent twice.
- **Throttle on weighted calls.** Rolling limits are ≤ 500 per 60 s, ≤ 4,500 per hour, and ≤ 9,500 per UTC day. The service's own limits are 600, 5,000 and 10,000. The day total counts the request log, so it holds across relaunches.
- **Logs.**
  - `weather_requests.csv` has one row per real request: time, workspace, event, locations, days, weighted calls and HTTP status.
  - `weather_runlog.txt` has one line per start, step and stop. Every restart is visible there with its time and stage.

## Operation

- The run is a harness-tracked background task. A self check-in every ~10 minutes relaunches it if it has died.
- The 2 h tracked-task limit or a container restart costs only the request in flight.
