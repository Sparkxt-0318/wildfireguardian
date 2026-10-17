"""WildfireGuardian Route-Check API (local HTTP wrapper around wfg_latest 1.0.0, kit v3, checkpoint c651).

The API never re-implements forecasting, routing or checking: every route check is one controlled attempt of the
frozen kit (``wfg_latest.api.route_and_check`` or, for the ablation policies, the frozen ablation worker launched by
the same controller), and every verdict is the kit's authoritative journey decision mapped onto three states.
"""
API_VERSION = "1.4.0"   # implements contracts/wfg_api_v1.yaml info.version
__all__ = ["API_VERSION"]
