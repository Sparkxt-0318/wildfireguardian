# Korean non-weather covariates for the other 13 KFS events (EPSG:5179)

This covers KFS_01, 04, 05, 06, 07, 09, 11, 12, 13, 14, 15, 16 and 17. It completes the 15 Korean events in `forecast/data/environment/events.json`; KFS_02 and KFS_03 are in `../kr_smoke/` (pinned, unchanged). The method is the same as kr_smoke: the repo's own `forecast/wildfire` from Main `8d50f2e2`, run with the pinned venv. `environment inventory` was followed by `terrain` (rc=0), `landcover` (rc=0, Copernicus Global Land Cover, NASIA) and `python -m wildfire biome` (rc=0, "BIOMES VALIDATED 15 fires"). No Open-Meteo calls were made.

`kr_check_all.py ENV_ROOT` checks every raster's shape, transform and EPSG against events.json. It prints, per layer, valid cells / short sha, the biome classes, and the arrival-valid cells without a biome value. The grid matches events.json for all 15 events.

| Event | Grid | Slope / elev. valid | Tree valid | Biome valid (class) | Arrival-valid | Arrival-valid without biome |
|---|---|---|---|---|---|---|
| KFS_01 | 79×237 | 18723 | 18406 | 18470 (4) | 10955 | 0 |
| KFS_04 | 29×27 | 783 | 783 | 783 (4) | 355 | 0 |
| KFS_05 | 18×18 | 324 | 322 | 277 (4) | 153 | **6** (coastal sea, masked) |
| KFS_06 | 14×14 | 196 | 196 | 196 (4) | 78 | 0 |
| KFS_07 | 12×14 | 168 | 168 | 168 (4) | 70 | 0 |
| KFS_09 | 15×11 | 165 | 165 | 165 (4) | 57 | 0 |
| KFS_11 | 17×11 | 187 | 187 | 187 (4) | 80 | 0 |
| KFS_12 | 8×12 | 96 | 96 | 96 (4) | 51 | 0 |
| KFS_13 | 7×9 | 63 | 63 | 63 (4) | 27 | 0 |
| KFS_14 | 5×8 | 40 | 40 | 40 (4) | 19 | 0 |
| KFS_15 | 9×7 | 63 | 63 | 63 (4) | 25 | 0 |
| KFS_16 | 5×6 | 30 | 30 | 30 (4) | 9 | 0 |
| KFS_17 | 8×4 | 32 | 32 | 32 (4) | 14 | 0 |

Across all 15 Korean events, the arrival-valid cells without a biome value are KFS_02 10 (in kr_smoke) and KFS_05 6. All others have 0. In a c651 refit on rebuilt covariates these cells are environment-filter rejections.

## Data root for the full-catalog c651_fullvalid_rebuilt run

`prepare.py` reads every entry of events.json, using one rng across all events in order. The rebuilt run therefore uses ONE data root that holds all 44 events (29 US + 15 KR):

    <root>/data/environment/events.json      = forecast/data/environment/events.json from Main 8d50f2e2,
                                               sha256 607f831ea64235449d7eb19e5cd931099486aaae44de1221c1ec27b34965ac8b (44 events, unmodified)
    <root>/data/environment/biome_classes.json  (written by `wildfire biome` over all 44)
    <root>/data/environment/regions/<id>/{arrival_time_hours.tif, kriging_std_hours.tif, grid.json,
                                          terrain/, vegetation/, biome/, weather/}       for every one of the 44 ids
    <root>/data/sources/zenodo_21788344/extracted/   (Choi archive, rasters_us/ and rasters_kr/)

The US events add fuel/ and fuel_moisture/ (LANDFIRE, gridMET), which the stages skip for KR. Weather is the slim Open-Meteo ECMWF-IFS rebuild (temperature_2m, wind_eastward_10m, wind_northward_10m). The pins manifest comes from `data-fetch/make_input_manifest.py`.

## sha256

```
5c78ae6bc1ff0940c7d282fb4f48bf1dcfccea32667b04c48d1321379e1ad1eb  KFS_01/biome_class_375m.tif
d8cefbcf605e33a21061cee9d3e1393f4c5170159e09725d1132a1679f5d8773  KFS_01/elevation_m_375m.tif
eb1ce499b21e3f3b8ade825d8f650a775ad464481a669a37b09875cc949de5c5  KFS_01/slope_degrees_375m.tif
093974c5149ab43607eb68a87dc69fadec398e63f175161ad3c6921e02f3a84b  KFS_01/tree_cover_percent_375m.tif
077f530ba4f1813ec6ed700d08baf3742c4c3ffdb1a23014f20e2378b370f29c  KFS_04/biome_class_375m.tif
6ae657a58cb6e200f67e8690d51497a837b16922204b50ecd50be9811f48457a  KFS_04/elevation_m_375m.tif
a7030cb1eba78d992e09d6ffe09f45be81e2097047f640ee38993c49bdd193a3  KFS_04/slope_degrees_375m.tif
e8ebfa35d677ae9b57e14cc8caf50849d9540253b7a490638cc4a035cfb95e28  KFS_04/tree_cover_percent_375m.tif
d756be3fa9116011ccf20d34f60056ac6f848467e27f8d465ffd1cbbab1509d3  KFS_05/biome_class_375m.tif
ebdac5cbc46295e5d1d9a2e8a4fcaab6028844aec7990ccff31127c9745b1dc7  KFS_05/elevation_m_375m.tif
d8793ce97af422c76bd40045fd61dabe57ce25069255895c9872f35999a03cbb  KFS_05/slope_degrees_375m.tif
7bcf9cd4c22916b24ca8e557d35a468fcf4e9b32e331be6395faed5a9d2e0603  KFS_05/tree_cover_percent_375m.tif
06da83e4f28f6983bd318cad2dc25d7917ec5afa3ff1a7fd5cd35c07fa0a14ca  KFS_06/biome_class_375m.tif
6cedbe1d5dd4b260db27b6b537fe326b54ca681602c4a73075aeae5a0ea6834d  KFS_06/elevation_m_375m.tif
5e474690dc0d59569ca2077807c005d7410c4b116aa76ad53bb7baa7282df85b  KFS_06/slope_degrees_375m.tif
d50c360b1d80f0d95fd8ae39a6ef67ac5a7f0cf0318ad52157b58bbf11eabc51  KFS_06/tree_cover_percent_375m.tif
fd4ccaf1c5755e331dd438d4670c367421a401578adc45b7e3da81ae44fd49ac  KFS_07/biome_class_375m.tif
b1bd2ce5344ae6fcb5851a7e2f4f5c8b04c32a57d70a5462b2192c72dd772625  KFS_07/elevation_m_375m.tif
ecdb718aca65b18288aca30c8c9c8d6da29f08c5bc41cd0e73c63330e223f270  KFS_07/slope_degrees_375m.tif
5eecb96d46927f2efcbff3956e2b166b016053520c560da31943b2a859437af5  KFS_07/tree_cover_percent_375m.tif
82c6f6a40927c175f7023c72d9087fad5297e4f46f1d520ab6847fa7edaf3b20  KFS_09/biome_class_375m.tif
50665240a4fd6363f266639ce69d969553c78ec15e0452c50a81172456d1b6df  KFS_09/elevation_m_375m.tif
0120f7e2678390d5a47974c6b54bb5ceeb9d15a399f53520eac90cecd5a42880  KFS_09/slope_degrees_375m.tif
058967e4906410fb263dc0c23271729d6f8f139b3ebea002d1ac492db6b3eeb6  KFS_09/tree_cover_percent_375m.tif
7cd72aa40fe4195ad6064a91bc8c8a28034ed19074aff109ee65201cdb1c592f  KFS_11/biome_class_375m.tif
0249d075ed490d2202782ed43199dc10a6197db7a4b904e45aa274795d0b87e2  KFS_11/elevation_m_375m.tif
7b093d98cb4161b7469a2b3693b792aaae104be313f8b177b417df225febf831  KFS_11/slope_degrees_375m.tif
302a35a97163b6db714c82be0c5a138d93a6b84faeeb1e1c821e56d59744a8e4  KFS_11/tree_cover_percent_375m.tif
557294d0fdee42abac866d1406e835ce44e3373d20c5a0abb6ae571cbc56cbc8  KFS_12/biome_class_375m.tif
8ea8095202097c1a889fe675adfde62300db4b91c0aa34c32d93bd758a9fd220  KFS_12/elevation_m_375m.tif
89be807d43eda7c8b757232778d169282e20bcb8e8fdd17cd6e0086305cf678f  KFS_12/slope_degrees_375m.tif
0dc440799be5769fd40056b261f978a62319580b11f6f2bab959912af52b2f67  KFS_12/tree_cover_percent_375m.tif
f911f1f6111761e98e1e690b451318f0d7d0db769f7f7fe0ce0be84d4f873d5f  KFS_13/biome_class_375m.tif
924bf93ed12f2da724e5bed599d79411ac58aeed0eab3fcb20e0d049f8aa4d0b  KFS_13/elevation_m_375m.tif
c0f1c7573412e5de2410c4a1ad888be3f3f40033007d9114e85d90cb7b690fe1  KFS_13/slope_degrees_375m.tif
80d3890ee9220d75710fd5bb5962d35ad4ca58b5a56078fedfe3bd3a389d409a  KFS_13/tree_cover_percent_375m.tif
03151406c3af81a539d33d8eeee485938101f980f46598899f13a914ced5fdc1  KFS_14/biome_class_375m.tif
fd78609fc2fbe058b6fa36ce027c54a2ea5a56062f44084a3cb243ab8047a3ce  KFS_14/elevation_m_375m.tif
b37116bed55afe7ccb247bc1149cac7abdc5bb573154adefb89fecb04f392e71  KFS_14/slope_degrees_375m.tif
77e46f08e31443ae78bbbcd26b730d12d083d3ce8c6ac4554f8fb72bb140c829  KFS_14/tree_cover_percent_375m.tif
ca97f9a334de01138cbe31cd016a3ed6c74f07cf75bed9e8958656daf38009e7  KFS_15/biome_class_375m.tif
27903a9a4d5db17a3fc0308871453f70ed22ca4018e37317d967d592a13c6b0a  KFS_15/elevation_m_375m.tif
f969f8613c05502d65f1b4d0f70901d1efcfab67d4965fd7dd4d26c29876616a  KFS_15/slope_degrees_375m.tif
9eaac7cba7ef26d58594212b6eeffa14b7de6d248f62302f2423f19d9bfedff2  KFS_15/tree_cover_percent_375m.tif
6b5bb6bf9b60f9fff580dbb302126708ee8fe26ebf0a04687dc94e7c8bdc10a8  KFS_16/biome_class_375m.tif
85cb54083c1cd77b1f27e2d558c3e3d2f94a2506477e726109232e40a4726e24  KFS_16/elevation_m_375m.tif
d76a1659ff84a0f2571535f3de52e85e0eade65835da55e8fbac5f6414fc68b5  KFS_16/slope_degrees_375m.tif
8aa75860a88af6e9245519cf8aefdb2a8826f0dbe37a72145eff6fe1b341b4e3  KFS_16/tree_cover_percent_375m.tif
4f812039054a78499ba0449830678d2306020e8abd26994f22d35ffad9e540d6  KFS_17/biome_class_375m.tif
140c09046404a1c953d07fc911c848e3027200293a66e670fdabffd313e3f82b  KFS_17/elevation_m_375m.tif
2bc5e05fbfbb72b8100491b5deb021bead62ee647c67225333aa4f39a0a1a350  KFS_17/slope_degrees_375m.tif
3640e3eea225d7edd402def4cb8d96e3fb0cef2ef58348fcbcf720bdf26d6466  KFS_17/tree_cover_percent_375m.tif
```
