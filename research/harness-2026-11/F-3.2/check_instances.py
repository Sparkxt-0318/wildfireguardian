"""O2: compare the frontend instance with the independent derivation on the 20 Korean missions."""
import sys,json,time
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import cases, derive_instance as DI
from wfg_scenario_members.contact import ContactModel
from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance
for c in cases.korean_cases():
    g=json.load(open(c['graph']));r=json.load(open(c['request']));m=routable_contact_model(c['packet'])
    t=time.time(); inst,pg=build_instance(g,r,m); d=DI.derive(g,r,m.cell_intervals); diffs=DI.compare(inst,d)
    print(c['mission'], 'EB',len(d['EB']),'WB',len(d['WB']),'diffs',len(diffs),'oog',d['out_of_grid_points'],round(time.time()-t,1), diffs[:2])
