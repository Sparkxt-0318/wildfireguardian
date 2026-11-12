
### kriged_calibrated (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| hard_hourly | 0.925 | 0.0390 | 0.364 (0.366 / 0.351) | 9.9 | — | 0/1 |
| plugin | 0.870 | 0.0586 | 0.380 (0.364 / 0.462) | 0.1 | — | 1/1 |
| soft_risk_softfeat | 0.884 | 0.0414 | 0.418 (0.428 / 0.363) | 13.2 | — | 0/1 |
| mcem | 0.981 | 0.0439 | 0.436 (0.427 / 0.481) | 324.7 | — | — |
| mcem_long | 0.983 | 0.0421 | 0.404 (0.390 / 0.477) | 1450.9 | — | 0/1 |

### kriged_correlated (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| hard_hourly | 0.926 | 0.0407 | 0.420 (0.426 / 0.387) | 10.4 | — | 0/1 |
| plugin | 0.874 | 0.0422 | 0.398 (0.410 / 0.322) | 0.1 | — | 0/1 |
| soft_risk_softfeat | 0.882 | 0.0407 | 0.452 (0.463 / 0.389) | 15.7 | — | 0/1 |
| mcem | 0.980 | 0.0601 | 0.608 (0.600 / 0.650) | 326.9 | — | — |

### kriged_miscal (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| hard_hourly | 0.797 | 0.0664 | 0.464 (0.481 / 0.352) | 7.5 | — | 1/1 |
| plugin | 0.755 | 0.0783 | 0.481 (0.485 / 0.456) | 0.1 | — | 1/1 |
| soft_risk_softfeat | 0.793 | 0.0464 | 0.413 (0.419 / 0.382) | 7.8 | — | 1/1 |
| soft_risk_softfeat_recal | 0.731 | 0.0626 | 0.432 (0.449 / 0.322) | 10.5 | — | 1/1 |
| mcem_recal | 0.979 | 0.0393 | 0.627 (0.641 / 0.538) | 327.9 | — | 1/1 |
| mcem | 0.895 | 0.0305 | 0.454 (0.437 / 0.542) | 408.9 | — | — |

### perim_3h (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 0.984 | 0.0554 | 0.396 (0.365 / 0.538) | 0.0 | — | 1/1 |
| bracket_composite | 0.978 | 0.0305 | 0.482 (0.478 / 0.504) | 16.9 | — | 1/1 |
| meanfield_nll | 1.034 | 0.0391 | 0.453 (0.416 / 0.619) | 54.7 | — | 1/1 |
| meanfield_brier | 0.000 | 15.0373 | 1.000 (1.000 / 1.000) | 0.3 | — | 1/1 |
| mcem | 0.976 | 0.0279 | 0.483 (0.465 / 0.569) | 356.5 | — | — |

### perim_6h (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 1.001 | 0.1065 | 0.523 (0.473 / 0.738) | 0.0 | — | 1/1 |
| bracket_composite | 0.959 | 0.0700 | 0.525 (0.537 / 0.455) | 6.8 | — | 1/1 |
| meanfield_nll | 1.037 | 0.0614 | 0.658 (0.650 / 0.699) | 197.2 | — | 1/1 |
| meanfield_brier | 1.038 | 0.0840 | 0.750 (0.747 / 0.765) | 38.2 | — | 1/1 |
| mcem | 0.990 | 0.0342 | 0.434 (0.395 / 0.604) | 390.9 | — | — |

### perim_12h (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 0.940 | 0.2807 | 0.685 (0.612 / 0.995) | 0.0 | — | 1/1 |
| bracket_composite | 0.857 | 0.1702 | 0.542 (0.523 / 0.637) | 14.7 | — | 1/1 |
| meanfield_nll | 0.996 | 0.1427 | 0.748 (0.454 / 1.585) | 402.4 | — | 1/1 |
| meanfield_brier | 1.011 | 0.1775 | 1.066 (1.033 / 1.232) | 168.7 | — | 1/1 |
| mcem | 1.012 | 0.0720 | 0.550 (0.543 / 0.591) | 376.3 | — | — |

### perim_24h (1 replicates; median crossing time 6.72 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 0.690 | 0.5861 | 0.768 (0.796 / 0.585) | 0.0 | — | 1/1 |
| bracket_composite | 0.583 | 0.4361 | 0.558 (0.502 / 0.801) | 0.9 | — | 1/1 |
| meanfield_nll | 0.911 | 0.2704 | 1.136 (1.182 / 0.835) | 375.6 | — | 1/1 |
| meanfield_brier | 0.890 | 0.2319 | 1.147 (1.196 / 0.820) | 339.4 | — | 1/1 |
| mcem | 0.969 | 0.0538 | 0.556 (0.484 / 0.850) | 284.5 | — | — |

### perim_nonexp_12h (1 replicates; median crossing time 21.39 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 0.317 | -1.4566 | 0.580 (0.473 / 0.979) | 0.1 | — | 1/1 |
| bracket_composite | 0.270 | -1.4790 | 0.637 (0.546 / 1.000) | 1.3 | — | 0/1 |
| meanfield_nll | 0.267 | -0.3839 | 0.634 (0.542 / 1.000) | 20.7 | — | 1/1 |
| meanfield_brier | 0.309 | -0.5278 | 0.589 (0.479 / 0.997) | 11.3 | — | 1/1 |
| mcem | 0.274 | -1.4752 | 0.635 (0.543 / 1.000) | 22.0 | — | — |

### perim_spotting_12h (1 replicates; median crossing time 6.18 h)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |
|---|---:|---:|---:|---:|---:|---:|
| plugin | 0.922 | 0.3902 | 0.665 (0.609 / 0.912) | 0.0 | — | 1/1 |
| bracket_composite | 0.910 | 0.0990 | 0.461 (0.451 / 0.514) | 8.6 | — | 1/1 |
| meanfield_nll | 1.163 | 0.1713 | 1.223 (0.712 / 2.635) | 335.2 | — | 1/1 |
| meanfield_brier | 1.152 | 0.1339 | 1.117 (0.712 / 2.308) | 132.5 | — | 1/1 |
| mcem | 1.100 | 0.0340 | 0.510 (0.323 / 1.058) | 429.9 | — | — |
