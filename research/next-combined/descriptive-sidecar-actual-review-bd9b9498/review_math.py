"""Independent pooled-diagnostic replay; imports no repository/producer module."""
from dataclasses import dataclass
import numpy as np
from scipy.stats import rankdata

FIELDS = ('pooled_raw_brier','pooled_average_precision','pooled_roc_auc','pooled_ece_10_bins','pooled_clipped_nll')
RAW = ('brier','average_precision','roc_auc','ece_10_bins','clipped_nll')
BINS = np.linspace(0.,1.,11)


def exact_points(y,p):
    """Literal frozen point expressions on original float64 concatenation order.

    Independent code, no producer helper. Exact equality is required for these
    original points; algebraically different grouped resample sums are separate.
    """
    y,p=np.asarray(y,dtype=np.float64),np.asarray(p,dtype=np.float64)
    brier=float(np.mean((p-y)**2))
    if y.sum()==0:ap=None
    else:
        order=np.argsort(-p,kind='mergesort');a,b=y[order],p[order]
        ends=np.r_[np.flatnonzero(np.diff(b)),len(b)-1]
        tp=np.cumsum(a)[ends];fp=(ends+1)-tp
        precision=tp/(tp+fp);recall=tp/a.sum();previous=np.r_[0.,recall[:-1]]
        ap=float(np.sum((recall-previous)*precision))
    pos,neg=y.sum(),len(y)-y.sum()
    auc=None if pos==0 or neg==0 else float((rankdata(p)[y==1].sum()-pos*(pos+1)/2)/(pos*neg))
    index=np.clip(np.digitize(p,BINS[1:-1],right=False),0,9)
    rows=[]
    for b in range(10):
        use=index==b;n=int(use.sum())
        if n:rows.append(n*abs(float(p[use].mean())-float(y[use].mean())))
    ece=sum(rows)/len(y)
    q=np.clip(p,1e-7,1-1e-7)
    loss=float(np.mean(-(y*np.log(q)+(1-y)*np.log1p(-q))))
    return dict(zip(FIELDS,(brier,ap,auc,ece,loss)))


@dataclass
class Plan:
    matrix:np.ndarray
    multiplicities:np.ndarray
    vectors:np.ndarray
    inverse:np.ndarray
    frequencies:np.ndarray


def plan(fires):
    assert fires in (4,6)
    matrix=np.random.default_rng(20261030).integers(0,fires,size=(10000,fires))
    # Deliberately different construction from producer np.add.at.
    multiplicities=np.stack([(matrix==f).sum(axis=1) for f in range(fires)],axis=1)
    vectors,inverse,frequencies=np.unique(multiplicities,axis=0,return_inverse=True,return_counts=True)
    assert np.array_equal(vectors[inverse],multiplicities) and frequencies.sum()==10000
    return Plan(matrix,multiplicities,vectors,inverse,frequencies)


def distributions(labels,predictions,draws):
    assert len(labels)==len(predictions)==draws.matrix.shape[1]
    ys=[np.asarray(y,dtype=np.float64) for y in labels]
    ps=[np.asarray(p,dtype=np.float64) for p in predictions]
    assert all(y.ndim==1 and len(y) and p.shape==y.shape and np.isin(y,[0,1]).all()
               and np.isfinite(p).all() and ((p>=0)&(p<=1)).all() for y,p in zip(ys,ps))
    y,p=np.concatenate(ys),np.concatenate(ps)
    points=exact_points(y,p)
    counts=np.array([len(a) for a in ys],dtype=np.int64)
    positive=np.array([int(a.sum()) for a in ys],dtype=np.int64)
    sse=np.array([np.sum((b-a)**2) for a,b in zip(ys,ps)])
    nll=[];prob_bin=[];truth_bin=[]
    for a,b in zip(ys,ps):
        q=np.clip(b,1e-7,1-1e-7)
        nll.append(np.sum(-(a*np.log(q)+(1-a)*np.log1p(-q))))
        index=np.clip(np.searchsorted(BINS,b,side='right')-1,0,9)
        prob_bin.append([b[index==k].sum() for k in range(10)])
        truth_bin.append([a[index==k].sum() for k in range(10)])
    # Ascending global unique-score inverse and dense per-fire bincounts differ
    # from producer's descending lexsort/sparse score-group-fire run encoding.
    scores,group=np.unique(p,return_inverse=True)
    total_by_fire=[];positive_by_fire=[];start=0
    for a in ys:
        end=start+len(a);g=group[start:end]
        total_by_fire.append(np.bincount(g,minlength=len(scores)))
        positive_by_fire.append(np.bincount(g,weights=a,minlength=len(scores)).astype(np.int64))
        start=end
    totals=np.asarray(total_by_fire,dtype=np.int64);hits=np.asarray(positive_by_fire,dtype=np.int64)
    m=draws.vectors;denom=m@counts
    cached=np.full((len(m),5),np.nan,dtype=np.float64)
    cached[:,0]=(m@sse)/denom
    cached[:,3]=np.abs(m@(np.asarray(prob_bin)-np.asarray(truth_bin))).sum(axis=1)/denom
    cached[:,4]=(m@np.asarray(nll))/denom
    for i,row in enumerate(m):
        n=row@totals;a=row@hits
        positives=int(a.sum());negatives=int(n.sum())-positives
        if not positives:continue
        if not negatives:cached[i,1]=1.;continue
        use=n>0
        suffix_n=np.cumsum(n[::-1])[::-1];suffix_a=np.cumsum(a[::-1])[::-1]
        cached[i,1]=np.sum((a[use]/positives)*(suffix_a[use]/suffix_n[use]))
        negative=n-a;strictly_below=np.cumsum(negative)-negative
        cached[i,2]=np.sum(a.astype(np.float64)*(strictly_below+.5*negative))/(positives*negatives)
    values={name:cached[draws.inverse,i] for i,name in enumerate(FIELDS)}
    no_positive=(draws.multiplicities@positive)==0
    no_negative=(draws.multiplicities@(counts-positive))==0
    return points,values,no_positive,no_negative


def descriptor(values,point,no_positive,no_negative,kind):
    ap=kind in ('ap','paired_ap','auc')
    bad_pos=no_positive if ap else np.zeros(10000,dtype=bool)
    bad_neg=no_negative if kind=='auc' else np.zeros(10000,dtype=bool)
    bad=bad_pos|bad_neg
    assert values.shape==(10000,) and np.array_equal(~np.isfinite(values),bad)
    conditional=np.quantile(values[~bad],[.025,.975],method='linear').tolist() if (~bad).any() else None
    full=conditional if point is not None and not bad.any() else None
    return dict(point=point,percentile_95_interval=full,conditional_on_defined_draws_interval=conditional,
                status='AVAILABLE_FULL_95_INTERVAL' if full is not None else 'UNAVAILABLE_UNDEFINED_POINT_OR_DRAW',
                defined_draws=int((~bad).sum()),undefined_no_positive_draws=int(bad_pos.sum()),
                undefined_no_negative_draws=int(bad_neg.sum()),undefined_union_draws=int(bad.sum()),
                conditional_scope=('conditional on a draw containing both classes' if kind=='auc' else
                    'conditional on a draw containing positive labels' if kind in ('ap','paired_ap') else
                    'all validated nonempty draws'))


def literal_reference(labels,predictions,multiplicity):
    """Predeclared independent validation of actual/tiny weighted tie handling."""
    from sklearn.metrics import average_precision_score,roc_auc_score
    y=np.concatenate([np.tile(a,int(n)) for a,n in zip(labels,multiplicity)])
    p=np.concatenate([np.tile(a,int(n)) for a,n in zip(predictions,multiplicity)])
    expected=exact_points(y,p)
    if y.sum():assert np.isclose(expected['pooled_average_precision'],average_precision_score(y,p),rtol=1e-12,atol=1e-14)
    if 0<y.sum()<len(y):assert np.isclose(expected['pooled_roc_auc'],roc_auc_score(y,p),rtol=1e-12,atol=1e-14)
    return expected
