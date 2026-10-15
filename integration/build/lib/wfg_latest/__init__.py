"""wfg_latest: latest WildfireGuardian forecast (checkpoint c651f672...) to checked route, research construction.

Pipeline (each heavy step runs in its own Python process; see api.py):
  export_forecast  -> clock-bound latest forecast export (contract wfg.latest-forecast-contract/1.1)
  build_packet     -> regional hazard packet (wfg.latest-regional-packet/2.1; scalar max-remaining present-fire enclosure
                      under construction law wfg.hazard.construction/1, inherited radiation operator)
  rekey_request    -> a frozen routing request re-keyed onto the packet's members (numbers unchanged)
  route_and_check  -> one controlled routing attempt with the routing kit (30 s deadline, 3,072 MiB guard), its mandatory
                      runtime whole-road check, the authoritative decision and the offline independent checker
Research evidence only: not a calibrated joint forecast, not accuracy, not physical-safety evidence."""
__version__ = "1.0.0"
__all__ = ["api", "__version__"]
