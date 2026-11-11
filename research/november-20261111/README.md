# November 2026 research update

This note summarizes separate, retrospective research conducted after the October release. It does not replace preserved benchmarks or promote a model. Numerical artifacts and scripts are held locally and are not included in this commit; this note alone does not independently reproduce them. Reviews referred to below were conducted by separate AI agents or software implementations, not independent human experts.

## Routing and missing inputs

A replay of the original 20 designed missions, two repetitions per arm, retained the 30-second request limit and sampled 3,072 MiB guard. The proposed implementation produced 15 checked-route missions and five model-scoped no-route outcomes; the internal reference produced 13 routes and seven unresolved outcomes. On the 26 shared-route executions per arm, medians were 6.903 seconds for the candidate and 6.859 seconds for the reference. This is not evidence of a speed advantage for shared outcomes.

A subsequent local native new-burn-probability mask overlay flagged 11 of the 15 saved route witnesses; four had no contact with that mask. Flagged means locally missing input, not observed danger; clear does not establish total input support or safety. Five no-route outcomes had no returned witness and were not included.

Under a separate conservative sensitivity blocking roads that touch missing-q cells, one of the 11 flagged missions had a checked alternative: 2,580 seconds versus 2,143 seconds originally, a 437-second increase. Nine had an origin or all destinations prohibited by the policy; one had no arrival in a restricted contact-only relaxation. These are not observed closures or real-world infeasibility. The four locally clear witnesses retained their arrivals. Both policies used a 30-second request cap and sampled memory guard; continuous-road thermal physics and source validation remain unresolved.

A separate exploratory cohort of 106 rekeyed requests returned 73 route witnesses, 29 raw model-scoped no-route claims and four timeouts. Independent model checks supported 27 of 29 no-route claims; two remained unproved. Fifty-four of 73 returned witnesses touched the local missing-q mask. The cohort reused existing packets and four parent fires, and 19 requests retained nonzero dose values from earlier histories; it is not a set of independent wildfire validations.

## Forecast and observation readiness

On two retrospective 2019 sensitivities (HUNT and LEVELOCK), experimental d4 produced slightly lower Brier error than persistence, but a fitted logistic baseline had better Brier score and average precision in both. Weather substitutions, timing approximations and retrospective scene selection limit the conclusions. This does not supersede the earlier failed primary superiority result or promote d4.

Synthetic tests showed that d4 can output hourly cumulative marginal probability fields and that preserved c651 can output hourly sampled histories. Independent replay checked the synthetic aggregation; no fire-arrival accuracy or calibration was established. The GOFER archive was recovered and checked against the publisher checksum. Its nominal hourly output labels do not establish continuous sensor coverage or physical arrival truth. Event overlap, observation support, historical input availability and independent calibration/test allocation remain open. A real-fire arrival-bound evaluation remains not ready.

## Fictional facility planning

A fictional two-vehicle demonstration selected after examining an archived scenario compared the same endpoints with and without a conservative all-horizon modeled fire restriction: 602 seconds / 6.041 km versus 1,288 seconds / 12.650 km. The unrestricted routes encountered modeled contact. Independent software checks reconstructed the restricted routes and specified holding periods. Vehicles do not return; the restriction is not an observed closure, and the result does not verify heat exposure, actual road status, destination suitability or safety.

Fictional Korean manager-review materials and an exploratory blank-versus-prefilled-document comparison were prepared. No care facility or emergency agency has been contacted or tested the materials through this work. Case difficulty and live-software effectiveness are unmeasured. Outreach is on hold. No resident data is included.

## Remaining boundaries

No additional external Dijkstra or commodity-router baseline has been matched to the original 20 missions. The latest-departure prototype was exercised on finite synthetic networks only. Human professional review, thermal and physical validation, realistic destination and transport data, and institutionally authorized feedback remain outstanding. A timeout is not evidence of no route; missing inputs are not evidence of safety.
