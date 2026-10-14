# Sources

Provenance for every external dataset, parameter and paper. Access date is 2026-10-14 unless stated. Access level: FT = full text read, ABS = abstract or landing page only, SEC = only seen cited in another source, NA = not accessed (cited from general knowledge, to be verified before publication).

## Datasets

| ID | Dataset | Where | License or permission | Use here |
|---|---|---|---|---|
| D1 | Copernicus DEM GLO-30 (DSM), tiles N36 E128 and N36 E129 | https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N36_00_E128_00_DEM/Copernicus_DSM_COG_10_N36_00_E128_00_DEM.tif (and E129); registry https://registry.opendata.aws/copernicus-dem/ ; downloaded 2026-10-14 (48,490,284 and 21,247,924 bytes) | Licence for the use of the Copernicus WorldDEM-30 (free, worldwide, reuse and modification allowed, attribution required): https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf . Required notice for derived products: "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved". The organisations in charge of the Copernicus programme do not incur any liability for any use of the Copernicus WorldDEM-30. | Step 4 and 5 terrain |
| D2 | OpenMRG: Andersson et al. (2022), Gothenburg CML, radar and gauge data, Jun to Aug 2015 | https://doi.org/10.5281/zenodo.7107689 , file https://zenodo.org/records/7107689/files/OpenMRG.zip (317,994,487 bytes, MD5 4e4cdf6ced4d45a084c348f245b8d690) | CC BY-SA 4.0 (dataset); article CC BY 4.0. Derived noise statistics here are shared under the same terms. | Step 6 real dry-weather noise |
| D3 | OpenRainER (Emilia-Romagna, 1 min, 25 GHz, mountainous) | https://doi.org/10.5281/zenodo.10593848 | CC BY 4.0 | Not used yet; candidate for mountain noise |
| D4 | Netherlands four-year CML dataset (15-min min/max) | https://doi.org/10.4121/be252844-b672-471e-8d69-27269a862ec1 | CC BY 4.0 | Not used (22 GB) |
| D5 | pycomlink 0.6.0 (ITU-R P.838-3 coefficients) | https://github.com/pycomlink/pycomlink , PyPI | BSD-3-Clause | Step 7 rain attenuation |

## Papers and reports

| ID | Reference | URL | Access |
|---|---|---|---|
| S1 | Mphale K., Heron M. (2007). Microwave measurement of electron density and collision frequency of a pine fire. J. Phys. D: Appl. Phys. 40(9):2818-2825. doi:10.1088/0022-3727/40/9/023. Same experiment also in Mphale, Jacob, Heron (2007) Int. J. Infrared Millim. Waves 28:251-262, doi:10.1007/s10762-007-9199-7 | https://researchonline.jcu.edu.au/2587/1/17424_Mphale_%26_Heron_2007.pdf ; https://researchonline.jcu.edu.au/2655/1/17300_Mphale_et_al_2007.pdf | FT |
| S2 | Mphale K.M., Luhanga P.V.C., Heron M.L. (2008). Microwave attenuation in forest fuel flames. Combust. Flame 154(4):728-739. doi:10.1016/j.combustflame.2008.07.006 | https://researchonline.jcu.edu.au/6105/1/6105_Mphale_et_al._2008.pdf | FT |
| S3 | Mphale K.M. (2008). Radiowave propagation measurements and prediction in bushfires. PhD thesis, James Cook University. doi:10.25903/wbx1-n038 | https://researchonline.jcu.edu.au/2028/13/JCU_2028_Mphale_2008_thesis.pdf | FT |
| S4 | Mphale K.M., Heron M., Ketlhwaafetse R., Letsholathebe D., Casey R. (2010). Interferometric measurement of ionization in a grassfire. Meteorol. Atmos. Phys. 106:191-203. doi:10.1007/s00703-010-0061-4 | https://researchonline.jcu.edu.au/11792/1/mheron1.pdf | FT |
| S5 | Letsholathebe D., Mphale K.M., Chimidza S., Heron M.L. (2016). Radio wave propagation experiment in sugarcane fire environments. J. Electromagn. Anal. Appl. 8(7):124-131. doi:10.4236/jemaa.2016.87013 | https://file.scirp.org/Html/2-9801672_68770.htm | FT (HTML) |
| S6 | Mphale K., Heron M. (2007). Ray tracing radio waves in wildfire environments. PIER 67:153-172 | https://researchonline.jcu.edu.au/2460/1/2460_Mphale_2007.pdf | FT |
| S7 | Mphale K., Heron M., Verma T. (2007). Effect of wildfire-induced thermal bubble on radio communication. PIER 68:197-228. doi:10.2528/PIER06072202 | https://researchonline.jcu.edu.au/2461/1/2461_Mphale_2007.pdf | FT |
| S8 | Williams D.W. et al. (1970). Operation Euroka: an Australian mass fire experiment. Defence Standards Laboratory Report 386 | cited in S3 | SEC |
| S9 | Gibbins C.J., Chadha R. (1987). Millimetre-wave propagation through a hydrocarbon flame. IEE Proc. H 134(2):169-173. doi:10.1049/ip-h-2.1987.0032 | cited in S3 | SEC |
| S10 | Mphale K., Heron M. (2007). Absorption and transmission power coefficients for millimeter waves in a weakly ionised vegetation fire. Int. J. Infrared Millim. Waves 28:865-879. doi:10.1007/s10762-007-9264-2 | https://researchonline.jcu.edu.au/2654/1/17420_Mphale_%26_Heron_2007.pdf | FT |
| S11 | Hong S.G. et al. (2021). Experimental study of microwave attenuation in a compartment fire. J. Electromagn. Eng. Sci. 21(3):249-251. doi:10.26866/jees.2021.3.l.2 | https://ksp.etri.re.kr/ksp/article/file/64687.pdf | FT |
| S12 | Li Y., Yuan H. et al. (2017). Experimental studies of electromagnetic wave attenuation by flame and smoke in structure fire. Fire Technol. 53(1):5-27. doi:10.1007/s10694-016-0608-0 | https://pure.bit.edu.cn/en/publications/experimental-studies-of-electromagnetic-wave-attenuation-by-flame/ | ABS |
| S13 | Bystrov A. et al. (2021). Experimental evaluation of 79 and 300 GHz radar performance in fire environments. Sensors 21(2):439. doi:10.3390/s21020439 | https://pmc.ncbi.nlm.nih.gov/articles/PMC7827190/ | FT |
| S14 | Wotton B.M. et al. (2012). Flame temperature and residence time of fires in dry eucalypt forest. Int. J. Wildland Fire 21(3):270-281. doi:10.1071/WF10127 | https://connectsci.au/wf/article/21/3/270/127066/ | ABS |
| S15 | Butler B.W., Cohen J.D., Latham D.J. et al. (2004). Measurements of radiant emissive power and temperatures in crown fires. Can. J. For. Res. 34(8):1577-1587. doi:10.1139/x04-060 | https://www.frames.gov/catalog/3641 | ABS |
| S16 | Stocks B.J. et al. (2004). Crown fire behaviour in a northern jack pine-black spruce forest. Can. J. For. Res. 34:1548-1560 | https://sites.ualberta.ca/~flanniga/publications/2004%20Stocks%20et%20al%20CJFR%20-%20Crown%20fire%20behaviour.pdf | FT (first pages) |
| S17 | Byram G.M. (1959) in Davis K.P. (ed.) Forest Fire: Control and Use; Thomas P.H. (1963) The size of flames from natural fires, 9th Symp. Combust. | cited widely | SEC |
| S18 | McCaffrey B.J. (1979). Purely buoyant diffusion flames: some experimental results. NBSIR 79-1910 | https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nbsir79-1910.pdf | FT |
| S19 | Morton B.R., Taylor G.I., Turner J.S. (1956). Turbulent gravitational convection from maintained and instantaneous sources. Proc. R. Soc. A 234:1-23; Yokoi S. (1960) line-source plumes | https://doctorfire.com/pages/Yokoi.pdf | NA (MTT), found not read (Yokoi) |
| S20 | George W.K., Alpert R.L., Tamanini F. (1977). Turbulence measurements in an axisymmetric buoyant plume. Int. J. Heat Mass Transfer 20:1145-1154 | | NA |
| S21 | Hayhurst A.N., Telford N.R. (1974); Butler J.M., Hayhurst A.N. (1996) on flame ion recombination | https://pubs.rsc.org/en/content/articlelanding/1996/ft/ft9969200707 | ABS |
| S22 | ITU-R P.453-14 (2019). The radio refractive index: its formula and refractivity data | https://www.itu.int/rec/R-REC-P.453 | NA |
| S23 | Uiseong fire news and agency reports: Hankyung 2025-03-28 https://www.hankyung.com/article/2025032863827 ; Newsis https://www.newsis.com/view/NISX20250322_0003109003 , https://www.newsis.com/view/NISX20250327_0003116059 , https://www.newsis.com/view/NISX20250323_0003109219 , https://mobile.newsis.com/view/NISX20250328_0003116977 ; Money Today https://www.mt.co.kr/policy/2025/03/27/2025032716355753806 ; weekly.khan https://weekly.khan.co.kr/article/202504171120001 ; kbmaeil https://kbmaeil.com/article/20251106500567 ; Korea JoongAng Daily https://www.koreajoongangdaily.com/korea/telecom-infrastructure-damaged-in-wildfires-almost-wholly-restored-govt-says/12399279 ; newsseoul https://newsseoul.co.kr/news/view/1065583217622576 | as listed | FT (news) |
| S24 | Jeong et al. (2026). Fire 9:439. doi:10.3390/fire9100439; Yi and Lee (2025). Fire 8:363. doi:10.3390/fire8090363 | via doi | ABS |
| S25 | Alexander M.E. (1985). Estimating the length-to-breadth ratio of elliptical forest fire patterns. Proc. 8th Conf. Fire and Forest Meteorology, 287-304 | | NA |
| S26 | Noble I.R., Bary G.A.V., Gill A.M. (1980). McArthur's fire-danger meters expressed as equations. Aust. J. Ecol. 5:201-203 | | NA |
| S27 | Van Wagner C.E. (1977). Conditions for the start and spread of crown fire. Can. J. For. Res. 7:23-34 | | NA |
| S29 | Ervin K.M. et al. (2003). J. Phys. Chem. A 107:8521 (O2 electron affinity 0.448 eV) | | NA |
| S30 | NIST Atomic Spectra Database, K I ionization energy 4.3407 eV | https://physics.nist.gov/asd | NA |
| S31 | Chwala C., Kunstmann H. (2019). Commercial microwave link networks for rainfall observation. WIREs Water 6(2):e1337. doi:10.1002/wat2.1337 | https://publikationen.bibliothek.kit.edu/1000091866/23813107 | FT |
| S32 | Overeem A., Leijnse H., Uijlenhoet R. (2013). Country-wide rainfall maps from cellular communication networks. PNAS 110(8):2741-2745. doi:10.1073/pnas.1217961110 | https://pmc.ncbi.nlm.nih.gov/articles/PMC3581927/ | FT |
| S33 | Graf M., Chwala C., Polz J., Kunstmann H. (2020). Rainfall estimation from a German-wide commercial microwave link network. HESS 24:2931-2950. doi:10.5194/hess-24-2931-2020 | https://hess.copernicus.org/articles/24/2931/2020/ | FT |
| S34 | Andersson R.C., Olsson J., van de Beek R., Hansryd J. (2022). OpenMRG. ESSD 14:5411-5426. doi:10.5194/essd-14-5411-2022 | https://essd.copernicus.org/articles/14/5411/2022/ | FT |
| S35 | Fencl M. et al. (2020). Atmospheric observations with E-band microwave links. AMT 13:6559-6578. doi:10.5194/amt-13-6559-2020 | via doi | ABS |
| S36 | ITU-R P.530 (propagation data for terrestrial line-of-sight systems); 0.6 F1 at k = 4/3 is common planning practice | https://www.itu.int/rec/R-REC-P.530 | NA |
| S37 | Kim M.-S., Kwon B.H. (2018). Rainfall detection and rainfall rate estimation using microwave attenuation. Atmosphere 9(8):287. doi:10.3390/atmos9080287 | via doi | FT |
| S38 | ETSI TR 103 103 V1.1.1 (ATPC description); vendor ATPC material (secondary) | https://www.etsi.org/deliver/etsi_TR/103100_103199/103103/01.01.01_60/tr_103103v010101p.pdf | FT (ETSI), SEC (vendor) |
| S39 | ITU-R P.838-3 (2005). Specific attenuation model for rain | https://www.itu.int/rec/R-REC-P.838 | via pycomlink |
| S40 | Ericsson Microwave Outlook (October 2025), backhaul chapter | https://www.ericsson.com/en/reports-and-papers/microwave-outlook | FT (web) |
| S41 | etnews 2015-03-18 https://www.etnews.com/20150318000008 ; boannews 2022-02-23 https://www.boannews.com/news/articleView.html?idxno=104979 ; Aju News 2024-04-02 https://www.ajunews.com/view/20240402082608686 | as listed | FT (news) |
| S42 | inews24 2020-06-25 https://www.inews24.com/view/1276539 | | FT (news) |
| S43 | ETRI ATSC 3.0 material https://ksp.etri.re.kr/ksp/article/read?id=57607 | | ABS |
| S44 | https://www.ajunews.com/view/20210515090020727 ; https://www.sateconomy.co.kr/news/view/179588703054632 | | FT (news) |
| S45 | fnnews 2026-03-15 https://www.fnnews.com/news/202603142148283714 | | FT (news) |
| S46 | KoreaScience CFKO201133254120849 https://koreascience.kr/article/CFKO201133254120849.pdf | | ABS |
| S47 | Central Radio Management Office https://www.crms.go.kr/ | | Not found |
| S48 | Messer H., Zinevich A., Alpert P. (2006). Environmental monitoring by wireless communication networks. Science 312:713. doi:10.1126/science.1120034 | via doi | ABS |
| S49 | Guyot A. et al. (2021). Wildfire smoke particulate matter concentration measurements using radio links from cellular communication networks. AGU Advances 2:e2020AV000258. doi:10.1029/2020AV000258 | via doi | ABS |
| S50 | Mphale K., Heron M. (2008). Nonintrusive measurement of ionisation in vegetation fire plasma. Eur. Phys. J. Appl. Phys. 41(2):157-164 (peak ne 2.63e16 grass, 1.46e16 bark) | https://www.cambridge.org/core/journals/the-european-physical-journal-applied-physics/article/abs/nonintrusive-measurement-of-ionisation-in-vegetation-fire-plasma/CCBBFBB9C0D455D5C7222AA6306DCB55 | ABS |
