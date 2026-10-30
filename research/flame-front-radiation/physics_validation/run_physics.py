"""Generate optical diagnostics; never turn missing geometry into validation."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"experimental/flame-front-radiation/src"))
from wfg_flamefront.solidflame import finite_panel_view_factor,infinite_wall_view_factor
from wfg_flamefront.intensity import flame_length,flame_geometry

SOURCES={
    "nist":{"url":"https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=860891","status":"PRIMARY_LOCATED","location":"NISTIR 6925, Eq.5, printed p.3","use":"polygon edge-angle projected solid angle"},
    "byram_putnam":{"url":"https://www.fs.usda.gov/psw/publications/weise/psw_1996_weise000.pdf","status":"PRIMARY_LOCATED","location":"Weise and Biging 1996, Eq.3 and Eq.5","use":"Byram length and Putnam tilt as reproduced by the authors"},
    "butler1998":{"url":"https://doi.org/10.1071/WF9980073","status":"PRIMARY_METADATA_ONLY","use":"radiation-only separation model; no claimed experimental reproduction"},
    "morandini2006":{"url":"https://www.pure.ed.ac.uk/ws/files/12097665/morandini_et_al.pdf","status":"PRIMARY_EXCERPTS_RETRIEVED_BY_ORCHESTRATOR_INDEPENDENT_RETRY_TIMEOUT","metadata_url":"https://www.research.ed.ac.uk/en/publications/fire-spread-experiment-across-mediterranean-shrub-influence-of-wi/","access":"Old author-file URL403; alternate manuscript parsed by orchestrator, independent retry timed out","location":"manuscript pp.6,7,12-14","use":"2.5m is shrub height; sensor heights2and4m with horizontal sensing normals; first burn110m2 pointed head; plot30by80m is not instantaneous flame width"},
    "butler2014":{"url":"https://ap1.sib.uc.pt/bitstream/10316.2/34306/1/978-989-26-0884-6_147.pdf","status":"AUTHOR_SYNTHESIS_LOCATED","location":"printed p.1343","use":"explicitly calls 2.5m shrub height, not flame height; quotes Morandini fluxes and notes missing Packham flame dimensions"},
    "packham1971":{"url":"https://www.frames.gov/documents/catalog/spa/butler_cohen_latham_schuette_sopko_shannon_jimenez_bradshaw_2004.pdf","status":"ORIGINAL_NOT_LOCATED_REPORTED_BY_BUTLER","use":"100 near flame and57 at7.6m are historical context with absent geometry"},
    "silvani2009":{"url":"https://doi.org/10.1016/j.firesaf.2008.06.004","status":"PRIMARY_FULL_TEXT_NOT_LOCATED","use":"51 radiative and112 total from prompt/author synthesis are distinct quantities, no numerical fit"},
    "pimont2014":{"url":"https://doi.org/10.13140/RG.2.2.19775.36008","status":"PRIMARY_POSTER_METADATA_ONLY_429","use":"FIRETEC model comparison, requested22-31,8-12,5-8 bands not independently located"},
    "frankman2013":{"url":"https://research.fs.usda.gov/treesearch/42185","status":"PRIMARY_ABSTRACT_LOCATED","use":"in-flame sensor peaks: surface100, shrub132, crown200 and300 kW/m2; not a unique panel emissive power"},
    "butler2004":{"url":"https://www.frames.gov/documents/catalog/spa/butler_cohen_latham_schuette_sopko_shannon_jimenez_bradshaw_2004.pdf","status":"PRIMARY_FULL_TEXT_LOCATED","location":"abstract and conclusions","use":"about200mean and290peak in crown-fire sensors; context only"},
    "cohen2004":{"url":"https://www.frames.gov/documents/catalog/spa/cohen_2004.pdf","status":"PRIMARY_FULL_TEXT_LOCATED","location":"printed pp.1617,1619,1623; Tables2and3","use":"centre-aligned50x20m ideal model, 79/45/27 kW/m2 model values, distinct actual measurements"},
    "hsa":{"url":"https://www.hsa.ie/media/4oap0mec/tlup-guidance-feb-2023-final.pdf","status":"PRIMARY_GUIDANCE_LOCATED","use":"Eisenberg probit with kW/m2 dose units; contextual only"},
}


def write_csv(path,rows):
    with path.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def save(fig,path):
    fig.savefig(str(path)+".png",dpi=300,bbox_inches="tight",facecolor="white")
    fig.savefig(str(path)+".svg",bbox_inches="tight",facecolor="white",metadata={"Date":None})
    svg=Path(str(path)+".svg")
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines())+"\n")
    plt.close(fig)


def run():
    out=Path(__file__).resolve().parent
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"white","svg.hashsalt":"wfg-flamefront-20261030"})
    rows=[];fig,ax=plt.subplots(figsize=(7.2,3.4))
    for intensity,color in zip((1000,5000,20000),("#0072B2","#D55E00","#009E73")):
        h=float(flame_length(intensity));ds=np.geomspace(5,100,80)
        qs=[100*finite_panel_view_factor(20,h,d,receiver="worst_case") for d in ds]
        ax.plot(ds,qs,color=color,label=f"I={intensity:,} kW/m, h={h:.2f} m")
        for d in (5,10,20,50,100):
            rows.append({"case":"declared_straight_front","intensity_kw_m":intensity,"height_m":h,"width_m":20,"distance_m":d,"E_kw_m2":100,"receiver_height_m":0,"flux_kw_m2":100*finite_panel_view_factor(20,h,d,receiver="worst_case"),"wall_facing_base_kw_m2":100*infinite_wall_view_factor(h,d),"comparison":"MODEL_ONLY","reference_kw_m2":"","source":"byram_putnam"})
    ax.set(xlabel="Distance from front (m)",ylabel="Incident radiation (kW/m2)",xscale="log")
    ax.legend(loc="upper left",bbox_to_anchor=(1.01,1),frameon=False)
    save(fig,out/"fig01_flux_vs_distance")
    blackbody=5.670374419e-11*1200**4
    cohen=[]
    for d,reference in ((10,79),(20,45),(30,27)):
        value=blackbody*finite_panel_view_factor(50,20,d,receiver="worst_case",receiver_height_m=10)
        cohen.append({"distance_m":d,"published_model_kw_m2":reference,"this_model_kw_m2":value,"ratio":value/reference,"kind":"MODEL_RELATIVE_APPROXIMATION_NOT_MEASUREMENT"})
        rows.append({"case":"Cohen_ideal_centre_aligned","intensity_kw_m":"","height_m":20,"width_m":50,"distance_m":d,"E_kw_m2":blackbody,"receiver_height_m":10,"flux_kw_m2":value,"wall_facing_base_kw_m2":"","comparison":"MODEL_RELATIVE_APPROXIMATION_NOT_MEASUREMENT","reference_kw_m2":reference,"source":"cohen2004"})
    diagnostics=[]
    for width in (7.2,20,30):
        for d,reported in ((5,7.8),(10,2.2),(15,1.)):
            value=100*finite_panel_view_factor(width,2.5,d,receiver="worst_case")
            diagnostics.append({"assumed_width_m":width,"assumed_height_m":2.5,"distance_m":d,"model_kw_m2":value,"quoted_flux_kw_m2":reported,"ratio":value/reported,"comparison":"INCOMPARABLE_SHRUB_HEIGHT_IS_NOT_FLAME_HEIGHT","source":"butler2014"})
    write_csv(out/"MODEL_TABLE.csv",rows);write_csv(out/"INCOMPARABLE_DIAGNOSTICS.csv",diagnostics)
    base_intensity=5000;length=float(flame_length(base_intensity));base=100*finite_panel_view_factor(20,length,20,receiver="worst_case")
    tornado=[]
    for label,e,height,width,receiver in (("E:50",50,length,20,"worst_case"),("E:200",200,length,20,"worst_case"),("Width:10m",100,length,10,"worst_case"),("Width:40m",100,length,40,"worst_case"),("Receiver:base facing",100,length,20,"vertical_facing(0)"),("Residence:5s (snapshot)",100,length,20,"worst_case"),("Residence:30s (snapshot)",100,length,20,"worst_case")):
        tornado.append({"parameter":label,"flux_kw_m2":e*finite_panel_view_factor(width,height,20,receiver=receiver),"baseline_kw_m2":base,"kind":"DECLARED_PARAMETER_SCENARIO"})
    from wfg_flamefront.solidflame import rectangle_flux
    for speed in (2,5):
        height,_,shift=flame_geometry(length,(speed,0))
        q=rectangle_flux((20,0),(0,-10),(0,10),height,100,tip_shift_xy=shift)
        tornado.append({"parameter":f"Wind:{speed}m/s toward receiver","flux_kw_m2":q,"baseline_kw_m2":base,"kind":"PUTNAM_SCENARIO"})
    write_csv(out/"TORNADO.csv",tornado)
    fig,ax=plt.subplots(figsize=(7.2,3.6));vals=np.array([r["flux_kw_m2"] for r in tornado]);idx=np.arange(len(vals))
    ax.barh(idx,vals-base,left=base,color=["#D55E00" if v>base else "#0072B2" for v in vals]);ax.axvline(base,color="black",lw=.8)
    ax.set(yticks=idx,yticklabels=[r["parameter"] for r in tornado],xlabel="Snapshot radiation at 20 m (kW/m2)")
    save(fig,out/"fig02_parameter_sweep")
    result={"overall_gate":"UNRESOLVED_DO_NOT_RUN_ROUTING","optical_model_checks":"PASS","empirical_factor_three_gate":"UNRESOLVED_INCOMPARABLE_OR_UNLOCATED_INPUTS","cohen_model_rows":cohen,"incomparable_diagnostics_max_ratio":max(d["ratio"] for d in diagnostics),"max_ratio_is_not_a_physical_validation_error":True,"finite_20m_panel_at_80m_base_view_factor":finite_panel_view_factor(20,20,80),"infinite_wall_at_2h_base_view_factor":infinite_wall_view_factor(20,40),"sources":SOURCES,"corrections":["Morandini 2.5m is shrub height, not verified flame height; plot width is not instantaneous front width.","Cohen 2004 has three wall ignitions at10m; only one involved observed flame contact. The prompt's only-contact claim is contradicted.","Cohen's79,45,27 are ideal-model values, not the measured flux table.","In-flame irradiance does not uniquely identify an extended uniform emitting panel's emissive power."]}
    (out/"RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
    (out/"SOURCES.json").write_text(json.dumps(SOURCES,indent=2)+"\n")
    return result


if __name__=="__main__":print(json.dumps(run(),indent=2))
