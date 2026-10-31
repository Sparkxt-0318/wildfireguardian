"""Pure synthetic custody/admission probes. Never reads study inputs or predictions."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pickle
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import numpy as np
import pandas as pd


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def run(root):
    blind = load('audit_blind', root / 'research/forecast-v2/scripts/blind_test.py')
    assessment = load('audit_assessment', root / 'research/forecast-v2/scripts/score_cohorts.py')
    observations = []
    with tempfile.TemporaryDirectory(prefix='wfg-blind-tools-audit-') as td:
        tmp = Path(td)
        names = blind.MODEL_NAMES | {'persistence', 'logistic', 'dilation_best', *(f'dilation_{k}h' for k in (1,2,4,8))}
        def scored_fixture(tag, *, bad_coordinates=False, year=2026, failed=False):
            d = tmp / tag
            entries = d / 'predictions'
            (entries / 'cases').mkdir(parents=True)
            rp, cp, op = d / 'registry.json', d / 'cohort.json', d / 'scores.json'
            registry = dict(status='FROZEN', models={n: {'sha256': blind.C651_SHA if n=='c651_mc' else 'unverified'} for n in blind.MODEL_NAMES}, selected_model='base_seed0')
            blind.write(rp, registry)
            records, cases = [], []
            count = 10 if failed else 1
            for n in range(count):
                case = dict(event=f'synthetic_{n}', cutoff=f'{year}-01-01T00:00:00Z', endpoint=f'{year}-01-02T00:00:00Z', year=year, reference_kind='nirops_mapped_extent')
                cases.append(case)
                y = np.r_[np.zeros(20, dtype=np.uint8), np.ones(1, dtype=np.uint8)]
                p = np.where(y, .9, 0.)
                arrays = {f'p_{name}': np.zeros(len(y)) if name in {'persistence','dilation_best'} else p for name in names}
                row = np.arange(len(y), dtype=float) + .25 if bad_coordinates else np.zeros(len(y), dtype=int)
                col = np.arange(len(y)) + (100000 if bad_coordinates else 0)
                f = entries / 'cases' / f'{n}.npz'
                np.savez(f, y=y, row=row, col=col, **arrays)
                records.append(dict(case=case, status='SCORED', file=f'cases/{n}.npz', sha256=sha(f), scored_cells=len(y)))
            if failed:
                case = dict(event='omitted_synthetic', cutoff='2026-01-01T00:00:00Z', endpoint='2026-01-02T00:00:00Z', year=2026, reference_kind='nirops_mapped_extent')
                cases.append(case); records.append(dict(case=case, status='FAILED', reason='synthetic failure'))
            blind.write(cp, dict(cases=cases))
            blind.write(entries/'RECEIPT.json', dict(registry_sha256=sha(rp), cohort_sha256=sha(cp), cases=records))
            try:
                blind.score(SimpleNamespace(registry=rp,cohort=cp,entries=entries,out=op))
                result = json.loads(op.read_text())
                s = result['results']['nirops_mapped_extent']
                return dict(state='ACCEPTED', result_status=s['status'], entries=s['entries'], fires=len(s['fires']), primary_criteria=s['decision']['statistical_superiority_criteria_pass'], failed_cases=len(result['failed_cases']), superiority_claim_permitted=result['superiority_claim_permitted'])
            except Exception as e:
                return dict(state='RAISED', type=type(e).__name__, reason=str(e))
        for tag, kw in [('unbound_reference_coordinates',dict(bad_coordinates=True)),('scoring_bypasses_2026_eligibility',dict(year=1999)),('incomplete_cohort_primary_flag',dict(failed=True))]:
            value = scored_fixture(tag, **kw)
            passed = value['state']=='RAISED' or (tag=='incomplete_cohort_primary_flag' and not value.get('primary_criteria',True))
            observations.append(dict(id=tag, pass_defensive_admission=passed, fixture=kw, observed=value))

        # Cached covariates are returned without source files or provenance.
        envroot, cache = tmp/'empty_source', tmp/'cache'
        envroot.mkdir(); cache.mkdir()
        (envroot/'events.json').write_text(json.dumps([dict(id='synthetic')]))
        np.savez(cache/'synthetic_20260101T00.npz', raw=np.full((1,1,2),123456.,dtype=np.float32), names=np.array(['invented_channel']))
        environment = assessment.P.Environment(envroot, cache)
        value = environment.at('synthetic',pd.Timestamp('2026-01-01T00:00:00Z'))
        observations.append(dict(id='unauthenticated_environment_cache',pass_defensive_admission=False,observed=dict(state='RETURNED',raw=value.tolist(),names=environment.names,source_files_present=['events.json'])))

        # Drive the original assessment main down its resume branch only.
        # No model prediction or HEAVY lock is reached. All runtime objects are synthetic.
        d = tmp/'resume'; data=d/'data'; work=d/'work'; run=d/'run'
        for p in [data,work,run/'baselines',run/'heldout/cases']: p.mkdir(parents=True,exist_ok=True)
        (run/'baselines/logistic.pkl').write_bytes(pickle.dumps(None))
        (run/'baselines/dilation_choice.json').write_text('{"best_hours_per_cell":4}')
        frozen=dict(checkpoints={},synthetic=True,extraction_manifest_sha256='fixture')
        assessment.identities=lambda args: frozen
        assessment.P.Environment=lambda *args: SimpleNamespace()
        assessment.P.SPLIT={'held_out':{'us_2024':['synthetic']}}
        assessment.load_model=lambda *args,**kw:None
        assessment.P.host_record=lambda:dict(synthetic=True)
        sample=SimpleNamespace(t1='2024-01-01T00:00:00+00:00',hours=12.,meta={'t2':'2024-01-01T12:00:00+00:00'},initial=np.array([[True,False]]),endpoint=np.array([[True,True]]),score_mask=np.array([[False,True]]),environment=np.zeros((1,1,2)))
        assessment.P.perimeter_samples=lambda *args,**kw:[sample]
        case=dict(event='synthetic',cutoff=sample.t1,endpoint=sample.meta['t2'],hours=sample.hours)
        cid=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()[:24]
        fp=run/'heldout/FROZEN_ASSESSMENT.json'; assessment.write(fp,frozen)
        entry=run/'heldout/cases'/f'{cid}.npz'
        np.savez(entry,y=np.array([0],dtype=np.int8),row=[0],col=[1],p_persistence=[0.])
        stale='0'*64
        receipt=dict(case=case,case_id=cid,assessment_sha256=sha(fp),status='SCORED',sha256=sha(entry),scored_cells=1,initial_sha256=stale,endpoint_sha256=stale,environmental_snapshot_sha256=stale,reference_mask_sha256=stale)
        assessment.write(entry.with_suffix('.json'),receipt)
        prior=sys.argv
        sys.argv=['score_cohorts.py','--cohort','us2024','--data',str(data),'--work',str(work),'--run',str(run)]
        try:
            with redirect_stdout(io.StringIO()): assessment.main()
            with np.load(run/'heldout/synthetic.npz') as f: old_y=f['y'].tolist()
            receipt2=json.loads((run/'heldout/ASSESSMENT.json').read_text())
            observed=dict(state='ACCEPTED',status=receipt2['status'],source_endpoint=sample.endpoint[sample.score_mask].tolist(),reused_y=old_y,all_four_input_hashes_deliberately_wrong=True,model_columns=['p_persistence'])
        except Exception as e:
            observed=dict(state='RAISED',type=type(e).__name__,reason=str(e))
        finally: sys.argv=prior
        observations.append(dict(id='resume_ignores_source_array_hashes_and_modelset',pass_defensive_admission=observed['state']=='RAISED',observed=observed))
    paths=['research/forecast-v2/scripts/score_cohorts.py','research/forecast-v2/scripts/blind_test.py','research/forecast-v2/scripts/pipeline.py','forecast/wildfire/baselines.py','forecast/documents/preregistration_blind_test.md','research/forecast-v2/SPLIT.json']
    return dict(scope='Synthetic files and mocked numerical producers only; no study inputs/predictions/scores read; not evidence of errors in an actual heldout campaign',track_head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),host=platform.platform(),python=sys.version,numpy=np.__version__,pandas=pd.__version__,audit_script_sha256=sha(__file__),source_sha256={p:sha(root/p) for p in paths},observations=observations,checks=len(observations),passed=sum(r['pass_defensive_admission'] for r in observations),status='FAIL_TARGETED_BLIND_TOOL_ADMISSION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track-b',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=run(a.track_b.resolve()); a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['track_head','checks','passed','status']}));sys.exit(0 if result['checks']==result['passed'] else 1)
