import sys, json, time, csv, urllib.request, urllib.parse, pandas as pd
split = pd.read_csv(sys.argv[1]); inc = pd.read_csv(sys.argv[2]); ics_path = sys.argv[3]; out = sys.argv[4]
fit_held = inc[inc.project_status.isin(['forecast_v2_fit','forecast_v2_heldout'])]
want = pd.concat([split[['Incident_C','irwinid']].assign(group='cohort_'+split.part),
                  fit_held[['Incident_C','irwinid']].assign(group=fit_held.project_status)], ignore_index=True)
want = want.merge(inc[['Incident_C','first_utc','last_utc']], on='Incident_C', how='left')
U = 'https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations/FeatureServer/0/query'
ids = sorted(set(want.irwinid.str.upper()))
rec = {}
for i in range(0, len(ids), 50):
    chunk = ids[i:i+50]
    where = 'IrwinID IN (' + ','.join("'{%s}'" % x for x in chunk) + ')'
    q = urllib.parse.urlencode(dict(where=where, outFields='IrwinID,IncidentName,UniqueFireIdentifier,FireDiscoveryDateTime,InitialLatitude,InitialLongitude,POOState', returnGeometry='true', outSR=4326, f='json'))
    r = json.load(urllib.request.urlopen(urllib.request.Request(U, data=q.encode(), headers={'User-Agent':'wfg-data-fetch/1'}), timeout=120))
    for f in r.get('features', []):
        a = f['attributes']; g = f.get('geometry') or {}
        rec[a['IrwinID'].strip('{}').upper()] = dict(wfigs_name=a['IncidentName'], wfigs_unique_fire_id=a['UniqueFireIdentifier'],
            discovery_utc=pd.to_datetime(a['FireDiscoveryDateTime'], unit='ms', utc=True).isoformat() if a['FireDiscoveryDateTime'] else '',
            initial_lat=a['InitialLatitude'], initial_lon=a['InitialLongitude'],
            poo_lat=g.get('y'), poo_lon=g.get('x'), poo_state=a['POOState'])
    time.sleep(0.5)
w = pd.DataFrame([dict(irwin_upper=k, **v) for k,v in rec.items()])
want['irwin_upper'] = want.irwinid.str.upper()
out_df = want.merge(w, on='irwin_upper', how='left')
# ICS-209-PLUS (1999-2020): match by incident number (Incident_C prefix like CA-SRF-000620) for fallback / cross-check
ics = pd.read_csv(ics_path, low_memory=False, usecols=lambda c: c in ('POO_STATE','INCIDENT_NUMBER','INCIDENT_NAME','DISCOVERY_DATE','POO_LATITUDE','POO_LONGITUDE','START_YEAR'))
ics['key'] = ics.POO_STATE.astype(str).str.upper() + '_' + ics.INCIDENT_NUMBER.astype(str).str.strip().str.zfill(6) + '_' + ics.START_YEAR.astype('Int64').astype(str)
parts = out_df.Incident_C.str.split('_').str[0].str.upper().str.split('-')
out_df['key'] = parts.str[0] + '_' + parts.str[2].str.zfill(6) + '_' + out_df.first_utc.str[:4]
ics = ics[~ics.key.duplicated(keep=False)].rename(columns={'DISCOVERY_DATE':'ics209_discovery_date','POO_LATITUDE':'ics209_poo_lat','POO_LONGITUDE':'ics209_poo_lon','INCIDENT_NAME':'ics209_name'})
out_df = out_df.merge(ics[['key','ics209_name','ics209_discovery_date','ics209_poo_lat','ics209_poo_lon']], on='key', how='left')
cols = ['Incident_C','irwinid','group','first_utc','last_utc','discovery_utc','poo_lat','poo_lon','initial_lat','initial_lon','poo_state','wfigs_name','wfigs_unique_fire_id','ics209_name','ics209_discovery_date','ics209_poo_lat','ics209_poo_lon']
out_df['ics209_vs_wfigs_poo_km']=((out_df.ics209_poo_lat-out_df.poo_lat)**2+((out_df.ics209_poo_lon-out_df.poo_lon)*__import__('numpy').cos(__import__('numpy').radians(out_df.poo_lat)))**2)**0.5*111.2
out_df["ics209_vs_wfigs_poo_km"]=out_df["ics209_vs_wfigs_poo_km"].round(3)
cols.append('ics209_vs_wfigs_poo_km')
out_df[cols].sort_values(['group','Incident_C']).to_csv(out, index=False)
print('rows', len(out_df), 'WFIGS matched', out_df.discovery_utc.notna().sum(), 'with POO lat/lon', out_df.poo_lat.notna().sum(), 'ICS-209 matched', out_df.ics209_discovery_date.notna().sum())
print(out_df.groupby('group').agg(n=('Incident_C','size'), wfigs=('discovery_utc', lambda s: s.notna().sum()), ics=('ics209_discovery_date', lambda s: s.notna().sum())).to_string())
