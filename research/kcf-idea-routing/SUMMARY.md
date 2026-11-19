# Plain-English summary

**Verdict: NEW, PROVED AND FASTER** — with the limits below, which are part of the verdict.

**The idea.** Today the system answers one question per place: "what is the latest second you can leave and still
reach a shelter?" That answer trusts every road-closure time to the second. The new method answers a second
question in the same sweep: "by how many seconds could every closure time be wrong, early or late, before this
departure stops working?" We call that number the margin. One sweep over the road network gives the margin for
every place and every departure second at once.

**What is proved** (`METHOD.md`). The margin the method computes is exactly right, not an estimate. A departure
with margin m has one fixed route that still works however the closure times move within m seconds, and no
departure with a smaller margin has that. The margin cannot be read off the existing answer: a place can have a
long unbroken leave window and still have margin zero in the middle of it, because one road closes just as another
opens (figure, panel a).

**What is new and what is not.** We searched before claiming anything (`METHOD.md` §6, `survey_notes/`). The basic
fact that such a number can be computed level by level is a known general theorem (Bruns and Godefroid, 2004), and
the gap between "long window" and "safe window" is a known effect in another field. What we did not find anywhere
is the one-sweep algorithm for road networks with reopening closures and blocked waiting, or the proof that one
route serves every timing error. Not finding something is not proof that it does not exist.

**Accuracy.** It agreed exactly with the existing code and with a brute-force check on 12,000 random road networks,
including ones where roads reopen, and with the existing code on all six recorded fire hours: about 3.5 billion
comparisons, no disagreement. Five bugs planted on purpose were all caught.

**Speed** (`BENCH.md`, plan frozen before running).
* Asked for two or more margins, it is faster than running the existing sweep once per margin on every recorded
  hour: 1.5 to 4.7 times at two margins, 5 to 16 times at sixteen, hundreds of times for every margin from 0 to 600
  seconds.
* Asked for only today's answer (margin zero), it is faster on the three Uiseong–Andong hours (1.7 to 3.2 times)
  and **slower on the three Yeongdeok hours (about 0.6 times)**. It does not replace the existing sweep for that
  job.

**Memory.** About 1.5 to 2 times one existing sweep at peak; about an eighth of keeping sixteen sweeps.

**What it showed about the data.** On the six recorded hours, 1,457 of 1,482 place–shelter leave-by times do not
change when every closure is moved by ten minutes. So on this data the margin mostly confirms the existing answers
rather than changing them.

**Not done.** Not connected to the planner or the app. Not compared with a compiled version of the existing sweep.
Timed on one laptop, in Python. Closure times are treated as uncertain; travel times are not.
