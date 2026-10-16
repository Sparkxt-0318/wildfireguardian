"""Verify published file identities and recorded table consistency; no routing run."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib, json

def main():
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'PUBLISHED_FILES.json').read_text())
    for item in manifest['files']:
        rel=Path(item['path'])
        assert not rel.is_absolute() and '..' not in rel.parts
        p=root/rel
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],rel
    rows=json.loads((root/'data/ROWS.json').read_text())
    summary=json.loads((root/'data/SUMMARY.json').read_text())
    assert len(rows)==200 and summary['rows']==200
    keys=[(r['policy'],r['cohort'],r['case_id'],r['rep'])for r in rows]
    assert len(set(keys))==200
    assert Counter(r['policy']for r in rows)=={f'A{i}':40 for i in range(5)}
    reference_missions=None
    for policy in [f'A{i}'for i in range(5)]:
        group=defaultdict(list)
        for row in rows:
            if row['policy']==policy:group[(row['cohort'],row['case_id'])].append(row)
        assert len(group)==20 and all(len(g)==2 and {r['rep']for r in g}=={1,2}for g in group.values())
        if reference_missions is None:reference_missions=set(group)
        else:assert set(group)==reference_missions
        stable=lambda pred:sum(all(pred(r)for r in g)for g in group.values())
        arm=next(a for a in summary['arms']if a['policy']==policy)
        assert arm['executions']==40
        assert arm['stable_own_routes']==stable(lambda r:r['own_outcome']=='CHECKED_ROUTE')
        assert arm['stable_scoped_refusals']==stable(lambda r:r['own_outcome']=='SCOPED_REFUSAL')
        assert arm['stable_full_passing_routes']==stable(lambda r:r['own_outcome']=='CHECKED_ROUTE' and r['full_policy_pass'] is True)
        counts=Counter(r['own_outcome']for r in rows if r['policy']==policy)
        assert counts==arm['all_outcomes']
    print(f"PASS: {len(manifest['files'])} published file hashes; 200 unique execution records; five policy tables reconciled.")
    print('This verifies recorded artifacts and table consistency. It does not rerun routing or independently prove continuous-road radiation bounds.')

if __name__=='__main__':main()
