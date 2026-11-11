# HPWREN access / usage notices (verbatim)

Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego.
Fetched 2026-11-11 by `src/` scripts (copies in `cache/hpwren/`, not committed).

## 1. Data Use and Licensing  -- https://www.hpwren.ucsd.edu/cc.html (linked as "Terms of use" on the cameras page)

> **License.** Archived HPWREN data (more than 24 hours old) is licensed under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. HPWREN data includes camera imagery, the Fire Ignition images Library (FIgLib), and meteorological and other sensor data. It is copyright (c) The Regents of the University of California. For non-commercial purposes, you may copy, redistribute and adapt the data, provided you credit HPWREN as described under Attribution. Non-commercial purposes include research, teaching, and training or evaluating machine-learning models.
>
> **Real-time data.** Real-time data is HPWREN data less than 24 hours old. [...] A license from the UC San Diego Office of Innovation and Commercialization is required to: retrieve real-time data automatically, for example with scripts, scrapers, scheduled downloads of image or data URLs, or stream capture; redistribute or rebroadcast real-time data [...]; use real-time data in a product or service, including running detection or analysis models on live feeds. This requirement applies to commercial and non-commercial users alike. HPWREN may waive it for academic research and teaching [...]
>
> **Publishing results.** Anyone, commercial or non-commercial, may publish results obtained with HPWREN data without prior approval. [...] Publications must credit HPWREN and include this statement: "HPWREN data are not intended to be used as a decision-making tool, or as a replacement for such tools."
>
> **Attribution.** Minimum credit line: "Data courtesy of HPWREN, University of California San Diego (https://www.hpwren.ucsd.edu/)." If you use FIgLib, please also cite: Dewangan, A., et al. (2022). FIgLib & SmokeyNet: Dataset and Deep Learning Model for Real-Time Wildland Fire Smoke Detection. Remote Sensing, 14(4), 1007.
>
> **No warranty.** HPWREN data is provided "as is" as a public service, without support or warranty.

(Full text, including the Commercial Use Permission section: the URL above. Our use is archived data only, non-commercial research.)

## 2. Cameras page notice -- https://www.hpwren.ucsd.edu/cameras/ (JS string in page source)

> Retrospective data is available for 90 days. If you need to access archived data older than 90 days, please contact us.

## 3. Help page -- https://www.hpwren.ucsd.edu/cameras/help.html

> In the Images tab, you can view images from the past 90 days; data older than 90 days is archived in AWS S3 Glacier Deep Archive, so it is not available on the website.
>
> Q: How long are images and videos stored?
> A: Currently, images and videos are stored in AWS S3 Standard for 90 days. After 90 days, images are deleted and the corresponding 3h videos are archived in S3 Glacier. Retrieval from Glacier is done on request and takes about 1 day.
>
> Important: The interface refreshes the images & weather automatically. You should NOT use your own implementation of auto refresh as it adds unnecessary load on our infrastructure.
>
> Due to regulations, we have to round the coordinates of most sites to 2 decimal places. This rounding is now done on the server side when generating the sites.js file that is used on the website. (changelog 9/16/2024; note: the sites.js we fetched has mostly 4-6 decimals, so the rounding claim is not visible in the data we got; verify per site.)

## 4. HPWREN Usage Conditions (network collaborators) -- https://www.hpwren.ucsd.edu/usageconditions.html
Concerns connecting hosts to the HPWREN network; relevant general line: "A host/site connect requester commits to using HPWREN bandwidth efficiently in a non-wasteful way (i.e., taking any reasonable steps to minimize unnecessary bandwidth use)."

## Our conduct
Sequential requests, >= 1.2 s spacing, generic User-Agent `research-poc-camera-arrival/0.1`, every response cached on disk and never refetched, HEAD / tiny ranged GETs where possible, archived (> 24 h old) data only, non-commercial research, credit on every output.
