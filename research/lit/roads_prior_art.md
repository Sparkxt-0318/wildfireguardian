# Roads prior-art note (T1.6)

Owner: A7. Covers H-ROADS: the hypothesis that breach probability across a
Korean linear barrier (forest road, river or ridge) falls with the barrier's
effective width, and that whether a 6 m forest road is by itself sufficient
to hold a front under Korean approach angles, slope directions and lee-side <!-- research-claim-ok: RC-001 -->
fuels is the open question. This is a hypothesis under test, not a result;
see `research/FORBIDDEN_CLAIMS.md`.

To our knowledge (see the novelty caveat at the end of this note), no single
existing study fits a per-segment breach probability model of the form
`1 - (1 - flame crossing) x (1 - ember spotting)` to real Korean fire
perimeters using satellite burn-severity labels on both sides of a barrier.
That specific combination (Korean fires, per-segment breach labels from
dNBR, a two-mechanism breach model) is what this program's roads direction
would add if it is carried out. The rest of this note lays out, piece by
piece, what is already done and where the gaps actually are.

## 1. The NIFoS 6 m claim, exactly as it reads

Source: National Institute of Forest Science (NIFoS) / Korea Forest Service
press release, dated 2025-04-25, titled "국내외 연구 통해 입증된 임도의
산불 대응 효과, 지속적 확충 필요!" (Proven wildfire-response effects of
forest roads through domestic and international research, continuous
expansion necessary). Page:
https://nifos.forest.go.kr/kfsweb/cop/bbs/selectBoardArticle.do?nttId=3207026&bbsId=BBSMSTR_1036&mn=UKFR_03_03_01&orgId=kfri
(confirmed reachable and read directly on 2026-09-16).

The exact sentence, in Korean, as it appears on the page:

> "폭 6m 이상의 임도가 우리나라와 유사한 조건에서 가장 효과적인 방화선
> 기능을 발휘한다고 확인됐다"

In English, staying as close to the original claim shape as the language
allows: forest roads 6 m wide or wider were confirmed to perform the most
effective firebreak function under conditions similar to Korea's.

Two things about that sentence matter for how the program uses it, and both
are why RC-001 in `FORBIDDEN_CLAIMS.md` treats it as prior art to be tested,
not a result to restate or refute:

1. It is a **relative** claim ("가장 효과적", most effective), not an
   absolute sufficiency claim. It does not say a 6 m road stops every fire;
   it says a 6 m road is claimed to be the most effective among whatever set <!-- research-claim-ok: RC-001 -->
   of widths or barrier types the underlying research compared, and that
   claim is what this program tests rather than accepts. H-ROADS, correctly
   stated, tests sufficiency under specific approach angles, slope
   directions and lee-side fuel; that is a narrower and different question
   than "most effective," and the program should not conflate the two.
2. The page's own evidentiary basis is thin from what this agent could
   reach. The main body of the release does not name the underlying studies,
   authors, dates, sample sizes or a quantitative breach rate in the text
   this agent could fetch. The supporting research is pointed to as
   attachment "붙임 2-2" (attachment 2-2), a downloadable file. That file is a
   session-bound download this agent cannot open without accepting terms of
   service or creating an account, both of which are out of scope for A7.
   It is tracked on the taskboard as human gate **WJ-004**. Until that
   attachment is read, the program does not know which studies NIFoS is
   relying on for the 6 m figure, whether any of them used Korean fire data
   directly, or what breach rate (if any) is quoted. **Do not paraphrase this
   claim into something stronger ("6 m roads stop fires") or weaker ("NIFoS
   has no evidence") than what the page itself supports:** the page asserts
   the claim and names an attachment as its source; it does not, in the text
   reachable here, quote a number or a study.

## 2. What is already done, by direction

### 2.1 Barrier width and breach, general fire science (foreign, method only)

- **Wilson 1988** (`wilson1988` in the bibliography), Canadian Journal of
  Forest Research. Field experiments on Australian grassland fires. Found
  that breach probability rises with fireline intensity and with trees
  within 20 m of the firebreak, and falls with firebreak width; flame length
  is proposed as a rough sizing rule for the width needed to stop a fire.
  This is the closest existing work to a width-versus-breach relationship,
  but it is grassland, not the mixed conifer/broadleaf, steep-slope,
  wind-driven crown fire behavior that characterizes the five Korean fires
  this program plans to use. It also predates satellite-based labeling
  entirely; breach was scored by direct observation in a controlled
  experiment, not from a real, uncontrolled wildfire perimeter.
- **Zong et al. 2026** (`zong2026`), Fire Ecology, "Effectiveness of
  firebreaks: a review." A global synthesis of firebreak design, breach
  mechanisms (the review frames these around environmental, structural and
  operational factors: width, placement, maintenance, fuel continuity and
  suppression capacity) and where the literature's gaps are. Notably, the
  review itself flags the same gap this program is trying to fill: it calls
  for "spatially explicit, predictive models" of breach and for
  "standardized, georeferenced databases on firebreak breaches," which is
  close to a direct statement that a rigorous, georeferenced breach dataset
  does not yet broadly exist. This is useful as a framing citation for why
  the roads direction is worth doing, but it is a review, not itself a
  fitted model, and it does not include Korean case material as far as this
  agent could establish from the article text reached.
- **Thompson et al. 2021** (`thompson2021`), Forests, "Forest Roads and
  Operational Wildfire Response Planning." American. This paper is about
  how forest road networks are used in suppression operations planning
  (access, control-line placement, pre-season assessment), not about a
  breach-probability model for a fire front crossing a road. It supports the
  program's framing of why roads matter operationally, but it does not
  overlap the roads hypothesis's actual mechanism.
- **Swedosh et al. 2021** (`swedosh2021`), MODSIM2021 conference paper
  (Australian, Spark simulator). This is the source the roads model plans to
  draw its effective-width formulation from, so its exact numbers matter
  more than the others here. What this agent could confirm from the paper
  and its abstract: the study incorporates directionality (the angle between
  fire approach and a linear firebreak, such as a road that changes bearing
  along its length) into a two-dimensional dynamic fire-spread simulator, so
  that a firebreak is modeled with an "effective width" that depends on the
  angle of attack rather than a single fixed physical width. In the
  validation cases reported, the effective firebreak widths obtained were
  32.6 m and 33.8 m, run from a circular ignition over a 1.5 hour
  simulation, with fuel load 25 t/ha and FFDI (Forest Fire Danger Index) 80,
  giving a peak head-fire intensity of 31 MW/m. **Caveat for whoever builds
  the roads model from this (A3/A6): this agent read the paper's abstract
  and the search-indexed summary of its methods and validation-case numbers,
  not the full PDF page by page for every equation. Before hard-coding an
  effective-width formula from this source, confirm the exact functional
  form (how effective width is computed from physical width and approach
  angle) against the PDF at
  mssanz.org.au/modsim2021/papers/G3/swedosh.pdf directly.** This agent
  flags that as an open risk rather than asserting the formula is fully
  captured here.

### 2.2 Korean-specific work found (T1.8 sweep)

None of the following directly answers the roads breach-probability
question, and that is the headline finding for this section (see the
prominent flag at the top of this note and in the round-1 report): **no
Korean paper found this round already builds a per-segment breach
probability model of Korean forest roads from satellite burn-severity
labels.**

- **Kwon, Zoh and Kang 2025** (`kwon2025`), Journal of Mountain Science,
  "Identifying road-related factors in wildfire risk management: The case of
  South Korea." Korean data: a qualitative and quantitative database of 225
  Korean wildfires (2013 to 2022, each 2.5 ha or larger). Cross-tabulation
  found wider roads have a mitigating association with wildfire occurrence.
  This is occurrence (does a fire start/get reported nearby), not spread
  breach (does an active fire front cross this road segment). It is the
  closest Korean paper found to the roads question, but it answers a
  different, correlational question at a coarser unit than a ~100 m barrier
  segment, and it does not use satellite dNBR labeling of fire spread either
  side of a road.
- **Kim and Im 2024** (`kim2024`), Korean Society of Forest Engineering
  (한국산림공학회) 2024 autumn conference, one-page abstract. FDS (Fire
  Dynamics Simulator) modeling of the 2022 Yeongdeok fire site, comparing
  four scenarios (SC1: road width and terrain as built; SC2: roadside fuel
  density cut 50% both sides; SC3: road widened and fill-slope trees
  removed, fuel cut 25%; SC4: reduced crown height/width). The fire was
  blocked only in SC3, where the road was both widened and the fill-slope
  trees were removed. This is real, useful, Korean, physically-modeled prior
  art directly on point for the roads mechanism, but it is a single fire
  site, a one-page conference abstract (not a full paper this agent could
  verify beyond the abstract, see UNVERIFIED.md), a physics simulation
  rather than an empirical breach dataset, and it studies one road's
  cross-section design rather than fitting a general breach-probability
  curve across many barrier segments and fires. It is complementary to, not
  a substitute for, the planned roads model: it explains a plausible
  mechanism (canopy fuel on the fill slope carrying the fire across a road
  that would otherwise be wide enough) that the empirical model should be
  able to pick up if lee-side fuel is included as a covariate.
- **Kang et al. 2004** (`kang2004`), Journal of Korean Society of Forest
  Science, historical review of firebreak (방화선) and fire-resistant forest
  belt (내화수림대) construction in Korea from the Joseon Dynasty through the
  Japanese colonial period. Historical and policy background only; no
  quantitative breach data.
- A wind-tunnel study on surface-fire firebreak width (지표화 방화선 구축
  폭 평가, Korean Society of Fire Science and Engineering conference
  proceedings, found via DBpia search) tests firebreak widths at the scale
  of tens of centimeters against pine-needle surface fuel in a wind tunnel.
  Different scale and fuel type from a forest road crossed by a crown fire;
  noted for completeness but not added to the bibliography since this agent
  did not pin down full authorship and a DOI within this round's time
  budget, and it is not load-bearing for the differentiation argument.
- A targeted search for Korean satellite (Sentinel-2 dNBR) studies of
  forest-road or firebreak breach specifically (as opposed to general
  burn-severity mapping, which is a well developed Korean literature, see
  e.g. work on Sentinel-2-based Fire Burn Index and dNBR classification for
  Korean fires) returned no match. Korean dNBR work exists in volume; none
  of it found this round is framed around roads as the unit of analysis.

### 2.3 Roads as a double-edged factor (context, foreign)

- **Aplet, Hartger and Dietz 2026** (`aplet2026`), Fire Ecology,
  "Three-decade record of contiguous-U.S. national forest wildfires
  indicates increased density of ignitions near roads." American, 30 years
  of U.S. national forest data. Finds ignition density is higher near roads,
  consistent with roads as human-access points rather than as firebreaks.
  Worth carrying into the roads direction's writeup as a caution: roads can
  simultaneously raise local ignition risk and, once a fire exists, act as a
  barrier or a suppression corridor. The Korean Kwon et al. 2025 paper above
  found a similar mitigating-with-distance pattern for occurrence near
  roads in Korea specifically, so this is not purely a U.S. artifact, but
  neither paper measures the fire-front-breach question H-ROADS is about.

### 2.4 Landslide-direction background carried by this note (not scored as roads)

- **Sidle 1992** (`sidle1992`), Water Resources Research. See section 3 and
  `landslides_prior_art.md`; recorded here only because it shares a
  bibliography with the roads work, not because it answers H-ROADS.

## 3. What this program would do differently, if it goes ahead

This section is written for A3 and A6 to use directly when they write the
pre-registration and judge whether the direction still clears a novelty bar.
Each point below states precisely how far existing work goes and where it
stops.

1. **Country and fires.** None of the width/breach literature found (Wilson
   1988, Zong et al. 2026, Swedosh et al. 2021) uses Korean fire data. The
   two Korean-specific pieces found (Kwon et al. 2025, Kim and Im 2024) use
   Korean data but do not fit a breach-probability curve across multiple
   real fires. Fitting on the five named Korean fires (Goseong 2019, Uljin
   2022, Gangneung 2023, Uiseong 2025, Sancheong 2025) together would be new
   relative to everything found this round.
2. **Unit of analysis.** Wilson 1988 and Swedosh et al. 2021 model breach at
   the level of a whole firebreak or a controlled experimental strip; Kwon
   et al. 2025 models occurrence at distance bands around roads (250 m,
   500 m, ... to 2 km); Kim and Im 2024 models one road cross-section in one
   simulated fire. None of them scores breach at ~100 m barrier segments
   across a real fire perimeter. That segment-level unit is what the planned
   model would add.
3. **Label source.** None of the pieces found uses paired Sentinel-2 dNBR
   (before/after burn severity) on both sides of a barrier, combined with
   satellite fire-detection timing, to label a segment as breached or held.
   Kim and Im 2024's labels come from a physics simulation, not from an
   observed real fire's satellite trace.
4. **Two-mechanism decomposition.** The planned
   `1 - (1 - flame crossing) x (1 - ember spotting)` form separates direct
   flame-front crossing from ember spotting as two multiplicatively combined
   failure modes. Zong et al. 2026's review discusses both mechanisms
   qualitatively as drivers of breach, and Wilson 1988's breach probability
   already folds in both without separating them; this agent found no
   existing model that fits the two mechanisms as separate, combined terms
   for Korean or foreign road/firebreak data.
5. **Effective width under approach angle.** Swedosh et al. 2021 is exactly
   this idea already (see 2.1) for an Australian simulator; reusing that
   equation form on Korean topography and fire data would be an application
   of an existing method, not a new method. That should be represented as
   such in the pre-registration, not claimed as new.
6. **Where an existing study already covers part of the question, stated
   plainly for A3/A6:**
   - If the question is "do wider Korean roads correlate with fewer nearby
     fires," Kwon et al. 2025 already answers a version of that, at a
     coarser (event-occurrence, distance-band) resolution, and the roads
     direction should cite it rather than treat that sub-question as open.
   - If the question is "can a widened road plus fill-slope fuel removal
     stop a real Korean crown fire," Kim and Im 2024's single-site FDS study
     already shows one physical mechanism (SC3) under which it can, for one
     fire, in simulation. The planned empirical model should be checked for
     consistency with that mechanism (does lee-side/fill-slope fuel show up
     as a significant covariate) rather than treated as a fully open
     question.
   - The specific pre-registered question, breach probability as a function
     of effective width and mechanism, fit on five real Korean fires with
     satellite-derived labels, was not found answered anywhere in this
     round's search. That is the part of H-ROADS this agent did not find
     covered.

## 4. Open risks for A3/A6

- **Attachment 2-2 (WJ-004) is still unread.** Until it is, the program does
  not actually know what NIFoS's own evidentiary basis is for the 6 m claim,
  including whether it draws on Korean fire data, foreign data, or a
  modeling study. That is a real gap in understanding the claim under test,
  not just a nice-to-have.
- **Swedosh et al. 2021's exact effective-width formula should be confirmed
  against the source PDF** before being hard-coded into the model (see 2.1).
- **Kim and Im 2024 is one fire, one simulation, one page.** It should not be
  treated as validating or refuting the general roads hypothesis either way;
  it is a useful mechanism hint and nothing more at this round's evidence
  level.
- **The Korean-language sweep (T1.8) was not exhaustive.** KCI, DBpia and
  ScienceON were searched by keyword through general web search rather than
  through each database's native advanced-search interface (this agent has
  no login credentials and was instructed not to create accounts). A
  follow-up sweep using each database's own search tooling, if access can be
  arranged without violating the no-accounts rule, would be worth doing
  before the roads pre-registration is finalized.

## 5. Novelty caveat (RC-009)

The statements above about what is or is not already covered are, to this
agent's knowledge, accurate as of this search round (2026-09-16), and this
agent is not aware of prior work that fully answers the pre-registered roads
question as specified in section 3. That not-aware-of status is itself an
unverified claim: it reflects the limits of what a web search and the
databases reachable without an account could surface in one round, not an
exhaustive systematic review. This hedge is deliberate and should not be <!-- research-claim-ok: RC-009 -->
read as a bare claim that no prior work exists in the unqualified sense
RC-009 forbids; A6 should treat the differentiation section above as a
starting point for its own check, not as a closed case.
