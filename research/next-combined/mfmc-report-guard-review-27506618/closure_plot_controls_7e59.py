"""Independent closure/manual report checks using source bytes and synthetic rows."""
from pathlib import Path
import ast,copy,gzip,hashlib,importlib.util,json,sys,tempfile
import numpy as np,pandas as pd,pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b';OUT=TASK/'work/mfmc-report-guard-independent-review'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'forecast'))
from forecast.tests import test_report_comparison as T
CONTRACT=json.loads((TASK/'work/mfmc-final-independent-review/SOURCE_CONTRACT.json').read_text());SOURCE_BYTES={rel:(ROOT/rel).read_bytes() for rel in CONTRACT['source_pins']}
need=lambda ok,msg: (_ for _ in ()).throw(AssertionError(msg)) if not ok else None
need(all(hashlib.sha256(b).hexdigest()==CONTRACT['source_pins'][rel] for rel,b in SOURCE_BYTES.items()),'immutable61source changed')
checks=[]
def note(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
def report():
 s=importlib.util.spec_from_file_location('independent_report_closure',ROOT/'research/forecast-v2/scripts/report.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r);return r
def command(f,index,manifest):return ['synthetic-python',str(f.evidence/'scripts/pipeline.py'),'compare','--data-root',str(f.root/'NO_ENV_READ'),'--perimeters',str(f.root/'NO_PERIM_READ'),'--work',str(f.root/'NO_CACHE_READ'),'--run',str(f.run),'--data-manifest-sha256',manifest,'--epochs','3','--seed','0','--hidden','16','--lr','.003','--samples-per-step','1','--max-fit-intervals-per-fire','3','--intervals-per-epoch','0','--threads','2','--n-samples','1024','--balance','--compare-case-index',str(index),'--artifact-suffix','_a06']
def closed_fixture(R,folder,mp):
 constants={k:getattr(R,k) for k in ['COMPARISON_PROTOCOL_SHA256','COMPARISON_SOURCE_SHA256','COMPARISON_AUDITOR_SHA256','COMPARISON_CURRENT_AUDITORS']};f=T.fixture_comparison(R,folder,mp)
 (f.root/'forecast/wildfire/model.py').unlink()
 for rel,b in SOURCE_BYTES.items():p=f.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 for k,v in constants.items():mp.setattr(R,k,v)
 protocol=json.loads((f.evidence/'RUN_PROTOCOL.json').read_text());cases=protocol['mean_field_compare']['cases'];sources=dict(CONTRACT['source_pins'])
 for i,(p,recpath) in enumerate(zip(f.outputs,f.receipts)):
  d=json.loads(p.read_text());case=cases[i]
  for row in d['rows']:
   row.update(country=case['country'],event=case['event'],cutoff=case['cutoff'])
   if row['horizon_kind']=='survey':row['hours']=case['survey_hours']
  T.write(p,d);rec=json.loads(recpath.read_text());rec.update(source_sha256=sources,data_manifest_sha256=protocol['data_manifest_sha256'],command=command(f,i,protocol['data_manifest_sha256']));T.write(recpath,rec)
 rec=json.loads(f.aggregate_receipt.read_text());rec['source_sha256']=sources;T.write(f.aggregate_receipt,rec);f.sources=sources;f.cases=cases;T.resign(R,f)
 snap=f.evidence/'source_snapshots'/R.COMPARISON_AUDITOR_SHA256/'audit_fit_coverage.py.gz';snap.parent.mkdir(parents=True,exist_ok=True);snap.write_bytes(gzip.compress(SOURCE_BYTES['research/forecast-v2/scripts/audit_fit_coverage.py'],mtime=0))
 return f
with tempfile.TemporaryDirectory(prefix='source-only-and-synthetic-',dir=OUT) as temp:
 base=Path(temp)
 for phase in ['F175','F65','unknown','resigned_numeric_drift','bad_old_snapshot']:
  R=report()
  with pytest.MonkeyPatch.context() as mp:
   f=closed_fixture(R,base/phase,mp);auditor=f.evidence/'scripts/audit_fit_coverage.py';archive=ROOT/'research/forecast-v2/review/comparison_reporting_repair_v1/producer_auditors/F65.py.gz'
   if phase!='F175':auditor.write_bytes(gzip.decompress(archive.read_bytes()))
   if phase=='unknown':auditor.write_bytes(auditor.read_bytes()+b'\n# unreviewed source\n')
   if phase=='bad_old_snapshot':(f.evidence/'source_snapshots'/R.COMPARISON_AUDITOR_SHA256/'audit_fit_coverage.py.gz').write_bytes(gzip.compress(b'corrupted original',mtime=0))
   if phase=='resigned_numeric_drift':
    p=f.root/'forecast/wildfire/meanfield.py';p.write_bytes(p.read_bytes()+b'\n# changed numeric dependency\n');changed=T.source_map(f.root);changed['research/forecast-v2/scripts/audit_fit_coverage.py']=R.COMPARISON_AUDITOR_SHA256
    for p in [*f.receipts,f.aggregate_receipt]:d=json.loads(p.read_text());d['source_sha256']=changed;T.write(p,d)
    T.resign(R,f)
   try:frame,result=R.load_comparison(f.run);accepted=True;error=None
   except (ValueError,FileNotFoundError) as e:accepted=False;error=str(e)
   note('unmodified_canonical61_'+phase,accepted==(phase in ['F175','F65']),error)
   if phase=='F175':
    note('full61_production_anchor_not_patched',len(result['authentication']['producer_source_sha256'])==61 and R.COMPARISON_SOURCE_SHA256=='eb51e5ff3a6e7b871a266b61791f0c2b3ec5efd00c99d0f299b3050fbec62d17')
    joint=result['runtime']['joint24h'];survey=result['runtime']['survey_endpoint'];note('manual_unique_call_costs_not_repeated_horizon_sums',joint['mc_calls']==joint['mf_calls']==12 and survey['mc_calls']==survey['mf_calls']==6 and np.isclose(joint['mc_seconds'],sum(1.2345678901234567+i for i in range(12))) and np.isclose(survey['mc_seconds'],66.) and not np.isclose(joint['mc_seconds'],frame[frame.horizon_kind=='fixed'].mc_seconds.sum()))
 R=report()
 with pytest.MonkeyPatch.context() as mp:
  f=T.fixture_comparison(R,base/'manual_plot',mp);frame,result=R.load_comparison(f.run);support=R.comparison_support(frame)
  kr12=next(x for x in support if x['country']=='KR' and x['hours']==12);kr24=next(x for x in support if x['country']=='KR' and x['hours']==24);us1=next(x for x in support if x['country']=='US' and x['hours']==1)
  note('manual_KR_cutoffs_vs_unique_events_and_null_support',kr12['available_cutoffs']==0 and kr12['declared_cutoffs']==6 and kr12['declared_catalog_events']==3 and kr12['known_support_cutoffs']==3 and kr24['known_support_cutoffs']==0 and us1['available_cutoffs']==us1['declared_catalog_events']==6,support)
  mask=(frame.country=='KR')&(frame.horizon_kind=='fixed')&(frame.hours==1);frame.loc[mask,'rmse_active']=[.01,.02,.03,.04,.05,.06]
  figures=[];original=R.save
  def capture(fig,out,name):figures.append(fig);original(fig,out,name)
  mp.setattr(R,'save',capture);e=R.figure_meanfield(R.style(),frame,OUT/'manual_partial_figure',' [SYNTHETIC]');line=figures[-1].axes[0].lines[0]
  note('manual_plot_fixed_positions_nulls_and_median',list(line.get_xdata())==[1,3,6,12,24] and np.isclose(line.get_ydata()[0],.035) and np.isnan(line.get_ydata()[-2:]).all())
  svg=(OUT/'manual_partial_figure/fig04_meanfield_vs_mc_rmse_by_horizon.svg').read_text();note('plot_scope_disclosures',all(x in svg for x in ['unique catalog events','not CI','not physical flaming','C 0/6','E 0/3 U']))
  frame.loc[:,'rmse_active']=np.nan;frame.loc[:,'active_cells']=0;e=R.figure_meanfield(R.style(),frame,OUT/'manual_all_inactive_figure',' [SYNTHETIC]');note('known_support_separate_from_no_active_plot_availability',result['metric_data_available'] and e['metric_data_available'] is False and e['status']=='GENERATED_WITH_UNAVAILABLE_EVIDENCE')
archive=ROOT/'research/forecast-v2/review/comparison_reporting_repair_v1';manifest=json.loads((archive/'MANIFEST.json').read_text());bad=[]
for rel,pin in manifest['files'].items():
 b=(archive/rel).read_bytes()
 if hashlib.sha256(b).hexdigest()!=pin['sha256']:bad.append(rel)
 if pin.get('encoding')=='gzip' and hashlib.sha256(gzip.decompress(b)).hexdigest()!=pin['original_sha256']:bad.append('decoded:'+rel)
note('preserved_original_and_fixed_evidence_manifest',not bad,dict(files=len(manifest['files']),bad=bad))
before=gzip.decompress((archive/'report_before.py.gz').read_bytes()).decode();after=(ROOT/'research/forecast-v2/scripts/report.py').read_text();old={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(before).body if isinstance(n,ast.FunctionDef)};new={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(after).body if isinstance(n,ast.FunctionDef)};unchanged={k:old[k]==new[k] for k in old if k not in ['main','figure_meanfield']};note('original17_other_function_ASTs_unchanged',len(unchanged)==17 and all(unchanged.values()),unchanged)
result=dict(scope='Bounded source/custody and synthetic metadata/plot controls only; no actual comparison, model, raw prediction/data array or heldout opened. Full real61 source bytes copied without changing production trust-anchor constants; source-only F65 archive used.',review_head='7e59ce24a8d45e8d23b9efedb54bf3fb9a6a9806',checks=checks,passed=sum(x['passed'] for x in checks),total=len(checks),failures=[x for x in checks if not x['passed']]);(OUT/'CLOSURE_PLOT_CONTROLS_7e59.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
