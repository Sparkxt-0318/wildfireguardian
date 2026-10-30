"""Read fixed development aggregates only; no model or prediction execution."""
import hashlib,json,math,platform,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root/'track-1b'
protocol=json.loads((repo/'research/forecast-v2/RUN_PROTOCOL.json').read_text())
base=repo/'forecast/runs/20261030_perimeter_trained/execution_v3/folds'
records=[]; summaries={}
for variant in protocol['variants']:
 per_fire={}
 for fold in protocol['development_folds']:
  suffix='_flaming_only' if variant=='burnout_spotting' else ''
  p=base/f'{variant}_fold{fold}_seed0{suffix}'/'result.json'
  raw=p.read_bytes();r=json.loads(raw)
  assert r['variant']==variant and str(r['fold'])==fold and r['seed']==0
  assert set(r['validation_events'])==set(r['validation_per_fire'])
  assert not(set(r['train_events']) & set(r['validation_events']))
  for fire,v in r['validation_per_fire'].items():
   assert fire not in per_fire
   assert math.isfinite(v['brier']) and v['weight']>0
   per_fire[fire]=v
  records.append({'path':str(p.relative_to(repo)),'sha256':hashlib.sha256(raw).hexdigest(),'fires':len(r['validation_per_fire']),'fold':fold,'variant':variant})
 assert len(per_fire)==23
 summaries[variant]={'mean_fire_brier':statistics.fmean(v['brier'] for v in per_fire.values()),'pooled_own_support_brier':sum(v['brier']*v['weight'] for v in per_fire.values())/sum(v['weight'] for v in per_fire.values()),'fires':len(per_fire),'own_support_weight':sum(v['weight'] for v in per_fire.values())}
assert len(records)==21
order=list(protocol['variants'])
winner=min(order,key=lambda v:(summaries[v]['mean_fire_brier'],order.index(v)))
assert winner=='d4_wind'
assert math.isclose(summaries[winner]['mean_fire_brier'],0.037495116098823784,rel_tol=0,abs_tol=1e-15)
result={'scope':'Independent arithmetic of saved development aggregate scores only; does not replace phase source/cache admission or establish a common-cell contrast','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'host':platform.platform(),'phases':records,'summary':summaries,'rule':protocol['primary_selection'],'selected_variant':winner,'status':'PASS_21_PHASE_DEVELOPMENT_ARITHMETIC','actual_study_arrays_checkpoints_predictions_or_heldout_accessed':False,'paired_common_cell_effects_identified':False,'final_registry_frozen':False}
(root/'development-scores-parent.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],winner,summaries[winner], 'phases',len(records))
