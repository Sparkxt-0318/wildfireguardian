
### perim_6h (8 replicates)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 | s |
|---|---:|---:|---:|---:|
| plugin | 0.989 ± 0.032 | 0.1060 ± 0.0393 | 0.569 | 0.0 |
| bracket_composite | 1.000 ± 0.032 | 0.1424 ± 0.1124 | 0.492 | 4.8 |
| mcem | 1.028 ± 0.034 | 0.0684 ± 0.0389 | 0.492 | 29.9 |
| composite_scale | 1.086 ± 0.043 | 0.1439 ± 0.1115 | 0.553 | 14.6 |

composite_scale beats MCEM on held-out NLL in 1/8.

### perim_12h (8 replicates)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 | s |
|---|---:|---:|---:|---:|
| plugin | 0.905 ± 0.040 | 0.2723 ± 0.0843 | 0.752 | 0.0 |
| bracket_composite | 0.894 ± 0.030 | 0.3051 ± 0.1692 | 0.546 | 3.3 |
| mcem | 1.039 ± 0.030 | 0.1040 ± 0.0427 | 0.625 | 35.4 |
| composite_scale | 1.177 ± 0.084 | 0.3022 ± 0.1728 | 0.773 | 9.0 |

composite_scale beats MCEM on held-out NLL in 0/8.

### perim_24h (8 replicates)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 | s |
|---|---:|---:|---:|---:|
| plugin | 0.665 ± 0.046 | 0.5921 ± 0.1679 | 0.820 | 0.0 |
| bracket_composite | 0.647 ± 0.031 | 0.5827 ± 0.1819 | 0.620 | 0.7 |
| mcem | 1.040 ± 0.064 | 0.1177 ± 0.0384 | 0.670 | 36.5 |
| composite_scale | 1.367 ± 0.164 | 0.5162 ± 0.2126 | 1.196 | 4.9 |

composite_scale beats MCEM on held-out NLL in 0/8.

### perim_spotting_12h (8 replicates)

| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 | s |
|---|---:|---:|---:|---:|
| plugin | 0.879 ± 0.027 | 0.2843 ± 0.0759 | 0.749 | 0.0 |
| bracket_composite | 0.925 ± 0.008 | 0.1202 ± 0.0552 | 0.503 | 4.6 |
| mcem | 1.098 ± 0.015 | 0.0387 ± 0.0203 | 0.590 | 54.2 |
| composite_scale | 1.293 ± 0.027 | 0.1182 ± 0.0551 | 0.764 | 15.1 |

composite_scale beats MCEM on held-out NLL in 0/8.
