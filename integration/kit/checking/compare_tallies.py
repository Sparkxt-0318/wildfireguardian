"""Compare two tally outputs of the same queue (for example the campaign's own analysis and an independent re-check made
in a separate directory). Usage: compare_tallies.py A/EXECUTIONS.json B/EXECUTIONS.json
Compares, row by row (by label): class, regional_class, reporting_class, resolved, authoritative_status, arrival,
runtime_whole_road, independent_verdict, independent_centre, independent_contact, contradictions, on_time, slot_state.
Exit 0 if identical in all those fields, 1 otherwise (differences printed)."""
import json, sys

FIELDS = ('class', 'regional_class', 'reporting_class', 'resolved', 'authoritative_status', 'arrival', 'runtime_whole_road',
          'independent_verdict', 'independent_centre', 'independent_contact', 'contradictions', 'on_time', 'slot_state')
a = {r['label']: r for r in json.load(open(sys.argv[1]))}
b = {r['label']: r for r in json.load(open(sys.argv[2]))}
diff = []
for label in sorted(set(a) | set(b)):
    if label not in a or label not in b:
        diff.append((label, 'MISSING_IN_' + ('A' if label not in a else 'B'))); continue
    for f in FIELDS:
        if a[label].get(f) != b[label].get(f):
            diff.append((label, f, a[label].get(f), b[label].get(f)))
print(json.dumps({'rows_a': len(a), 'rows_b': len(b), 'fields': FIELDS, 'differences': len(diff), 'first': diff[:20]}, indent=1))
sys.exit(0 if not diff else 1)
