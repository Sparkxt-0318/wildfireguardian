"""Development metadata only. No RESULTS.json or current heldout data is read."""
from pathlib import Path
import ast,csv,hashlib,json,math,statistics
from fractions import Fraction
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
OWN=Path(__file__).resolve().parent
REPO=ROOT/'work/track-1b';E=REPO/'research/forecast-v2'
checks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,label):
 checks.append(dict(check=label,passed=bool(ok)))
 if not ok:raise ValueError(label)
def load(p):return json.loads(p.read_text())
s=load(E/'MODEL_SELECTION.json');split=load(E/'SPLIT.json');parent=load(ROOT/'work/development-scores-parent-v2.json')
pins={str(p.relative_to(ROOT)):sha(p) for p in [E/'MODEL_SELECTION.json',E/'SPLIT.json',E/'scripts/report.py',E/'scripts/audit_fit_coverage.py',E/'ablation.csv',ROOT/'work/final-forecast-result-review/check_results.py',ROOT/'work/final-forecast-result-review/AUTHORIZED_ACTUAL_REVIEW.json',ROOT/'work/development-scores-parent-v2.json',ROOT/'work/audit_development_scores_parent_v2.py']}
need(pins['work/final-forecast-result-review/check_results.py']=='b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8','original checker pinned')
need(pins['work/final-forecast-result-review/AUTHORIZED_ACTUAL_REVIEW.json']=='a2be36da59998020740f458e82df3df8fcdc282ffa11875b65c9f82970fb1fdc','original failure pinned')
need(pins['work/track-1b/research/forecast-v2/scripts/report.py']=='56e7769084481167cc57d2d62510eef37cb4f7657826e9737985b77d9dd7dfc7','frozen producing report source pinned')
need(pins['work/track-1b/research/forecast-v2/scripts/audit_fit_coverage.py']=='65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536','frozen selection arithmetic source pinned')
parent_phases={p['path']:p for p in parent['phases']}
# This CSV contains development scores only. Read exact text conversion, without pandas CSV rounding.
with (E/'ablation.csv').open() as f:
 reader=csv.DictReader(f);need(reader.fieldnames[0]=='','CSV explicit unnamed variant index header');csv_rows={r['']:r for r in reader}
VARIANTS=('base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base')
summary={};phase_pins=[]
for variant in VARIANTS:
 rows=[];selection_scores=[];fold_order=[]
 for fold in ['2020','2021','2022']:
  suffix='_flaming_only' if variant=='burnout_spotting' else '_utc_fixed' if variant=='mixed_base' else ''
  phase=f'{variant}_fold{fold}_seed0{suffix}'
  pointer=s['development_phases'][phase]['result'];path=REPO/pointer['path'];data=load(path)
  need(sha(path)==pointer['sha256']==parent_phases[pointer['path']]['sha256'],'unchanged authenticated development phase '+phase)
  need(data['variant']==variant and str(data['fold'])==fold and set(data['validation_per_fire'])==set(split['development_folds']['folds'][fold]),'frozen variant fold and fire inventory '+phase)
  phase_pins.append(pointer)
  for event in split['development_folds']['folds'][fold]:
   score=data['validation_per_fire'][event]['brier'];need(type(score) in (int,float) and math.isfinite(score) and 0<=score<=1,'development finite score '+phase+'/'+event)
   selection_scores.append(score);fold_order.append(event)
  for event,value in data['validation_per_fire'].items():rows.append(dict(variant=variant,fire=event,sq=value['brier']*value['weight'],w=value['weight']))
 need(len(selection_scores)==23 and len(set(fold_order))==23,'23 exact unique development fires '+variant)
 selection_mean=sum(selection_scores)/len(selection_scores)
 frame=pd.DataFrame(rows);group=frame.groupby(['variant','fire']).agg(sq=('sq','mean'),w=('w','mean')).reset_index().set_index('fire')
 report_mean=float((group.sq/group.w).mean())
 need(selection_mean==s['development_brier'][variant],'exact frozen sum/order selection mean '+variant)
 need(report_mean==float(csv_rows[variant]['mean_fire_brier']),'exact source reconstructed report CSV mean '+variant)
 exact_mean=sum(map(Fraction.from_float,selection_scores))/len(selection_scores)
 exact_source_correctly_rounded=float(exact_mean)
 need(statistics.fmean(selection_scores)==parent['summary'][variant]['mean_fire_brier'],'pre-existing independent parent arithmetic '+variant)
 need(math.isclose(report_mean,selection_mean,rel_tol=2e-10,abs_tol=2e-12),'unchanged pre-existing checker comparison policy '+variant)
 summary[variant]=dict(fires=len(selection_scores),selection_sum_order_mean=selection_mean,report_grouped_weight_roundtrip_mean=report_mean,exact_input_mean_correctly_rounded=exact_source_correctly_rounded,parent_fmean=parent['summary'][variant]['mean_fire_brier'],difference=report_mean-selection_mean,ulp=math.ulp(selection_mean),difference_ulps=(report_mean-selection_mean)/math.ulp(selection_mean),selection_hex=selection_mean.hex(),report_hex=report_mean.hex(),fold_order=fold_order,report_order=list(group.index),paired_effect_csv_fields={k:csv_rows[variant][k] for k in ['difference_vs_base','interval_95','excludes_zero','fires_better_than_base']})
need(len(phase_pins)==21,'all21 authenticated development phases')
need([v for v in VARIANTS if summary[v]['difference']!=0]==['d4_wind'],'only declared d4wind reconstructed difference')
need(summary['d4_wind']['difference_ulps']==-1.,'exact one negative ULP difference')
need(s['selected_variant']==min(VARIANTS,key=lambda v:(s['development_brier'][v],VARIANTS.index(v)))=='d4_wind','unchanged frozen selection rule and winner')
for relative,digest in pins.items():need(sha(ROOT/relative)==digest,'metadata pins unchanged '+relative)
result=dict(status='PASS_SOURCE_EXPLAINED_DEVELOPMENT_ROUNDING_ONLY',checks=len(checks),passed=sum(x['passed'] for x in checks),source_head='691cc162bf2c0295cecc257a558ae0d583f9018e',summary=summary,phase_pins=phase_pins,pins=pins,selected_variant=s['selected_variant'],current_RESULTS_json_read=False,current_heldout_KR_metrics_predictions_or_arrays_accessed=False,comparison_policy=dict(rel_tol=2e-10,abs_tol=2e-12,origin='Unmodified original checker compare(), authored before actual result review'))
(OWN/'DEVELOPMENT_PRECISION_PROOF.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks','passed','selected_variant']},indent=2));print(json.dumps(summary['d4_wind'],indent=2))
