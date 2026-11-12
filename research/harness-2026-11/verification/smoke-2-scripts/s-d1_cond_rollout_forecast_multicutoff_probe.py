import sys,numpy as np,torch
sys.path.insert(0,'tests'); sys.path.insert(0,'.')
from test_cond_rollout import simulate, simulate_with_conditional, new_burn_probability
class EnvStub(torch.nn.Module):
    channel_names=("x",)
    def __init__(s,K): super().__init__(); s.K=torch.tensor(K)
    def forward(s,states,environment,*,channel_names,burned_area_valid,feature_valid,dt_hours,boundary):
        # rate scaled by environment channel (forecast varies per hour) and masked by feature_valid
        scale=(1+environment[:, :1]).clamp_min(0)*feature_valid[:, :1]
        return new_burn_probability(states, s.K.expand(states.shape[0],-1,-1,-1)*scale, dt_hours=dt_hours,
                                    burned_area_valid=burned_area_valid, boundary=boundary)
rng=np.random.default_rng(5); bad=0
for trial in range(4):
    C,H,W,T=3,20,21,5
    K=rng.uniform(0,0.25,size=(25,H,W)); K[12]=0
    b=torch.zeros((C,H,W),dtype=torch.float64)
    for c in range(C): b[c,rng.integers(2,H-2),rng.integers(2,W-2)]=1
    bv=torch.ones((C,H,W),dtype=torch.bool); 
    env=torch.tensor(rng.normal(0,.3,(C,1,H,W)))
    fv=torch.ones_like(env,dtype=torch.bool)
    fc=torch.tensor(rng.normal(0,.5,(T,C,1,H,W))); fcv=torch.ones((T,C,1,H,W),dtype=torch.bool)
    kw=dict(channel_names=("x",),burned_area_valid=bv,feature_valid=fv,hours=[1.,3.,5.],n_samples=203,seed=trial,trajectory_batch_size=64,boundary=["zero","unknown"][trial%2])
    for use_fc in (False,True):
        extra=dict(environmental_forecast=fc,forecast_valid=fcv) if use_fc else {}
        try:
            r=simulate(EnvStub(K),b,env,**kw,**extra); m=simulate_with_conditional(EnvStub(K),b,env,**kw,**extra)
        except Exception as e: print("trial",trial,"fc",use_fc,"EXC",type(e).__name__,str(e)[:120]); continue
        for x,y in zip(r,m):
            ok=torch.equal(x["details"].valid,y["valid"]) and torch.equal(torch.nan_to_num(x["details"].probability,nan=-1.),torch.nan_to_num(y["probability"],nan=-1.))
            bad+= not ok
        print("trial",trial,"forecast",use_fc,"identical",all(torch.equal(torch.nan_to_num(x["details"].probability,nan=-1.),torch.nan_to_num(y["probability"],nan=-1.)) for x,y in zip(r,m)), "valid frac per h",[round(float(o["valid"].float().mean()),3) for o in m], "p>0 cells",int((m[-1]["probability"]>0).sum()), "cond>0",int((m[-1]["conditional"]>0).sum()))
print("BAD",bad)
