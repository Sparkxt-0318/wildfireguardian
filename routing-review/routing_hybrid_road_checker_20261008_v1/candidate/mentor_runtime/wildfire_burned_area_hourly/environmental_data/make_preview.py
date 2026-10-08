#!/usr/bin/env python3
"""Create a scientific preview from saved, spatially aligned numeric rasters."""
import json
import numpy as np
import pandas as pd
import rasterio
if __package__:
    from .acquire_environment import ROOT
else:  # Compatibility with direct execution of this file.
    from acquire_environment import ROOT

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    events={e['id']:e for e in json.loads((ROOT/'events.json').read_text())}
    ids=['KFS_01','CA-BTU-009205_Dixie']
    fig,axes=plt.subplots(2,4,figsize=(16,7),layout='constrained')
    spec=[('arrival_time_hours.tif','Estimated arrival','hours since t0','magma',None,None),
          ('terrain/slope_degrees_375m.tif','Slope','degrees','terrain',0,45),
          ('vegetation/tree_cover_percent_375m.tif','Tree coverage','percent','Greens',0,100),
          ('weather/wind_gusts_10m_375m.tif','Wind gusts at t0','m/s','viridis',0,None)]
    for row,id in enumerate(ids):
        e=events[id]
        for col,(relative,title,unit,cmap,vmin,vmax) in enumerate(spec):
            path=ROOT/'regions'/id/relative
            with rasterio.open(path) as s:
                band=1
                stamp=''
                if col==3:
                    times=pd.to_datetime(s.descriptions,utc=True)
                    band=int(np.argmin(abs(times-pd.Timestamp(e['t0_utc']))))+1
                    stamp='\n'+str(times[band-1].strftime('%Y-%m-%d %H:%M UTC'))
                a=s.read(band,masked=True)
                b=s.bounds
                extent=[b.left/1000,b.right/1000,b.bottom/1000,b.top/1000]
            ax=axes[row,col]
            im=ax.imshow(a,extent=extent,origin='upper',interpolation='nearest',cmap=cmap,vmin=vmin,vmax=vmax)
            ax.set_title(title+stamp,fontsize=10)
            ax.set_xlabel(f'Easting (km), EPSG:{e["epsg"]}',fontsize=8)
            ax.set_ylabel(f'{e["name"]} {e["year"]}\nNorthing (km)',fontsize=8)
            ax.tick_params(labelsize=8)
            fig.colorbar(im,ax=ax,shrink=.76,label=unit)
    fig.suptitle('375 m grids aligned to the original burned-area rasters\nWeather is resampled from ~9 km model cells; vegetation is a 2019 baseline; arrival is reconstructed.',fontsize=12)
    dest=ROOT/'previews/aligned_data_examples.png'
    dest.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(dest,dpi=160)
    plt.close(fig)
    print(dest)


if __name__ == "__main__":
    main()
