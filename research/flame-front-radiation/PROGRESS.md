# Track 1A progress log

- 2026-10-29: 1A-1 library `wfg.radiation.law/2-flamefront` (isochrone, intensity, solid flame, enclosure, dose, provenance), NumPy only; 21 unit tests pass, including 1,000 random box-and-interval enclosure checks with nesting; commit 764ec2c.
- 2026-10-29: 1A-2 physics validation: specified E = 100 kW/m2 is within 3x of Butler and Cohen 1998 and Zarate 2008 but over-predicts the Morandini 2006 shrub decay 5.1x and 6.7x at 10 and 15 m; panel E separated from in-flame E and a measurement-consistent E = 22.6 kW/m2 (worst factor 1.52) recorded before any routing run; commit 56ae42c.
