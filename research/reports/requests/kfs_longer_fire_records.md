# Draft request: KFS/NIFoS fire records older than the Open API's range

Status: DRAFT ONLY. Not sent. No account created, no form submitted, no terms
of service accepted.

**SEND CONDITION: only send this if `research/data/checks/probe_kfs_api.py`
shows that the KFS wildfire statistics Open API (registry id
kfs_fire_stats_api) does NOT reach back to 1991.** As of this draft
(2026-09-16), that probe has not run: `DATA_GO_KR_KEY` is unset (human gate
WJ-001), so whether the API already reaches 1991 is unknown. Run the probe
first. If the API does reach 1991, or reaches far enough back for the
program's needs, this letter is not needed and should not be sent.

---

**Subject: Request for Korean wildfire occurrence records prior to the Open API's available range**

To the Korea Forest Service (산림청) / National Institute of Forest Science
(국립산림과학원, NIFoS),

We are a small Korea-focused research program studying Korean wildfire
behavior, using publicly available Korea Forest Service datasets, including
the wildfire occurrence statistics Open API and the 산불통계데이터 and
산불상태이력 file datasets on 공공데이터포털.

We queried the Open API for wildfire records going back to [YEAR: fill in
the earliest year the probe actually returned real data for, from
research/data/checks/probe_kfs_api.py's output] and found that it does not
return records before that year. We would like to ask whether earlier
wildfire occurrence records exist in a form that could be shared for
research use, for example an internal archive, an older statistical
yearbook, or a scanned record, covering the period back toward 1991.

We are asking only for aggregate occurrence records (date, location at
whatever administrative level is available, and area burned if recorded), not
any restricted or personal data. This is for a non-commercial Korean research
program studying long-run patterns in Korean wildfire occurrence; we will not
redistribute anything you are able to share, and we will cite the source
appropriately in any resulting report.

Thank you for maintaining these records and for considering this request.

Sincerely,
[sender name and affiliation to be filled in before sending]

---

Notes for whoever sends this (not part of the letter):

- Fill in the bracketed year from the probe's actual output before sending.
  Do not send with the placeholder still in the letter.
- If the probe shows the API already reaches close to 1991, this letter is
  moot; do not send it, and update `research/data/REGISTRY.yaml`'s
  `kfs_fire_stats_api.temporal_coverage` from the probe result instead.
