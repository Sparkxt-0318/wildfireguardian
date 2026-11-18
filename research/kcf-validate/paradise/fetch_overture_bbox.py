# Adapted from research/kcf-roadcut/overture/fetch_overture_theme.py: bbox is argv[3] = lon0,lon1,lat0,lat1 (Overture release 2026-10-21.0).
import sys, os, time, json, pyarrow.fs as pafs, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
u=urlparse(os.environ['HTTPS_PROXY'])
po={'scheme':'http','host':u.hostname,'port':u.port}
if u.username: po.update(username=u.username,password=u.password)
fs=pafs.S3FileSystem(anonymous=True, region='us-west-2', proxy_options=po, tls_ca_file_path='/root/.ccr/ca-bundle.crt')
import sys
REL='overturemaps-us-west-2/release/2026-10-21.0/'+sys.argv[1]+'/'
X0,X1,Y0,Y1=[float(v) for v in sys.argv[3].split(',')]  # lon0,lon1,lat0,lat1
sel=[s.path for s in fs.get_file_info(pafs.FileSelector(REL))]
def stats(path):
    f=pq.ParquetFile(path, filesystem=fs); md=f.metadata; names=[md.schema.column(i).path for i in range(md.num_columns)]
    ix={n:names.index(n) for n in ('bbox.xmin','bbox.xmax','bbox.ymin','bbox.ymax')}
    keep=[]
    for g in range(md.num_row_groups):
        rg=md.row_group(g); s={k:rg.column(i).statistics for k,i in ix.items()}
        if s['bbox.xmin'].min<X1 and s['bbox.xmax'].max>X0 and s['bbox.ymin'].min<Y1 and s['bbox.ymax'].max>Y0: keep.append(g)
    return path, keep
t=time.time()
with ThreadPoolExecutor(16) as ex: res=list(ex.map(stats, sel))
res=[r for r in res if r[1]]; print('files',len(res),'rgs',sum(len(k) for _,k in res), time.time()-t, flush=True)
tabs=[]
for path,keep in res:
    f=pq.ParquetFile(path, filesystem=fs)
    tb=f.read_row_groups(keep, columns=None)
    b=tb.column('bbox')
    m=pc.and_(pc.and_(pc.less(pc.struct_field(b,'xmin'),X1),pc.greater(pc.struct_field(b,'xmax'),X0)),pc.and_(pc.less(pc.struct_field(b,'ymin'),Y1),pc.greater(pc.struct_field(b,'ymax'),Y0)))
    tb=tb.filter(m); tabs.append(tb); print(path[-40:], tb.num_rows, time.time()-t, flush=True)
pq.write_table(pa.concat_tables(tabs),sys.argv[2])
print('done', time.time()-t)
