# Plain-English summary

**Verdict: NEW, PROVED AND FASTER** — with the limits below, which are part of the verdict.

**The idea.** Today the system answers one question per place: "what is the latest second you can leave and still
reach a shelter?" That answer trusts every road-closure time to the second. The new method answers a second
question in the same sweep: "by how many seconds could every closure time be wrong, early or late, before this
departure stops working?" We call that number the margin. One sweep over the road network gives the margin for
every place and every departure second at once.

**What is proved** (`METHOD.md`). The margin the method computes is exactly right, not an estimate. A departure
with margin m has one fixed route that still works however the closure times move within m seconds. If the
forecast is revised and no closure time moves by more than d seconds, no margin drops by more than d, so a
departure with margin at least d stays valid. The margin cannot be read off the existing answer: a place can have
a long unbroken leave window and still have margin zero in the middle of it (figure, panel a).

**What is new and what is not.** Three literature searches (`METHOD.md` §6, `survey_notes/`). Known: the general
fact that such a number can be computed level by level (Bruns and Godefroid, 2004), the kind of quantity itself (a
robustness radius, as in Donzé and Maler 2010 and Rodionova et al. 2022), and every ingredient of the stability
result. Not found anywhere: the one-sweep algorithm on road networks with loops, reopening closures and blocked
waiting (the closest published algorithm, Clement et al. 2020, handles networks without loops), and the two
theorems stated for closure timing. So the contribution is a known kind of quantity made exact and computable for
this problem. Not finding something is not proof that it does not exist.

**Accuracy.** It agreed exactly with the existing code and with a brute-force check on 18,000 random road
networks, including ones where roads reopen, and with the existing code on all six recorded fire hours: about 3.5
billion comparisons, no disagreement. Eight bugs planted on purpose were all caught.

**Speed** (`BENCH.md`, two plans, each frozen before its run; pure Python against the existing pure Python).
* Today's answer only (margin zero): 2 to 6 times faster than the existing sweep on all six recorded hours.
* Several margins: 2 to 6 times faster at two margins, 4 to 16 times at sixteen.
* **The limit.** The single-answer speed comes from engineering shortcuts added in the second round, which the
  existing sweep could also be given. Compared like for like (compiled, same shortcuts), computing margins is 5 to
  12 percent **slower** than computing one answer, and becomes faster from the second margin on (1.6 times at two,
  4 to 7 times at sixteen).
* A compiled version runs a further 4 to 10 times faster, but nothing compiled exists for the existing sweep, so
  that is not a comparison.

**Memory.** Peak is now a little below one existing sweep (0.64 to 0.86 times).

**What it showed about the data.** On the six recorded hours, 1,457 of 1,482 place–shelter leave-by times do not
change when every closure is moved by ten minutes. On this data the margin mostly confirms the existing answers.

**Not done.** Not connected to the planner or the app. Timed on one laptop. Closure times are treated as
uncertain; travel times are not. All closures get the same margin.
