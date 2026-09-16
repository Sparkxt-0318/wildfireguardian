"""Quality-control transforms for the WildfireGuardian research program.

Owned by A2 (data engineering and QC) this round. See ``timestamps.py`` and
``complexes.py``. Every function here FLAGS defective records with added
boolean columns; none of them drop rows silently.
"""
