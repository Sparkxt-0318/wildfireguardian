"""Synthetic argv evidence; extracts only the pinned argparse declarations."""
from pathlib import Path
import argparse,ast,contextlib,copy,gzip,hashlib,importlib.util,io,json,sys,tempfile
import pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b';OUT=TASK/'work/mfmc-report-guard-independent-review/v2'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'forecast'))
from forecast.tests import test_report_comparison as T
pipeline=(ROOT/'research/forecast-v2/scripts/pipeline.py').read_text();tree=ast.parse(pipeline);main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');body=[]
for n in main.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='args' for t in n.targets):
  n=copy.deepcopy(n);n.value.args=[ast.Name(id='argv',ctx=ast.Load())];body.append(n);break
 body.append(copy.deepcopy(n))
fn=ast.FunctionDef(name='parse_only',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='argv')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body+[ast.Return(value=ast.Name(id='args',ctx=ast.Load()))],decorator_list=[])
code=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));ns=dict(argparse=argparse,Path=Path,VARIANTS={x:None for x in ['base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base']});exec(compile(code,'<pinned-parser-only>','exec'),ns)
def report():
 s=importlib.util.spec_from_file_location('report_matrix',ROOT/'research/forecast-v2/scripts/report.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def canonical(f,index):
 return ['synthetic-python',str(f.evidence/'scripts/pipeline.py'),'compare','--data-root',str(f.root/'NO_ENV_READ'),'--perimeters',str(f.root/'NO_PERIM_READ'),'--work',str(f.root/'NO_CACHE_READ'),'--run',str(f.run),'--data-manifest-sha256','d'*64,'--epochs','3','--seed','0','--hidden','16','--lr','.003','--samples-per-step','1','--max-fit-intervals-per-fire','3','--intervals-per-epoch','0','--threads','2','--n-samples','1024','--balance','--compare-case-index',str(index),'--artifact-suffix','_a06']
changes={'canonical':lambda c:c,'seed_equals7':lambda c:c+['--seed=7'],'seed_abbrev7':lambda c:c+['--se=7'],'N_equals7':lambda c:c+['--n-samples=7'],'N_abbrev7':lambda c:c+['--n-s=7'],'case_equals1':lambda c:c+['--compare-case-index=1'],'case_abbrev1':lambda c:c+['--compare-case-i=1'],'suffix_equals_a07':lambda c:c+['--artifact-suffix=_a07'],'suffix_abbrev_a07':lambda c:c+['--artifact-s=_a07'],'manifest_equals_changed':lambda c:c+['--data-manifest-sha256='+'f'*64],'threads_equals1':lambda c:c+['--threads=1'],'duplicate_separate7_then0':lambda c:c+['--seed','7','--seed','0'],'duplicate_separate0_then7':lambda c:c+['--seed','0','--seed','7'],'mixed_separate7_equals0':lambda c:c+['--seed','7','--seed=0'],'mixed_equals7_separate0':lambda c:c+['--seed=7','--seed','0'],'equals7_then0':lambda c:c+['--seed=7','--seed=0'],'separator_then_seed':lambda c:c+['--','--seed=7'],'unknown_extra':lambda c:c+['--not-a-pinned-option'],'extra_positional':lambda c:c+['fold'],'wrong_dispatch':lambda c:c[:2]+['fold']+c[3:],'run_override':lambda c:c+['--run','OTHER_OUTPUT'],'events_override':lambda c:c+['--events','KFS_02']}
rows=[]
with tempfile.TemporaryDirectory(prefix='synthetic-command-matrix-',dir=OUT) as temp:
 for name,change in changes.items():
  R=report()
  with pytest.MonkeyPatch.context() as mp:
   f=T.fixture_comparison(R,Path(temp)/name,mp)
   for i,path in enumerate(f.receipts):d=json.loads(path.read_text());d['command']=canonical(f,i);T.write(path,d)
   mp.setattr(R,'COMPARISON_COMMAND_SHA256',hashlib.sha256(json.dumps(canonical(f,0),separators=(',',':'),ensure_ascii=True).encode()).hexdigest())
   anchor_before=R.COMPARISON_COMMAND_SHA256
   p=f.receipts[0];d=json.loads(p.read_text());d['command']=change(d['command']);T.write(p,d);T.resign(R,f)
   argv=d['command'];parse_error=None;effective=None
   try:
    with contextlib.redirect_stderr(io.StringIO()):a=ns['parse_only'](argv[2:])
    effective={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items() if k in ['command','seed','n_samples','compare_case_index','artifact_suffix','data_manifest_sha256','threads','run','events']}
   except SystemExit as e:parse_error='ARGPARSE_EXIT_'+str(e.code)
   error=None
   try:_,out=R.load_comparison(f.run);accepted=out['execution_complete']
   except (ValueError,FileNotFoundError) as e:accepted=False;error=str(e)
   rows.append(dict(fixture_anchor_before_mutation=anchor_before,fixture_anchor_unchanged=R.COMPARISON_COMMAND_SHA256==anchor_before,control_pass=accepted==(name=='canonical') and R.COMPARISON_COMMAND_SHA256==anchor_before,case=name,argparse_effective=effective,argparse_error=parse_error,report_loader_accepted=accepted,report_loader_refusal=error))
result=dict(scope='Synthetic file/receipt fixtures only; exact AST-extracted parser declarations without pipeline dispatch or numerical imports. Loader uses owner synthetic custody fixture catalog; full real61 closure tested separately.',report_sha256=hashlib.sha256((ROOT/'research/forecast-v2/scripts/report.py').read_bytes()).hexdigest(),pipeline_sha256=hashlib.sha256(pipeline.encode()).hexdigest(),cases=rows)
result['passed']=sum(x['control_pass'] for x in rows);result['total']=len(rows);result['failures']=[x for x in rows if not x['control_pass']]
(OUT/'COMMAND_MATRIX_27506618.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

raise SystemExit(bool(result['failures']))
