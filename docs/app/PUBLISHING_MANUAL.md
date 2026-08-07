# 산불지킴이 / WildfireGuardian — Publishing Manual

> **From this repository to a live product: the web, the Apple App Store, and
> Google Play — written for someone who has never programmed and never shipped
> an app.**
>
> Companion documents: [`ARCHITECTURE.md`](./ARCHITECTURE.md) (what the app
> *is* — the binding technical spec) and [`AD_CAMPAIGN.md`](./AD_CAMPAIGN.md)
> (how to market it). This document is only about getting it **live**.

---

## §0. How to read this manual

### 0.1 The rules of this document

1. **Do the sections in order.** Later sections assume earlier ones are done.
   The one exception: start §2.4 (Apple D-U-N-S, if you enroll as an
   organization) and §8.6 (Google Play closed testing) **early**, because they
   have multi-week waiting periods that run in the background.
2. **One action per numbered step.** If a step says "click Save", click Save
   and nothing else, then read the ✅ checkpoint under it. If what you see
   doesn't match the checkpoint, stop and check the Troubleshooting FAQ (§11.3)
   before continuing. Nothing in this manual breaks anything permanently
   except two things, both flagged loudly: **losing your Android keystore
   passwords** (§8.3) and **deleting a live Stripe webhook secret** (§5.6).
3. **Grey boxes of text starting with `$` or containing code are commands.**
   You copy the whole line (not the `$` if shown), paste it into your
   terminal (defined below), and press Enter. Every command in this manual is
   copy-pasteable as written.
4. **Money and policy facts go stale.** Every fee, limit, and store rule in
   this manual was verified in **August 2026** and is marked
   *(as of Aug 2026)*. Before you pay anyone or promise anyone anything,
   glance at the linked source to make sure the number is still true.
5. **Time budget:** an evening for the web version (§3–§4), roughly 1–2 weeks
   of elapsed time for the Apple App Store (§7), and 3–5 weeks of elapsed
   time for Google Play (§8) — most of that is waiting, not working. Full
   tables in §11.

### 0.2 Things you need before step 1

- A computer. **For the web + Android: Windows, Mac, or Linux all work. For
  iOS you will eventually need a Mac** (§7.1 explains why and the
  alternatives).
- A credit/debit card that works for international payments (Apple and Google
  fees).
- A phone (any) for testing, ideally one iPhone and one Android.
- An email address you check daily. Store review teams write to it.
- Patience with waiting rooms: identity verification, D-U-N-S, and app review
  are queues run by other people.

### 0.3 Using the terminal (the one genuinely new skill)

The *terminal* (Mac: "Terminal" app; Windows: "PowerShell"; Linux: any
terminal) is a window where you type commands instead of clicking. You need
about five commands total in this manual, and every one is given to you
verbatim. Three habits:

1. Press Enter to run a command; wait until a new prompt line appears before
   typing the next one.
2. `cd some/folder` means "go into that folder" — like double-clicking a
   folder, but typed.
3. If a command fails, the error text is the clue. Copy the *last* few lines
   of it into a web search or into an AI assistant; that is what professional
   developers do too.

### 0.4 Glossary — every term this manual uses

Read this once now, skim it again whenever a word looks alien. Terms appear
roughly in the order you'll meet them.

| Term | Plain meaning |
|---|---|
| **repository (repo)** | The folder containing all the app's code, with its change history. This project's repo is `wildfireguardian`. |
| **Git / GitHub** | Git tracks changes to code; GitHub (github.com) is the website where the repo is stored online so hosting services can fetch it. |
| **frontend** | The part of the app users see and touch — screens, buttons, the map. Lives in `app/frontend/`. |
| **backend** | The invisible server program that fetches fire data, decides the danger level, and answers the frontend's questions. Lives in `app/backend/`. Also called the *gateway* or *server*. |
| **API** | The fixed set of questions the frontend may ask the backend and the exact shape of the answers (e.g. `GET /v1/situation` → a JSON danger report). Defined in `ARCHITECTURE.md` §5. |
| **JSON** | The text format APIs speak: `{"level": "SAFE"}`. You never write it by hand in this manual. |
| **build** | Turning human-written source code into the optimized files that actually run. Frontend build command: `npm run build`. Also used as a noun: "upload the build". |
| **deploy** | Putting a build onto a server on the internet so the world can reach it. |
| **cloud host** | A company (Render, Netlify…) that runs your code on their computers so you don't run a server at home. |
| **environment variable (env var)** | A named setting (e.g. `WFG_FIRMS_MAP_KEY`) given to the backend *outside* the code, so secrets never live in the repo. Set in the host's dashboard. |
| **domain / DNS** | `wildfireguardian.example` is a domain — a name you rent (~US$10–15/yr) that points at your servers. DNS is the phone book that does the pointing. |
| **HTTPS / TLS certificate** | The padlock in the browser: traffic is encrypted. Hosts in this manual issue the certificate automatically and free. Stores **require** HTTPS. |
| **PWA (Progressive Web App)** | A website that a phone can "install" so it gets an icon and works like an app — no app store involved. The frontend is already a PWA. |
| **Capacitor** | The tool that wraps the PWA into a *real* iOS/Android app that stores accept. Already configured in `app/frontend/capacitor.config.ts`. |
| **bundle ID / application ID** | The app's permanent unique name in reverse-domain form. Ours is **`kr.wildfireguardian.app`** (set in `capacitor.config.ts`). It can never change after release — treat it as carved in stone. |
| **IPA** | The packaged iOS app file you upload to Apple (you'll rarely see the file itself; Xcode uploads it for you). |
| **AAB (Android App Bundle)** | The packaged Android app file you upload to Google Play. (An **APK** is the older format — still used by Samsung Galaxy Store and ONE store.) |
| **certificate / signing** | A cryptographic identity proving *you* built the app. Apple manages it via Xcode; Android uses a **keystore** file you must never lose (§8.3). |
| **provisioning profile** | Apple-side glue tying your certificate + bundle ID + devices together. Xcode's "Automatically manage signing" handles it; you just need to know the name when an error mentions it. |
| **App Store Connect** | Apple's website where you create the store listing, upload builds, and talk to the review team. |
| **Play Console** | Google's equivalent website. |
| **TestFlight** | Apple's beta-testing app: testers install pre-release builds through it. |
| **webhook** | A URL on *your* backend that another service (Stripe) calls to report events ("payment succeeded"). Ours is `/v1/billing/webhook`. |
| **Stripe** | The payment company that handles cards for the web version's Guardian Plus subscription. **Test mode** uses fake cards; **live mode** moves real money. |
| **IAP (in-app purchase)** | Buying digital things *inside* an iOS/Android app through Apple/Google's own payment system. The stores have strict rules about when you must use it — the whole of §6. |
| **D-U-N-S number** | A free nine-digit company ID issued by Dun & Bradstreet; Apple and Google require it to open an *organization* developer account. |
| **SSE (server-sent events)** | The technique the backend uses to push live danger updates to the app (`/v1/alerts/stream`). Matters only in one FAQ entry (§11.3, Q13). |
| **demo mode / live mode** | The backend's two personalities: `demo` replays a clearly-labelled synthetic scenario; `live` shows real NASA satellite fire detections. See §1.2. |
| **NASA FIRMS** | NASA's free public feed of satellite-detected fires worldwide. Live mode reads it using a free "MAP_KEY" (§3.7). |
| **review (store review)** | A human at Apple/Google using your app before allowing it into the store. Takes hours to days; can reject with a reason you then fix. |

---

## §1. What you are shipping (plain-words architecture recap)

Everything here is a summary; [`ARCHITECTURE.md`](./ARCHITECTURE.md) is the
authoritative version.

### 1.1 The three deliverables

```
 Resident's phone                         The internet
┌───────────────────────┐    HTTPS    ┌──────────────────────────────┐
│ ① Web app (PWA)       │───────────▶ │ ③ Backend "gateway"          │
│    in any browser     │             │    on a cloud host (§3)      │
│                       │             │    - reads NASA FIRMS fires  │
│ ② The SAME app,       │───────────▶ │    - computes danger level   │
│    wrapped by         │             │    - picks guidance cards    │
│    Capacitor, in the  │             │    - talks to Stripe         │
│    App Store /        │             └──────────────┬───────────────┘
│    Google Play        │                            │
└───────────────────────┘                    NASA FIRMS,  Stripe
```

- **③ Backend** (`app/backend/`, Python/FastAPI): one small server program.
  Every phone asks it "what's my situation at lat/lon?" and it answers with a
  danger level (`SAFE 안전` / `WATCH 주의` / `GO 대피`), an ordered handful of
  guidance cards, an evacuation route, and shelter info — all strings in both
  Korean and English. You deploy it once (§3); web and store apps all share it.
- **① Frontend** (`app/frontend/`, a PWA): the elderly-first interface — huge
  type, one big button, three colors, read-aloud on every card. Deployed as a
  plain website (§4); installable to the home screen with no store.
- **② Store apps**: the *same* frontend wrapped by Capacitor into a genuine
  iOS app (§7) and Android app (§8), pointed at the same backend.

### 1.2 Demo mode vs live mode — the honesty switch

| | `demo` (default) | `live` |
|---|---|---|
| Fire data | Bundled **synthetic** Yeongdeok-area scenario, replayed on a loop | Real NASA FIRMS satellite detections |
| Spread prediction | Precomputed slices from the scenario file | Honestly reported as unavailable (`"prediction_available": false`) unless a prediction file is configured |
| How you get it | Deploy with no keys set | Set `WFG_FIRMS_MAP_KEY` (§3.7) |
| What users see | A permanent **연습 모드 / DEMO** banner | Live data, still with the supplement-not-replacement disclaimer |

Two honesty rules you must never undo, because they are both ethics and store
survival (§6):

1. **The DEMO banner stays** whenever synthetic data is shown. Presenting the
   demo scenario as a real fire would be dangerous and is grounds for store
   rejection and removal.
2. **All life-safety features are free** — danger status, map, spread,
   evacuation routes, alerts. The paid tier ("Guardian Plus", via Stripe)
   covers convenience only: family circle notifications, SMS/phone-call
   delivery, offline map packs, multiple addresses. (`ARCHITECTURE.md` §1.)

Also permanent: the app **supplements, never replaces,** official emergency
channels (재난문자 alerts and 119). That disclaimer ships in every API
response and must ship in every store listing (§7.8, §10.5). No research
metrics (AUC etc.) ever appear in resident-facing text or store listings.

### 1.3 What "going live" means, concretely

By the end of this manual you will have:

1. The backend running at `https://api.your-domain` with `/v1/health`
   answering `{"ok": true, ...}` (§3).
2. The web app at `https://your-domain`, installable as a PWA (§4).
3. Stripe live subscriptions purchasable **on the web** (§5), arranged so the
   store builds stay compliant (§6).
4. The iOS app in the App Store (§7) and the Android app on Google Play (§8),
   both free to download, both showing the same live (or demo) data.
5. Optionally, listings on Samsung Galaxy Store and ONE store (§9).
6. A privacy policy, terms, and the emergency disclaimer published (§10).

---

## §2. Accounts you need (and what they cost)

### 2.1 The full account list

Costs verified August 2026. "When" tells you the earliest section that needs
the account — create each one just-in-time except the two flagged **START
EARLY**.

| # | Account | Cost (as of Aug 2026) | Needed for | When |
|---|---|---|---|---|
| 1 | **GitHub** — [github.com](https://github.com) | Free | Hosting the code so cloud hosts can deploy it | §3.2 |
| 2 | **Render** — [render.com](https://render.com) | Free tier; recommended paid instance **US$7/mo** (§3.1) | Running the backend | §3.3 |
| 3 | **Netlify** — [netlify.com](https://netlify.com) | Free tier (commercial use allowed) | Hosting the web app | §4.1 |
| 4 | **Domain registrar** (e.g. Namecheap, Cloudflare, or Korean registrars like Gabia 가비아) | ~US$10–15/yr for `.com`; `.kr` similar | Your own address, e.g. `wildfireguardian.app` | §3.6 |
| 5 | **NASA FIRMS MAP_KEY** — [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | Free | Live fire data | §3.7 |
| 6 | **Stripe** — [stripe.com](https://stripe.com) | Free account; per-transaction fees only (no monthly fee). **Not available to businesses based in South Korea — read §2.5.** | Guardian Plus payments on the web | §5 |
| 7 | **Apple Developer Program** — [developer.apple.com](https://developer.apple.com/programs/) | **US$99/year** (billed in local currency where available; fee waivers exist for nonprofits/edu/government publishing free apps) | App Store + TestFlight | §7 — **START EARLY if enrolling as an organization (D-U-N-S, §2.4)** |
| 8 | **Google Play Console** — [play.google.com/console](https://play.google.com/console/signup) | **US$25 one-time** | Google Play | §8 — **START EARLY (personal accounts must run a 14-day closed test, §2.3/§8.6)** |
| 9 | **Samsung Galaxy Store Seller Portal** — [seller.samsungapps.com](https://seller.samsungapps.com) | Free | Optional Korean reach (§9) | §9.1 |
| 10 | **ONE store Developer Center** — [dev.onestore.net](https://dev.onestore.net) | Free | Optional Korean reach (§9) | §9.2 |

Sources for the fee facts: [Apple Developer Program membership](https://developer.apple.com/programs/whats-included/) and [fee waivers](https://developer.apple.com/help/account/membership/fee-waivers/); [Play Console signup](https://support.google.com/googleplay/android-developer/answer/6112435); [Galaxy Store "no sign-up nor annual fee"](https://developer.samsung.com/galaxy-store/faq.html); [Render pricing](https://render.com/pricing); [Stripe global availability](https://stripe.com/global).

### 2.2 Individual vs organization accounts — the decision that shapes everything

Both Apple and Google offer two account types. Decide once, up front:

| | Individual / personal | Organization |
|---|---|---|
| Who can use it | Any adult with government ID | A registered legal entity (회사/법인 or sole proprietorship with registration, depending on country) |
| Seller name shown in store | **Your personal legal name**, publicly | Company name |
| Apple extra requirement | None beyond ID | **D-U-N-S number** (§2.4) + legal entity status + authority to sign for the company |
| Google extra requirement | **Closed-test gate**: 12 testers × 14 days before you may publish (§2.3) | **D-U-N-S number** required for organization accounts (as of Aug 2026); no 12-tester gate |
| Time to open | Hours–days | Days–weeks (D-U-N-S can take up to 30 business days) |
| Later features | Fine for everything in this manual | Required if you ever want multiple team members with proper roles, or to hide your home identity |

**Recommendation for a first launch:** if you have no registered business,
enroll as an **individual** on both stores and accept the two trade-offs
(your name is public; Google's 14-day test gate). If you have — or are
willing to register — a legal entity, the organization route looks more
professional and avoids Google's tester gate, at the price of the D-U-N-S
wait. You *can* transfer apps between accounts later on both stores, but it
is paperwork you'd rather avoid.

### 2.3 Google's closed-testing gate for personal accounts *(as of Aug 2026)*

Verified against [Google's official help page](https://support.google.com/googleplay/android-developer/answer/14151465):

- Applies to **personal** Play Console accounts created after Nov 13, 2023.
- Before your app may go to production you must run a **closed test with at
  least 12 testers who stay opted-in for 14 consecutive days**. Interrupted
  days don't count.
- Afterwards you click **Apply for production**, answer questions about your
  test, and wait for a review that "usually takes 7 days or less."

Plan for it: recruit 12+ friends/family with Android phones *now* (a family
group chat is enough), and start §8.6 as soon as you have any working Android
build — the 14-day clock only runs while testers are opted in.

### 2.4 D-U-N-S numbers (organizations only)

A D-U-N-S number is a free nine-digit business identifier from Dun &
Bradstreet. Apple requires it for organization enrollment ([Apple's D-U-N-S
page](https://developer.apple.com/help/account/membership/D-U-N-S/)), and
Google requires it for organization Play Console accounts
([Google's account-type page](https://support.google.com/googleplay/android-developer/answer/13634885)) *(both as of Aug 2026)*.

1. Go to Apple's [D-U-N-S lookup tool](https://developer.apple.com/enroll/duns-lookup/)
   and search for your legal entity. Many registered companies already have a
   number without knowing it.
   - ✅ *What you should see:* either your company (Apple emails you the
     number) or "no match", with an option to submit your details to D&B.
2. If no match: submit the form. It is **free**; delivery takes roughly
   **5–30 business days** (D&B sells paid expediting, ~8 business days — you
   do not need it if you started early).
3. When the number arrives by email, keep it with your company records; you
   will type it into both Apple's and Google's enrollment forms.

⚠️ The company name and address you give Apple/Google must match the D&B
record **exactly** — mismatches are the #1 cause of enrollment delays.

### 2.5 The Stripe-in-Korea problem (read before promising anyone revenue)

*(As of Aug 2026)* Stripe's [supported-countries list](https://stripe.com/global)
does **not** include South Korea — you cannot activate a Stripe live account
with a Korean business entity or Korean bank account. Japan, Singapore, and
Hong Kong are supported. Your options, honestly:

1. **You (or a cofounder) have an entity/bank in a supported country** (US,
   Japan, Singapore, most of Europe…): proceed with §5 exactly as written.
2. **Korea-only, want revenue now:** keep the codebase's Stripe integration
   for later, and in the meantime either (a) use a merchant-of-record service
   that supports Korean sellers (e.g. Paddle or Lemon Squeezy — they become
   the seller and handle taxes; this needs a small backend change and is out
   of scope for this manual), or (b) integrate a Korean payment gateway
   (Toss Payments, PortOne) — a real development task.
3. **Simplest and perfectly respectable:** launch with **everything free**
   (billing endpoints already answer `billing_not_configured` when no keys
   are set) and add payments later. Nothing else in this manual depends on
   Stripe being live.

---
## §3. Deploy the backend (Render)

**Goal:** the gateway running at a public HTTPS address, answering
`/v1/health`.

### 3.1 Why Render, and what it costs

We recommend [Render](https://render.com) because it deploys a Python app
straight from GitHub with zero server administration, issues HTTPS
certificates automatically, and has a genuinely free tier to start.
*(As of Aug 2026:)*

- **Free instance:** enough for demo mode and testing, **but** it spins down
  after ~15 minutes with no traffic; the next visitor waits 30–60 seconds
  while it wakes. It also has **no persistent disk** — the SQLite database
  (`guardian.db`, which stores subscriptions and family circles) is erased on
  every restart.
- **Starter instance (US$7/mo):** always-on, no cold starts, and lets you
  attach a **persistent disk (US$0.25/GB/mo — 1 GB is plenty)** so
  `guardian.db` survives restarts.

**Rule of thumb: free tier until §5; the moment you take real money you need
Starter + a 1 GB disk**, otherwise paid subscriptions vanish on restart.
(Alternative hosts — Fly.io, Railway — are fine too, but this manual gives
exact clicks for Render only.)

### 3.2 Put the code on GitHub

If the repository is already on GitHub (this project's orchestrator normally
pushes it), skip to §3.3. Otherwise:

1. Create a free account at [github.com](https://github.com) → **Sign up**.
2. Click **+** (top right) → **New repository** → name `wildfireguardian` →
   **Private** → **Create repository**.
3. Follow GitHub's "push an existing repository" instructions shown on the
   next screen from a terminal opened in the project folder:

   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/wildfireguardian.git
   git push -u origin main
   ```

   ✅ *What you should see:* refresh the GitHub page — folders `app/`,
   `docs/`, `src/` etc. are listed.

### 3.3 Create the Render web service

1. Go to [render.com](https://render.com) → **Get Started** → sign up **with
   GitHub** (this links the two accounts in one step; authorize access to the
   `wildfireguardian` repo when asked).
2. In the Render dashboard click **New +** → **Web Service**.
3. Select the `wildfireguardian` repository → **Connect**.
4. Fill the form with exactly this:

   | Field | Value |
   |---|---|
   | Name | `wildfireguardian-api` |
   | Region | **Singapore** (closest to Korea) |
   | Branch | `main` |
   | Root Directory | `app/backend` |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn guardian_app.main:app --host 0.0.0.0 --port $PORT` |
   | Instance Type | Free (for now — see §3.1) |

5. Don't add environment variables yet (that's §3.5). Click
   **Create Web Service**.
   - ✅ *What you should see:* a build log scrolling. After 1–3 minutes, a
     green **Live** badge and a URL like
     `https://wildfireguardian-api.onrender.com`.

### 3.4 Health check — prove it's alive

1. Open `https://wildfireguardian-api.onrender.com/v1/health` (your URL) in a
   browser.
   - ✅ *What you should see:*
     `{"ok": true, "mode": "demo", "time_utc": "..."}` — `"mode": "demo"` is
     correct at this stage: no keys are set, so the backend honestly serves
     the labelled synthetic scenario.
2. In Render: **Settings → Health Check Path** → enter `/v1/health` → Save.
   Render will now auto-restart the service if it ever stops answering.
3. Try the main endpoint too:
   `https://wildfireguardian-api.onrender.com/v1/situation?lat=36.44&lon=129.45`
   - ✅ *What you should see:* a JSON block containing `"danger"`, `"cards"`,
     Korean and English strings, and `"mode": "demo"`.

### 3.5 Environment variables (the backend's settings panel)

In Render: your service → **Environment** → **Add Environment Variable**. The
complete set, from `ARCHITECTURE.md` §8 — all optional; add them as each
section tells you to:

| Variable | What it is | When you set it |
|---|---|---|
| `WFG_FIRMS_MAP_KEY` | Your NASA FIRMS map key. Setting it flips the app to **live** fire data | §3.7 |
| `WFG_APP_MODE` | Force `demo` or `live` (normally leave unset — the key above decides) | Only to override |
| `WFG_PREDICTION_FILE` | Path to a spread-prediction GeoJSON from the research pipeline. Leave unset: the app then honestly says prediction is unavailable in live mode | Advanced, later |
| `WFG_CORS_ORIGINS` | Comma-separated list of website origins allowed to call this API, e.g. `https://wildfireguardian.app,capacitor://localhost` | §4.4 |
| `WFG_DB_PATH` | Where the SQLite database file lives, e.g. `/data/guardian.db` on a mounted disk | §5.8 |
| `STRIPE_SECRET_KEY` | Stripe secret key (`sk_test_…` then `sk_live_…`) | §5 |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (`pk_…`) | §5 |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_…`) | §5.6 |
| `STRIPE_PRICE_MONTHLY` | Price ID (`price_…`) of Guardian Plus monthly | §5.4 |
| `STRIPE_PRICE_YEARLY` | Price ID (`price_…`) of Guardian Plus yearly | §5.4 |

Every change to environment variables triggers an automatic redeploy
(~1 minute).

### 3.6 Custom domain + HTTPS

You can ship on the free `…onrender.com` address, but a real domain looks
trustworthy in store listings and lets you move hosts later without breaking
the apps.

1. Buy a domain at any registrar (Namecheap, Cloudflare Registrar, or Gabia
   가비아 for `.kr`). ~US$10–15/yr. Say you bought `wildfireguardian.app`.
2. In Render: your service → **Settings → Custom Domains** → **Add Custom
   Domain** → enter `api.wildfireguardian.app`.
   - ✅ *What you should see:* Render shows you a **CNAME record** to create
     (a name and a target like `wildfireguardian-api.onrender.com`).
3. In your registrar's DNS panel: add that CNAME record exactly as shown.
4. Wait 5–30 minutes. Render verifies the record and issues a free HTTPS
   certificate automatically.
   - ✅ *What you should see:* the domain listed as **Verified /
     Certificate Issued**, and `https://api.wildfireguardian.app/v1/health`
     answering in your browser with the padlock icon.

From here on, this manual writes `https://api.wildfireguardian.app` —
substitute your real domain (or the `…onrender.com` URL).

### 3.7 Going live: the NASA FIRMS MAP_KEY

**What it is:** NASA's FIRMS (Fire Information for Resource Management
System) publishes satellite fire detections (VIIRS + MODIS instruments)
worldwide, free, within ~3 hours of overpass. Access to the machine-readable
API requires a free **MAP_KEY** — an anti-abuse token, not a payment.
*(As of Aug 2026 the limit is 5,000 transactions per 10-minute window —
vastly more than this app uses, since the backend caches for 60 s.)*

1. Go to [https://firms.modaps.eosdis.nasa.gov/api/map_key/](https://firms.modaps.eosdis.nasa.gov/api/map_key/).
2. Fill in your email address and submit.
   - ✅ *What you should see:* an email from NASA/LANCE containing a long
     hex string — that string is your MAP_KEY.
3. In Render → **Environment** → add `WFG_FIRMS_MAP_KEY` = that string →
   Save (redeploys automatically).
4. Re-open `/v1/health`.
   - ✅ *What you should see:* `"mode": "live"`. The app now shows real
     detections — and, honestly, `"prediction_available": false` (no spread
     prediction is fabricated; see `ARCHITECTURE.md` §3).

> If there are no active fires near a test location, **live mode showing "no
> active fire" is correct behavior**, not a bug. Use the demo deployment (or
> `WFG_APP_MODE=demo`) for demonstrations, where everything is labelled
> 연습 모드 / DEMO.

---

## §4. Deploy the web app (Netlify)

**Goal:** the resident app at `https://wildfireguardian.app`, installable on
phones as a PWA.

### 4.1 Why Netlify

*(As of Aug 2026)* Netlify's free tier **permits commercial use**; Vercel's
otherwise-similar free "Hobby" tier is restricted to non-commercial projects,
which a Stripe-selling app is not. Both are excellent; this manual gives
Netlify clicks. (You may also serve `dist/` from the backend host behind one
domain — a fine advanced setup, not covered here.)

### 4.2 Create the site

1. Sign up at [netlify.com](https://netlify.com) **with GitHub**.
2. **Add new site → Import an existing project → GitHub** → pick
   `wildfireguardian`.
3. Fill the build settings exactly:

   | Field | Value |
   |---|---|
   | Base directory | `app/frontend` |
   | Build command | `npm run build` |
   | Publish directory | `app/frontend/dist` |

4. Click **Add environment variables** → **New variable**:
   - Key: `VITE_API_BASE` — Value: `https://api.wildfireguardian.app`
   (This is baked in **at build time** — if you ever change the backend URL,
   change this variable and redeploy.)
5. Click **Deploy site**.
   - ✅ *What you should see:* a build log, then a green **Published** deploy
     and a random URL like `https://melodic-kitsune-123abc.netlify.app`.

### 4.3 Custom domain for the web app

1. Netlify → **Domain management** → **Add a domain** → enter
   `wildfireguardian.app` (the bare domain this time) → follow the DNS
   instructions (either point the domain's nameservers at Netlify, or add
   the A/CNAME records it shows — both work; nameservers are simpler).
2. Wait for **Netlify DNS verified** and the automatic HTTPS certificate.
   - ✅ *What you should see:* `https://wildfireguardian.app` loads the app
     with a padlock.

### 4.4 Connect frontend to backend (CORS)

Browsers block a site on one origin from calling an API on another origin
unless the API explicitly allows it. Allow it:

1. Render → **Environment** → set
   `WFG_CORS_ORIGINS` = `https://wildfireguardian.app,https://melodic-kitsune-123abc.netlify.app,capacitor://localhost,https://localhost`
   (your real Netlify URL; the two `localhost` entries are for the iOS and
   Android wrapped builds later) → Save.
2. Open `https://wildfireguardian.app` in a normal browser.
   - ✅ *What you should see:* the Home screen with the big status button,
     the 연습 모드 / DEMO banner (if the backend is in demo mode), Korean text
     by default. If instead the screen says it cannot reach the server, see
     FAQ Q1 (CORS).

### 4.5 Install it on a phone (the PWA moment)

Do this on your own phone now — it's also exactly what you'll tell users who
don't use app stores:

**Android (Chrome):**
1. Open `https://wildfireguardian.app` in Chrome.
2. Tap the **⋮** menu → **홈 화면에 추가 / Add to Home screen** → **설치 / Install**.
   - ✅ *What you should see:* a 산불지킴이 icon on the home screen that
     opens full-screen without browser bars.

**iPhone (Safari — must be Safari):**
1. Open the site in Safari.
2. Tap the **Share** square-with-arrow → scroll → **홈 화면에 추가 / Add to
   Home Screen** → **Add**.
   - ✅ *What you should see:* same full-screen icon behavior.

**You now have a live product.** Everything after this point is about
payments and stores.

---

## §5. Stripe: test mode → live mode

**Goal:** Guardian Plus (`ARCHITECTURE.md` §9) purchasable on the **web**
version with real cards. Reminder: if you're Korea-based without a foreign
entity, re-read §2.5 — you may be choosing "launch free" and skipping this
section for now, which is completely fine.

Design recap so the steps make sense: the backend uses **hosted Stripe
Checkout** — your server never touches card numbers; it just creates a
checkout session and Stripe hosts the payment page. Stripe then reports
events to your **webhook** (`/v1/billing/webhook`), which updates the
subscriptions table.

### 5.1 Create the account (test mode)

1. Sign up at [stripe.com](https://stripe.com).
   - ✅ *What you should see:* a dashboard in **Test mode** (orange "Test"
     badge / toggle in the top corner). Everything works immediately in test
     mode, before any identity checks.

### 5.2 Get the test keys

1. Dashboard → **Developers → API keys**.
2. Copy the **Publishable key** (`pk_test_…`) and reveal + copy the
   **Secret key** (`sk_test_…`).
3. In Render → Environment, add:
   - `STRIPE_PUBLISHABLE_KEY` = `pk_test_…`
   - `STRIPE_SECRET_KEY` = `sk_test_…`

### 5.3 Create the product

1. Dashboard (still Test mode) → **Product catalog** → **Add product**.
2. Name: `Guardian Plus`. Description (customer-visible on receipts, keep it
   honest): `가족 알림·문자 전송·오프라인 지도 등 편의 기능 구독. 모든 안전 정보는 무료입니다. / Convenience subscription (family alerts, SMS delivery, offline maps). All safety information is free.`

### 5.4 Create the two prices

1. On the product page, **Add price**: Recurring → Monthly → set your price
   (e.g. ₩4,900 or $3.99 — your call) → Save. Copy the price ID (`price_…`).
2. **Add another price**: Recurring → Yearly → set the price → Save. Copy its
   ID.
3. In Render → Environment:
   - `STRIPE_PRICE_MONTHLY` = the monthly `price_…`
   - `STRIPE_PRICE_YEARLY` = the yearly `price_…`

### 5.5 Configure the webhook (test mode)

1. Dashboard → **Developers → Webhooks** → **Add endpoint**.
2. Endpoint URL: `https://api.wildfireguardian.app/v1/billing/webhook`
3. Events to send — select exactly these three
   (`ARCHITECTURE.md` §9):
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Click **Add endpoint**, then reveal the **Signing secret** (`whsec_…`).
5. Render → Environment → `STRIPE_WEBHOOK_SECRET` = `whsec_…`.

### 5.6 Test the whole loop with a fake card

1. Open the web app → **가족 / Family** screen → choose Guardian Plus →
   subscribe.
   - ✅ *What you should see:* a redirect to a `checkout.stripe.com` page.
2. Pay with Stripe's universal test card: number `4242 4242 4242 4242`, any
   future expiry, any CVC, any name.
   - ✅ *What you should see:* redirect back to the app's success screen, and
     within a few seconds the Plus features unlock (the app polls
     `/v1/billing/status`).
3. In Stripe → **Developers → Webhooks → your endpoint**:
   - ✅ *What you should see:* recent deliveries with green **Succeeded
     (200)** marks. Any 400s → FAQ Q7.

⚠️ Never edit or delete the `STRIPE_WEBHOOK_SECRET` casually once live —
with a wrong secret the backend rejects all of Stripe's reports and paid
users stop unlocking, silently.

### 5.7 Activate live mode *(as of Aug 2026)*

1. In the Stripe dashboard, use the test/live toggle → Stripe prompts you to
   **Activate your account**.
2. Provide the legal details: business/personal legal name, address, tax
   information, bank account for payouts, website URL
   (`https://wildfireguardian.app`). Submit a few days before you actually
   need live payments — Stripe sometimes requests extra verification
   documents and review can take up to a week.
3. Stripe requirement: the website you list must show what you sell, contact
   info, and a refund/cancellation policy — §10.5's pages satisfy this;
   publish them first.

### 5.8 The live-mode cutover checklist

Stripe's own [go-live checklist](https://docs.stripe.com/get-started/checklist/go-live)
is the authority; the app-specific distilled version:

1. ☐ **Recreate the product and both prices in live mode** — test-mode
   objects (products, prices) do **not** carry over. Repeat §5.3–5.4 with the
   toggle on **Live**; you get *new* `price_…` IDs.
2. ☐ **Create a live webhook endpoint** — repeat §5.5 in live mode (same
   URL); you get a *new* `whsec_…`.
3. ☐ **Move the backend off the free tier first** (§3.1): Render Starter +
   1 GB persistent disk mounted at `/data`, and set `WFG_DB_PATH` =
   `/data/guardian.db`. A paid product must not forget its subscribers on
   restart.
4. ☐ Swap all five Stripe env vars in Render **in one sitting**:
   `STRIPE_SECRET_KEY` → `sk_live_…`, `STRIPE_PUBLISHABLE_KEY` → `pk_live_…`,
   `STRIPE_WEBHOOK_SECRET` → live `whsec_…`, `STRIPE_PRICE_MONTHLY` /
   `STRIPE_PRICE_YEARLY` → live `price_…` IDs. Mixing test and live values is
   FAQ Q8.
5. ☐ Make one **real purchase with your own card**, verify unlock, then
   refund yourself from the Stripe dashboard (Payments → ⋯ → Refund).
6. ☐ Check the live webhook shows **Succeeded** deliveries for that purchase.
7. ☐ Confirm payout schedule under **Balances → Payouts** (first payout is
   typically delayed ~7 days).

---
## §6. Payments and the app stores — THE CRITICAL SECTION

Read this twice. More apps die in review over payments than over anything
else, and the rules changed dramatically in 2025–2026. Everything below was
verified in **August 2026**; re-verify before each submission, because this
is the fastest-moving policy area in the industry.

### 6.1 The one rule that protects this app: safety is free

`ARCHITECTURE.md` §1 is deliberate armor: **every life-safety feature —
danger status, map, spread, evacuation routes, alerts — is free, forever, no
account needed.** Guardian Plus sells convenience only.

Why this matters for review, not just ethics:

- Apple reviews safety-adjacent apps with **greater scrutiny** (Guideline
  1.4, Physical Harm: apps that "could provide inaccurate data or
  information" in safety/medical contexts get extra review — see
  [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)).
  A reviewer who sees an evacuation route behind a paywall will, correctly,
  reject the app and may escalate.
- Both stores' reviewers test the app as an anonymous user. Because the free
  tier is the whole safety product, a reviewer can evaluate everything
  without an account — this alone avoids a large class of "we couldn't
  access the app's features" rejections.
- If a journalist ever writes "wildfire app charges elderly Koreans for
  evacuation routes," the product is dead regardless of what the stores say.

**Never let a future "growth idea" move a safety feature behind Guardian
Plus.** It violates the spec, the stores' spirit, and the users' trust.

### 6.2 The store rules in plain words *(state as of Aug 2026)*

**Apple (Guideline 3.1.1 and friends):** digital goods and services sold
*inside* an iOS app must use Apple's in-app purchase (IAP), with these
carve-outs:

- **United States storefront:** after the Epic v. Apple contempt ruling,
  Apple updated its guidelines (May 2025) so US-storefront apps **may
  include buttons and external links to outside purchase pages — no
  entitlement, no Apple commission** on those web purchases. This is
  US-only. ([Apple's current 3.1.1(a)](https://developer.apple.com/app-store/review/guidelines/#payments); [TechCrunch coverage](https://techcrunch.com/2025/05/02/apple-changes-us-app-store-rules-to-let-apps-redirect-users-to-their-own-websites-for-payments); [9to5Mac](https://9to5mac.com/2025/05/01/apple-app-store-guidelines-external-links/))
- **All other storefronts (including Korea):** apps "may not include
  buttons, external links, or other calls to action that direct customers to
  purchasing mechanisms other than in-app purchase" (guideline text, Aug
  2026). Korea has a separate legal carve-out — the StoreKit External
  Purchase entitlement under the Telecommunications Business Act — but it
  requires a **Korea-only separate binary** and Apple still charges a **26%
  commission** on those alternative-payment sales
  ([Apple's Korea entitlement page](https://developer.apple.com/support/storekit-external-entitlement-kr); [CNBC](https://www.cnbc.com/2022/06/30/apple-opens-up-third-party-app-payments-in-korea-will-take-26percent-cut-.html)).
  26% + your payment processor's fees ≈ 30%: for a small app it buys you
  paperwork, not margin. Skip it.
- **What is always allowed everywhere (Guideline 3.1.3(b), "multiplatform
  services"):** users may **sign in and use content/subscriptions they
  bought elsewhere** (on your website), as long as the app itself doesn't
  advertise or link to the external way to buy. This is the "Netflix model"
  and it is the backbone of our recommended path.

**Google Play:** digital purchases inside the app must use Google Play's
billing, **except** where billing-choice programs apply:

- **From June 30, 2026** *(rolling out first in the US, UK, and EEA)*:
  developers may offer **alternative billing or external web links alongside
  Play Billing**. New fee structure in those regions: **10% service fee** on
  the first US$1M/year and on all auto-renewing subscriptions, **plus a 5%
  billing fee only if Google processes the payment**
  ([Android Developers Blog](https://android-developers.googleblog.com/2026/06/play-expanded-billing.html); [Play service-fee help](https://support.google.com/googleplay/android-developer/answer/112622)).
- **South Korea:** the older user-choice billing program applies —
  offering an alternative billing system reduces Google's service fee by
  **4 percentage points** (e.g. 15% → 11%) on those transactions.
- Like Apple, Google allows sign-in to subscriptions purchased elsewhere, as
  long as the app doesn't steer users to the external purchase outside the
  sanctioned programs.

**Commissions if you *do* use store billing** *(as of Aug 2026)*:

| | Standard | What a small app actually pays |
|---|---|---|
| Apple | 30%; subscriptions drop to 15% after a subscriber's 12th paid month | **15% from day one** via the [Small Business Program](https://developer.apple.com/app-store/small-business-program/) (enroll — it's a form; eligibility: under US$1M/yr proceeds) |
| Google Play | 15% on first US$1M/yr (and 15% on subscriptions) in most countries; US/UK/EEA moving to the 10%+5% model above | ~15% all-in |

### 6.3 The recommended compliant path for THIS app

**Phase 1 — what you ship first (this manual's default): the store builds
contain no purchases at all.**

1. iOS and Android builds are **100% free**: all safety features, no
   payment button, no "Guardian Plus" upsell screen, no link to the website's
   pricing page. The web/PWA version is where Guardian Plus is sold (§5).
2. A user who subscribed on the web and signs in inside the native app gets
   their Plus features — allowed everywhere under the multiplatform rules
   (Apple 3.1.3(b); Play's equivalent).
3. The app may say, at most, factual copy like "이 기기에서는 Guardian Plus를
   구매할 수 없습니다 / Guardian Plus is not available for purchase in this
   app." **No price, no URL, no "visit our website."** (On the US storefront
   you *could* link out — but a single worldwide binary with no link is
   simpler and cannot be rejected anywhere.)

Why this is the right first move: it requires **zero native billing code**,
it is compliant in every country simultaneously, review risk is near zero,
and — because Guardian Plus is a convenience tier for a free safety app —
the revenue you forgo from store users at launch is small.

**Phase 2 — when revenue matters (later, optional):** implement real store
billing (Apple IAP via StoreKit, Google Play Billing), sell the same
monthly/yearly Guardian Plus through the stores at ~15% commission, and keep
Stripe for the web. This is genuine development work (a Capacitor IAP
plugin, backend receipt validation, reconciling three subscription sources)
— budget weeks, not days, and do it only when store demand proves itself.

**Phase 3 — regional link-outs (advanced, optional):** US storefront
link-out (free of commission) and Play's US/UK/EEA billing-choice program
can raise margins, at the cost of region-specific builds/configuration and
ongoing policy-watching. Not for a first-time publisher.

### 6.4 Consequences of getting it wrong

- **Immediate rejection** citing Apple 3.1.1 / Google Payments policy — the
  most common: a leftover "구독하기 / Subscribe" button that opens Stripe
  Checkout inside the iOS app in a non-US storefront. Days lost per attempt.
- **Removal after approval**: reviewers re-scan updates; a payment link
  added "temporarily" in v1.1 can take the whole app down.
- **Repeated or willful violations → developer account termination** (both
  stores), which also kills every other app on the account and is very hard
  to appeal.
- **Paywalling safety features** risks all of the above plus 1.4-class
  scrutiny — and unlike a payment-button mistake, it torches user trust.

**Pre-submission self-check (run before every store upload):**

1. ☐ Open every screen in the store build: is there any button, link, price,
   or text that would lead a user toward paying outside the store? Remove it.
2. ☐ Are all three danger levels, the map, routes, and alerts reachable with
   no account and no payment? They must be.
3. ☐ Does the demo scenario, if shown, carry the 연습 모드 / DEMO banner? It
   must.
4. ☐ Does the listing text avoid any claim that the app *is* an emergency
   service or replaces 119/재난문자? (§7.8.)

---

## §7. iOS via Capacitor: from repo to the App Store

### 7.1 What you need

- **A Mac.** Building and uploading iOS apps requires Xcode, which runs only
  on macOS — no exceptions. Any Apple-silicon Mac (even a base Mac mini, or
  a borrowed/rented one) works. Cloud Macs (MacStadium, AWS EC2 Mac) and
  CI services (Codemagic, GitHub Actions macOS runners) are real
  alternatives once you're comfortable, but do your **first** submission on
  a Mac you can see, because review feedback loops are much easier
  interactively.
- **Xcode** (free, from the Mac App Store) — the newest version it offers;
  Capacitor 6 (which this repo pins) requires Xcode 15 or newer.
- **Apple Developer Program membership** — US$99/yr *(as of Aug 2026)*, §2.
- ~2 GB of downloads and a free afternoon for the one-time setup.

### 7.2 One-time Mac setup

1. Install **Xcode** from the Mac App Store, open it once, accept the
   license, and let it install its extra components.
2. Install **Node.js** (LTS) from [nodejs.org](https://nodejs.org) (download
   the macOS installer, click through).
   - ✅ *What you should see:* in Terminal, `node --version` prints `v20…`
     or newer.
3. Install **CocoaPods** (Capacitor's iOS dependency manager):

   ```bash
   sudo gem install cocoapods
   ```

   (If this fights you on a fresh Mac, the Homebrew route — `brew install
   cocoapods` — is the reliable fallback; FAQ Q10.)
4. Get the code onto the Mac:

   ```bash
   git clone https://github.com/YOUR_USERNAME/wildfireguardian.git
   cd wildfireguardian/app/frontend
   npm install
   ```

### 7.3 Build the web app and generate the iOS project

1. Build with the production backend baked in:

   ```bash
   VITE_API_BASE=https://api.wildfireguardian.app npm run build
   ```

   - ✅ *What you should see:* `✓ built in …s` and a `dist/` folder.
2. Generate the native iOS project (first time only):

   ```bash
   npx cap add ios
   ```

   - ✅ *What you should see:* an `ios/` folder appears under
     `app/frontend/`, ending with `✔ add in …s`. (The repo intentionally
     does not commit `ios/` — you own it locally.)
3. Copy the web build into the native project (repeat after **every**
   `npm run build`):

   ```bash
   npx cap sync ios
   ```

4. Open it in Xcode:

   ```bash
   npx cap open ios
   ```

   - ✅ *What you should see:* Xcode opens a project called **App** with the
     app name 산불지킴이.

### 7.4 Signing and bundle ID

1. In Xcode's left sidebar click the blue **App** project icon → select the
   **App** target → **Signing & Capabilities** tab.
2. Tick **Automatically manage signing**.
3. **Team:** choose your Apple Developer account (add it first via Xcode →
   Settings → Accounts → **+** → sign in with your Apple ID if the menu is
   empty).
4. Confirm **Bundle Identifier** is `kr.wildfireguardian.app` (it comes from
   `capacitor.config.ts`).
   - ✅ *What you should see:* "Provisioning Profile: Xcode Managed Profile"
     and no red errors in the Signing panel.
5. Plug in an iPhone (or pick a Simulator), press the **▶ Run** button.
   - ✅ *What you should see:* the app launches, Korean-first, talking to
     your live backend. (First run on a real device asks you to trust the
     developer certificate in the iPhone's Settings → General → VPN & Device
     Management.)

### 7.5 Location permission purpose strings (bilingual)

iOS shows the user *your* explanation when asking for location. A missing or
vague explanation is a guaranteed rejection (Guideline 5.1.1). The app uses
when-in-use location only.

1. In Xcode: **App target → Info** tab → hover any row → **+** → add key
   `Privacy - Location When In Use Usage Description`
   (`NSLocationWhenInUseUsageDescription`) with the English value:

   > Your location is used only to show wildfire danger, evacuation routes,
   > and shelters near you. It is not used for advertising.

2. Give it Korean too (App Store language = ko first): in the project
   navigator select **App → App →** add a **Strings File (Legacy)** named
   `InfoPlist.strings`, click it → File Inspector → **Localize…** → Korean,
   and put in the Korean variant:

   ```text
   "NSLocationWhenInUseUsageDescription" = "현재 계신 곳 주변의 산불 위험, 대피 경로, 대피소를 알려드리기 위해서만 위치를 사용합니다. 광고에는 사용하지 않습니다.";
   ```

   (Simple, respectful 존댓말; no technical words — the reader may be 78.)

### 7.6 Create the app record in App Store Connect

1. Go to [appstoreconnect.apple.com](https://appstoreconnect.apple.com) →
   **My Apps** → **+** → **New App**.
2. Fill in:
   - Platform: iOS
   - Name: `산불지킴이 — 산불 안전 알리미` (30 chars max; the English
     localization can be `WildfireGuardian`)
   - **Primary language: Korean**
   - Bundle ID: select `kr.wildfireguardian.app` (it appears here after
     Xcode registered it in §7.4; if missing, add it manually at
     [developer.apple.com → Identifiers](https://developer.apple.com/account/resources/identifiers/list))
   - SKU: `wfg-ios-001` (internal label, never shown)
3. ✅ *What you should see:* the app's page with an empty "1.0 Prepare for
   Submission" version.

### 7.7 The listing, bilingual (ko primary + en-US)

In the version page, fill Korean first, then use the language switcher (top
right) → **English (U.S.)** and fill again. Suggested copy you may use
verbatim:

- **Subtitle (ko):** `우리 집 주변 산불, 세 가지 색으로`
  **(en):** `Nearby wildfire danger in three colors`
- **Description (ko):** must include, prominently:

  > 산불지킴이는 위성 관측 자료(NASA FIRMS)를 바탕으로 우리 집 주변의 산불
  > 상황을 안전(초록)·주의(주황)·대피(빨강) 세 단계로 알기 쉽게 보여드립니다.
  > 위험 상태, 지도, 대피 경로, 알림 등 모든 안전 기능은 무료입니다.
  >
  > 이 앱은 공식 재난 안내를 **보조**하는 서비스입니다. 재난문자와 119의
  > 안내를 항상 우선하여 따라 주세요.

- **Description (en):** equivalent text, including: *"All safety features
  are free. This app supplements official emergency alerts and 119
  instructions — always follow them first."*
- **Keywords (ko):** `산불,대피,안전,재난,위성,지도,어르신` — **(en):**
  `wildfire,evacuation,safety,korea,fire,map,seniors`
- **Support URL:** `https://wildfireguardian.app` · **Privacy Policy URL:**
  `https://wildfireguardian.app/privacy` (publish §10.5 first).
- **Category:** Weather (primary) / Navigation (secondary) — do **not**
  pick Medical.
- **Age rating questionnaire:** answer everything "No" → rating 4+.
  ("Unrestricted web access" = No; the app opens no browser.)

**Never put in any listing:** research metrics (no AUC — house rule),
"replaces official alerts", "emergency service", guarantees of accuracy, or
mention of purchasing outside the app (§6).

### 7.8 Screenshots *(sizes as of Aug 2026)*

Apple requires screenshots in exact pixel sizes. Since Apple auto-scales the
largest iPhone size down, you only need **one iPhone set** — plus an iPad
set **only if** the app targets iPad:

| Device class | Size | Required? |
|---|---|---|
| iPhone 6.9″ | **1320 × 2868** portrait | Yes — 1 to 10 images |
| iPad 13″ | 2064 × 2752 | Only if iPad is enabled |

Practical route: in Xcode choose a **iPhone 17 Pro Max simulator**, run the
app, press **⌘S** in the Simulator to save pixel-perfect screenshots. Take
6: Home in each of SAFE/WATCH/GO (use the demo backend's `?t=` replay to get
each state), the map with spread polygons, the evacuation route, the Guide
screen. The DEMO banner will be visible — that is honest and fine; you may
note it in the review notes. To simplify launch, disable iPad: Xcode → App
target → General → Supported Destinations → remove iPad (then no iPad
screenshots are needed).

### 7.9 App Privacy ("privacy nutrition labels")

App Store Connect → your app → **App Privacy** → **Get Started**. Declare
exactly what the app does — matching the privacy policy (§10.5):

1. **Location (Precise):** collected, used for **App Functionality** only,
   **not linked to identity**, **no tracking**. (Location is sent in API
   queries to compute the local situation; the backend stores no location
   history.)
2. **If billing is configured (web-purchased Plus with in-app sign-in):**
   Contact Info → Email Address: App Functionality, linked to identity (the
   subscription record), no tracking.
3. Nothing else. No advertising data, no analytics identifiers (the app
   ships none).
- ✅ *What you should see:* a generated privacy label preview showing
  "Data Not Linked to You: Location" (plus Email if declared).

### 7.10 TestFlight *(limits as of Aug 2026)*

1. In Xcode: **Product → Archive** (with "Any iOS Device (arm64)" selected
   as the run destination).
   - ✅ *What you should see:* the Organizer window with your archive.
2. Click **Distribute App → App Store Connect → Upload** → accept defaults.
   - ✅ *What you should see:* "Upload Successful". The build appears in App
     Store Connect → TestFlight in ~15–60 minutes (it emails you when
     processing finishes).
3. **Internal testing** (instant, no review): TestFlight tab → Internal
   Testing → **+** → add up to **100 members** of your team by Apple ID
   email. They get an invite in the TestFlight app.
4. **External testing** (optional, up to **10,000 testers** via email or a
   public link): create a group, add the build — the **first build of each
   version needs a lightweight Apple review** (~1 day) before external
   testers can install.
5. Builds **expire 90 days** after upload; upload a fresh one if testing
   runs long.
6. Test on a real phone in the field, ideally with one elderly relative —
   watch them use it, fix what confuses them, before any store submission.

### 7.11 Review notes for an emergency-adjacent app (copy, adapt, paste)

App Store Connect → version page → **App Review Information → Notes**. This
is your private channel to the human reviewer. Apple's Guideline **5.1.5
(Location Services)** says location-based APIs "shouldn't be used to provide
emergency services", and Guideline **1.4 (Physical Harm)** promises extra
scrutiny for apps whose bad data could hurt someone — so tell the reviewer
exactly what the app is and is not:

> **What this app is:** a wildfire *information and preparedness* app for
> residents, especially elderly users. It displays publicly available NASA
> FIRMS satellite fire detections, a three-level advisory status, walking
> routes to named shelters, and preparedness guidance, in Korean and
> English.
>
> **What it is not:** it is not an emergency service, does not contact
> emergency services automatically, and does not claim to replace official
> channels. A permanent in-app disclaimer states it supplements government
> emergency alerts (재난문자) and 119 instructions (visible on the Home and
> Guide screens). Per Guideline 5.1.5, location is used only to display
> relevant nearby information, and the UI notes coverage limitations.
>
> **Free access:** every safety feature is free with no account. The app
> contains no purchases and no external purchase links.
>
> **Demo data labeling:** if the server is in demonstration mode, all data
> is synthetic and the UI shows a permanent "연습 모드 / DEMO" banner.
> Nothing synthetic is ever presented as a real fire.
>
> **How to test:** launch the app and allow location, or use these
> coordinates in Simulator (Features → Location → Custom Location):
> lat 36.44, lon 129.45 (near the demo scenario area). The status button,
> map, route, and read-aloud buttons are all reachable from the Home screen.

### 7.12 Submit, and the common rejections

1. Version page → select the build → **Add for Review** → **Submit to App
   Review**.
   - ✅ *What you should see:* status "Waiting for Review". Typical wait
     *(as of Aug 2026)*: most reviews complete within 24–48 hours; first
     submissions can take longer. Rejections arrive as messages in App Store
     Connect — reply there, fix, resubmit; each round costs 1–3 days.

| Rejection (guideline) | Why it happens to apps like this | Fix |
|---|---|---|
| **4.2 Minimum functionality** ("web wrapper") | Capacitor apps that look like a website in a frame | Ours has native-feeling UI, offline shell, read-aloud, no browser chrome — if flagged, respond in Resolution Center describing the native behaviors (PWA offline shell, Web Speech read-aloud, location integration) |
| **3.1.1 Payments** | Any visible path to paying outside Apple | §6.3 — the store build must contain none |
| **5.1.1 Privacy — permission strings** | Vague/missing location purpose string | §7.5 exact strings |
| **5.1.5 Location services** | Marketing text implying the app *provides* emergency services | Use the wording in §7.7/§7.11: information + preparedness, supplements official channels |
| **1.4 Physical harm scrutiny** | Reviewer unsure whether data is real or reliable | The review notes above; DEMO banner honesty; disclaimer visible in-app |
| **2.1 App completeness** | Crashes, dead buttons, backend down during review | Keep the backend on a paid always-on instance during review week (cold-start timeouts read as "app broken" — FAQ Q2) |
| **2.3 Accurate metadata** | Screenshots showing features the build lacks, or unlabeled synthetic data presented as real | Screenshots from the actual build, DEMO banner visible where applicable |

When approved you choose **Manually release** or automatic; pick manual for
your first launch so the store page, web app, and backend go live in an
order you control.

---
## §8. Android via Capacitor: from repo to Google Play

Works on Windows, Mac, or Linux.

### 8.1 One-time setup

1. Install **Android Studio** from
   [developer.android.com/studio](https://developer.android.com/studio)
   (accept the default components: Android SDK, platform tools, an
   emulator).
2. Install **Node.js** LTS from [nodejs.org](https://nodejs.org) if this
   machine doesn't have it (check: `node --version`).
3. Get the code and dependencies (skip if already done on this machine):

   ```bash
   git clone https://github.com/YOUR_USERNAME/wildfireguardian.git
   cd wildfireguardian/app/frontend
   npm install
   ```

### 8.2 Build the web app and generate the Android project

```bash
VITE_API_BASE=https://api.wildfireguardian.app npm run build
npx cap add android      # first time only — creates app/frontend/android/
npx cap sync android     # repeat after every npm run build
npx cap open android     # opens the project in Android Studio
```

- ✅ *What you should see:* Android Studio opens, Gradle sync runs
  (minutes, first time), and finishes with no red errors. Press **▶ Run**
  with an emulator or a USB-connected phone (enable Developer Options →
  USB debugging on the phone): the app launches against your live backend.

### 8.3 The keystore — and how not to lose it

Android apps are signed with a **keystore** file + passwords. Understand the
two-key system before creating anything:

- **Upload key** (yours, created below): signs what you upload to Google.
- **App signing key** (Google's): because new apps must use **Play App
  Signing**, Google holds the key that signs what users actually install.
  This is good news: **if you lose your upload key, Google can reset it**
  (Play Console → Test and release → App integrity → request upload key
  reset) — annoying but survivable. Losing a *self-managed* signing key
  (the old-world setup, or what Galaxy/ONE-store APKs use) is fatal: you
  could never update the app again. So: use Play App Signing (the default),
  and still guard your upload keystore like a passport.

1. Create the upload keystore (any terminal; `keytool` ships with Android
   Studio's JDK — on Windows run this in the terminal *inside* Android
   Studio if `keytool` isn't found):

   ```bash
   keytool -genkey -v -keystore wfg-upload.keystore -alias wfg-upload -keyalg RSA -keysize 2048 -validity 10000
   ```

2. It asks for a keystore password, then name/organization questions
   (answers appear only in certificate metadata; sensible values are fine),
   then a key password (press Enter to reuse the keystore password).
   - ✅ *What you should see:* a file `wfg-upload.keystore` in the current
     folder.
3. **Back it up now, three ways:** password manager (file + both passwords),
   an offline USB stick, and a second location (cloud drive is acceptable
   for the *upload* key since Google can reset it — but never commit it to
   the git repository).
4. Tell Gradle about it. Create
   `app/frontend/android/keystore.properties`:

   ```properties
   storeFile=/absolute/path/to/wfg-upload.keystore
   storePassword=YOUR_KEYSTORE_PASSWORD
   keyAlias=wfg-upload
   keyPassword=YOUR_KEY_PASSWORD
   ```

   and add `keystore.properties` to `.gitignore` (never commit passwords).
   Then in Android Studio you can simply use **Build → Generate Signed App
   Bundle** (next step) which asks for the same values interactively — the
   file is optional convenience for command-line builds.

### 8.4 Build the AAB (the file you upload)

In Android Studio:

1. **Build → Generate Signed App Bundle / APK…** → choose **Android App
   Bundle** → Next.
2. Point it at `wfg-upload.keystore`, enter the passwords, alias
   `wfg-upload` → Next.
3. Build variant: **release** → **Create**.
   - ✅ *What you should see:* a notification "App bundle(s) generated
     successfully" with a locate link — the file is
     `app/frontend/android/app/build/outputs/bundle/release/app-release.aab`.

(Command-line equivalent, after §8.3 step 4: `cd app/frontend/android &&
./gradlew bundleRelease`.)

### 8.5 Play Console: account and app record

1. Sign up at [play.google.com/console/signup](https://play.google.com/console/signup):
   choose **Personal** or **Organization** (§2.2), pay the **US$25 one-time
   fee** *(as of Aug 2026)*, and complete identity verification (ID
   document; days, sometimes a week).
2. Console → **Create app**: name `산불지킴이`, default language
   **Korean (South Korea)**, type **App**, **Free** (⚠️ free→paid can never
   be changed later; free is correct — Guardian Plus is not sold in this
   build at all, §6.3).
3. Work through the **Set up your app** checklist on the dashboard —
   each item is a form:
   - **Privacy policy:** `https://wildfireguardian.app/privacy` (§10.5).
   - **App access:** "All functionality is available without special
     access" (true — no login needed for safety features).
   - **Ads:** No.
   - **Content rating:** the IARC questionnaire — category "Utility",
     answer the violence/gambling/etc. questions No.
     ✅ rating **Everyone / 전체이용가**.
   - **Target audience:** 18+ (do not target children — avoids the
     Families policy stack).
   - **News app:** No. **COVID-19 app:** No.
   - **Data safety** (the Android privacy label):
     - Collected: **Location → Precise location.** Purpose: App
       functionality. Processed ephemerally: yes (queries are not stored as
       a location history). Shared with third parties: No. (NASA FIRMS
       receives *area* queries from your backend, not the user's identity.)
     - If sign-in exists in this build: Email address, App functionality.
     - "Is all collected data encrypted in transit?" Yes (HTTPS).
       "Can users request deletion?" Yes (via the §10.5 contact email).
   - **Government app:** No.
4. **Main store listing** (bilingual — default ko-KR; then "Manage
   translations" → add **English (United States)**):
   - Short description (ko, ≤80 chars):
     `우리 집 주변 산불 위험을 안전·주의·대피 세 가지 색으로 알려드립니다. 모든 안전 기능 무료.`
   - Short description (en): `Nearby wildfire danger in three simple
     colors. All safety features free.`
   - Full description: reuse §7.7's text, including the
     supplements-official-alerts disclaimer.
   - Graphics: app icon 512×512 PNG (from
     `app/frontend/public/icons/icon-512.png`, or regenerate with
     `npm run icons`), feature graphic 1024×500 (make one in Canva or any
     editor: flame+shield glyph, app name, the three colors), at least 2
     phone screenshots (use the ones from §7.8 or Android emulator captures;
     Play accepts a range of sizes).

### 8.6 Closed testing — the 14-day gate *(as of Aug 2026; personal accounts)*

Verified against [Google's requirements page](https://support.google.com/googleplay/android-developer/answer/14151465).
Organization accounts may skip to §8.7 (still run a real test anyway).

1. Console → **Testing → Closed testing** → **Create track** (default
   "Alpha" is fine) → **Create release** → upload `app-release.aab` →
   release name auto-fills → **Next** → resolve any warnings → **Save and
   publish**.
2. In the track's **Testers** tab: create an email list with your **12+
   testers'** Google-account emails, save, and copy the **join link**.
3. Send testers the join link; each must open it, click **Accept
   invitation**, then install from the Play link it shows.
   - ✅ *What you should see (Console, within a day):* the track shows
     active testers count ≥ 12.
4. Keep all 12+ opted in for **14 consecutive days**. Use the time: collect
   feedback, fix bugs, upload new releases to the same track (uploads don't
   reset the clock; testers dropping below 12 does).
5. After 14 days: dashboard → **Apply for production** → answer the
   questions about your testing honestly → submit.
   - ✅ *What you should see:* "Your application is being reviewed" —
     typically **≤7 days**.

### 8.7 Production rollout

1. **Production → Create release** → upload the (latest) AAB → **Next**.
2. Countries: select **South Korea** plus anywhere else you want (adding
   more later is one click; launching everywhere at once is fine for a free
   app).
3. **Roll-out percentage:** start **staged at 20%**, watch crashes/ANRs in
   **Quality → Android vitals** for a few days, then raise to 100%.
4. **Send for review.** New apps' first production review can take from a
   day to a week+ *(as of Aug 2026)*.
   - ✅ *What you should see:* status "In review" → "Available on Google
     Play", and your store URL
     `https://play.google.com/store/apps/details?id=kr.wildfireguardian.app`.

---

## §9. Korean stores (brief): Samsung Galaxy Store & ONE store

**Why/when to bother:** Google Play already reaches every Samsung phone, so
these are *additional shelf space*, not requirements. They start mattering
when: (a) you want preinstalled-store visibility on Samsung devices popular
with elderly Koreans, (b) you pursue Korean telco/government partnerships
(ONE store is the domestic, telco-backed market and plays well there), or
(c) you later sell in-app and want their lower commissions. For launch week:
**skip both; revisit in month 2.** Both take **APK** uploads — in Android
Studio's Generate Signed Bundle/APK dialog choose **APK** instead of AAB,
and keep that signing keystore backed up forever (no Play App Signing safety
net here — §8.3).

### 9.1 Samsung Galaxy Store *(as of Aug 2026)*

- Register free at [seller.samsungapps.com](https://seller.samsungapps.com)
  (Samsung account → Sign Up; no sign-up or annual fee). Commercial seller
  status (needed only for *paid* content — not our free app) requires extra
  business verification.
- Revenue share, for reference: developers keep **80%** on paid
  apps/in-app items and **85% on subscriptions** via Samsung Checkout
  (structure effective May 15, 2025 —
  [Samsung's FAQ](https://developer.samsung.com/galaxy-store/faq.html)).
- Process: New Application → upload APK, reuse the Play listing text and
  screenshots, country list Korea (or wider), submit; review takes days.

### 9.2 ONE store *(as of Aug 2026)*

- Korea's domestic app market (backed by the telcos + Naver), meaningful
  Android share in Korea and popular for Korean-market apps. Register at
  [dev.onestore.net](https://dev.onestore.net) (free; foreign developers
  supported; Korean-language portal — machine translation gets you
  through).
- Commissions are materially lower than the global duopoly's — base ~20%,
  and lower still using external payment options (ONE store advertises
  single-digit rates in some configurations); rates vary by payment type
  and country — check their
  [service-fee page](https://onestore-dev.gitbook.io/dev/docs/payment/service_fee)
  when you get there.
- Process mirrors Play: register → new app → upload APK → Korean listing →
  review. Our app is free, so commissions are moot until Phase 2 (§6.3).

---

## §10. After launch

### 10.1 Monitoring (know it's down before users do)

1. **Uptime:** create a free [UptimeRobot](https://uptimerobot.com) monitor
   on `https://api.wildfireguardian.app/v1/health`, checking every 5
   minutes, alerting your email/phone.
   - ✅ *What you should see:* a green "Up" monitor; break it once on
     purpose (suspend the Render service for a minute) to confirm the alert
     arrives.
2. **Backend logs:** Render → your service → **Logs** (live tail). Render
   also emails you on failed deploys.
3. **Web app:** Netlify → site → **Deploys** shows build failures.
4. This app is *safety-adjacent*: treat backend downtime like a pager, not
   an inbox. During fire season, check the monitor's weekly report.

### 10.2 Crash reports

- **iOS:** Xcode → Window → **Organizer → Crashes** (needs users to opt in
  to sharing), and App Store Connect → App Analytics.
- **Android:** Play Console → **Quality → Android vitals → Crashes &
  ANRs** — watch this during every staged rollout (§8.7).
- Optional, later: add Sentry (free tier) to the frontend for JS error
  reporting; not required at launch.

### 10.3 Updating the app (the routine you'll repeat forever)

**Web (most changes end here — instant, no review):**

1. Change code → `git push` to `main`.
2. Netlify and Render auto-deploy.
   - ✅ *What you should see:* new deploys in both dashboards; hard-refresh
     the site (the service worker updates on next load).

**Stores (needed only when the wrapped shell itself must change, or you
want store users to get a fresh baked-in build):**

1. Bump the version: `app/frontend/package.json` `"version"`, and in Xcode
   (App target → General → Version + Build) and Android
   (`android/app/build.gradle` → `versionCode` +1 — must always increase —
   and `versionName`).
2. `VITE_API_BASE=… npm run build && npx cap sync ios && npx cap sync android`
3. iOS: Archive → Upload → new version in App Store Connect → Submit
   (review again, usually ≤48 h).
4. Android: Generate Signed AAB → Production → Create release → review →
   staged rollout.

Because the frontend fetches everything live from your backend, most
content/logic improvements reach store users **without** a store update —
one of the quiet superpowers of this architecture.

### 10.4 Responding to reviews

- Reply from App Store Connect (Ratings & Reviews) and Play Console
  (Reviews). Reply to every 1–2★ review within days: politely, in the
  reviewer's language, 존댓말 in Korean, no defensiveness, and a support
  email. Store algorithms and future users both read your replies.
- Reviews reporting *safety-information errors* are incidents, not
  feedback: verify against FIRMS, fix, reply with what you changed.

### 10.5 Legal minimums

Publish these as pages on the website (e.g. `/privacy`, `/terms` — a simple
page each; Netlify serves anything in the frontend's `public/` folder), link
them in both store listings, and keep them true.

**A. Privacy policy — fill-in-the-blanks template (ko + en on one page):**

> **개인정보 처리방침 / Privacy Policy — 산불지킴이 (WildfireGuardian)**
> 시행일 / Effective date: `[YYYY-MM-DD]` · 운영자 / Operator: `[이름 또는 법인명 / your legal name or entity]` · 연락처 / Contact: `[support email]`
>
> 1. **수집하는 정보 / What we collect.** 위치 정보(위험 상황·대피 경로 안내
>    목적으로만 사용, 서버에 이동 기록을 저장하지 않음). Guardian Plus 구독
>    시: 이메일 주소, 결제 처리는 `[Stripe 등 결제사]`가 담당하며 카드 정보는
>    당사 서버에 저장되지 않습니다. / Location (used only to show nearby
>    danger, routes, shelters; no movement history stored). For Guardian
>    Plus subscribers: email address; payment is processed by `[Stripe]` —
>    card details never touch our servers.
> 2. **이용 목적 / Why.** 산불 위험 안내, 대피 경로 제공, 구독 관리. / To
>    provide wildfire information, evacuation routes, and manage
>    subscriptions.
> 3. **보관 기간 / Retention.** 위치: 즉시 처리 후 미보관. 구독 정보: 구독
>    종료 후 `[N]`개월. / Location: processed immediately, not retained.
>    Subscription records: `[N]` months after cancellation.
> 4. **제3자 제공 / Sharing.** 판매하지 않습니다. 결제 처리(`[Stripe]`),
>    호스팅(`[Render/Netlify]`) 외 제공 없음. / Never sold. Shared only
>    with our payment processor and hosting providers to operate the
>    service.
> 5. **이용자 권리 / Your rights.** 열람·정정·삭제 요청: `[support email]`
>    (30일 이내 처리). / Access, correction, deletion requests via the
>    contact email, handled within 30 days.
> 6. **아동 / Children.** 만 14세 미만을 대상으로 하지 않습니다. / Not
>    directed at children under 14.

> ⚠️ Korea-specific homework (not legal advice): if you operate
> location-based services as a business in Korea, the **위치정보법**
> (Location Information Act) may require filing a location-based service
> business report (위치기반서비스사업 신고) with the authorities, and
> **개인정보 보호법 (PIPA)** applies to any personal data you hold. Spend
> one hour with a Korean startup lawyer before scaling — it is cheap
> insurance.

**B. Terms of service — minimum viable clauses:** service description
(information service, not an emergency service); the disclaimer below
incorporated; subscription terms (price, renewal, cancellation anytime
effective end of period, refund policy per store/Stripe rules); limitation
of liability to the extent local law allows; governing law
`[대한민국 / your jurisdiction]`; contact email.

**C. The emergency-information disclaimer (must-carry, verbatim):** this
text (already served by the backend in every situation response) must also
appear in both store listings and on the website:

> **산불지킴이는 공식 재난 안내를 보조하는 정보 서비스입니다. 재난문자와
> 119, 지자체의 안내를 항상 우선하여 따라 주세요. 위성 관측에는 시간 지연과
> 한계가 있으며, 이 앱은 긴급구조 서비스가 아닙니다.**
>
> **WildfireGuardian is an information service that supplements official
> emergency channels. Always follow government emergency alerts (재난문자),
> 119, and local-authority instructions first. Satellite observation has
> delays and limitations; this app is not an emergency rescue service.**

---

## §11. Total cost, timeline, and troubleshooting FAQ

### 11.1 Money (verified Aug 2026)

| Item | Cost | Frequency |
|---|---|---|
| GitHub, Netlify, NASA FIRMS key, UptimeRobot | $0 | — |
| Domain | ~US$10–15 | /year |
| Render backend — demo/testing | $0 (free tier) | — |
| Render backend — production (Starter + 1 GB disk) | ~US$7.25 | /month |
| Apple Developer Program | US$99 | /year |
| Google Play Console | US$25 | once |
| Galaxy Store / ONE store registration | $0 | — |
| D-U-N-S (organizations) | $0 (skip paid expediting) | once |
| Stripe | no fixed fee; ~3% + fixed fee per transaction (varies by country) | per sale |
| A Mac, if you own none | from ~US$599 (Mac mini) or rent/borrow | once |
| **Year-one total (have a Mac, individual accounts)** | **≈ US$225–320** | |

Store commissions apply only if/when you sell through store billing
(Phase 2, §6.3): Apple ~15% via the Small Business Program; Play ~15%
(10%+5% model rolling out in US/UK/EEA from June 30, 2026).

### 11.2 Calendar (realistic elapsed time; work ≪ waiting)

| Milestone | Working time | Elapsed time (incl. waits) |
|---|---|---|
| §3–§4 Backend + web live (demo mode) | 3–5 h | same day |
| §3.7 Live fire data (FIRMS key) | 15 min | same day |
| §5 Stripe test → live | 2–4 h | 2–7 days (account review) |
| §2 Apple account (individual) | 1 h | 1–3 days (verification) |
| §2 Apple/Google account (organization) | 2 h | 1–5 weeks (D-U-N-S 5–30 business days) |
| §7 iOS: setup → TestFlight | 4–8 h | 1–3 days |
| §7 iOS: submission → approved | 1–2 h | 1–4 days typical; +1–3 days per rejection round |
| §8 Android: setup → closed test live | 3–6 h | 1–2 days |
| §8.6 Play 14-day test gate + production review (personal acct) | ~1 h | **14 days + ≤7 days review** |
| §8.7 Staged rollout to 100% | minutes | 3–7 days (your choice) |
| **Web product live** | | **~1 day** |
| **App Store live** | | **~1–2 weeks** |
| **Google Play live (new personal account)** | | **~3–5 weeks** |

### 11.3 Troubleshooting FAQ — the top 15 failure modes

**Q1. The web app loads but says it can't reach the server; the browser
console shows a CORS error.**
`WFG_CORS_ORIGINS` on the backend doesn't include the site's exact origin.
It must match scheme+domain exactly (`https://wildfireguardian.app` — no
trailing slash, no path). Native builds need `capacitor://localhost` (iOS)
and `https://localhost` (Android) in the list too (§4.4).

**Q2. The app randomly takes 30–60 s to load data, then works fine.**
Render free tier cold start (§3.1). Upgrade to Starter, at latest during
store review week — reviewers interpret the stall as a broken app.

**Q3. `/v1/health` says `"mode": "demo"` after I set the FIRMS key.**
Check the variable name is exactly `WFG_FIRMS_MAP_KEY`, the value has no
spaces/quotes, and the service redeployed after saving (Render → Events).
`WFG_APP_MODE=demo` left over from testing also forces demo — remove it.

**Q4. Live mode shows no fires and I think it's broken.**
If FIRMS has no detections near that location today, "no active fire" is the
correct, honest answer (§3.7). Test rendering against the demo deployment.
Also confirm you haven't hit FIRMS limits (5,000 transactions/10 min — with
the backend's 60 s cache, effectively impossible unless the key is shared).

**Q5. The PWA won't offer "Add to Home Screen".**
It must be HTTPS (not `http://`), the `manifest.webmanifest` and service
worker must load (Netlify serves them from the build automatically), and on
iPhone it must be **Safari** — Chrome on iOS can't install PWAs.

**Q6. Stripe Checkout returns `billing_not_configured`.**
The backend has no `STRIPE_SECRET_KEY` (§5.2) — by design it degrades to
this answer rather than crashing (`ARCHITECTURE.md` §8). Set all five Stripe
vars.

**Q7. Stripe webhook deliveries show 400 errors.**
Signature mismatch: the `STRIPE_WEBHOOK_SECRET` in Render doesn't match the
endpoint whose deliveries you're viewing — test vs live confusion (§5.8) or
a stale secret after recreating the endpoint. Copy the secret fresh from the
exact endpoint's page.

**Q8. Payments succeed but Plus never unlocks.**
Classic mixed-mode: live `sk_live_…` with **test** `price_…` IDs (or vice
versa), or the webhook still points at a test endpoint. Redo §5.8 step 4 as
one atomic swap. Also check the DB isn't being wiped by free-tier restarts
(§5.8 step 3).

**Q9. `npx cap sync` fails or the native app shows a blank white screen.**
Sync copies `dist/` — run `npm run build` first; a blank screen usually
means the build was made without `VITE_API_BASE` (so the native app calls a
relative URL that doesn't exist) — rebuild with the env var, then re-sync.

**Q10. `pod install` / CocoaPods errors during `npx cap add ios`.**
On a fresh Mac: install via Homebrew (`brew install cocoapods`), then run
`npx cap sync ios` again. Apple-silicon Ruby issues are almost always solved
by the Homebrew route.

**Q11. Xcode: "No profiles for 'kr.wildfireguardian.app' were found."**
Signing isn't set: §7.4 — tick Automatically manage signing and select your
Team. If the bundle ID is taken (rare), you registered it under another
account; use App Store Connect's Identifiers page to check.

**Q12. Apple rejected under 4.2 / 3.1.1 / 5.1.x.**
See the rejection table in §7.12 — each has a specific fix. Reply in
Resolution Center *with the fix described*, don't just resubmit silently.

**Q13. Live updates (SSE) don't arrive on the deployed site, but polling
works.**
Some proxies buffer streams. Render passes SSE through correctly; if you
later front the API with another proxy/CDN, disable buffering for
`/v1/alerts/stream` (e.g. nginx `proxy_buffering off`). The frontend
already falls back to 10 s polling, so this is a degradation, not an
outage.

**Q14. Play Console won't let me publish to production.**
Personal account gate (§2.3/§8.6): 12 testers, 14 *consecutive* days, then
**Apply for production**. Testers dropping to 11 restarts the continuity
requirement — over-recruit to 15–20.

**Q15. Play rejected the Data safety form / listing.**
The form must match reality *and* the privacy policy URL's text: if you
declared "location, not shared", the policy must say the same (§10.5
template does). Update both together and resubmit. For listing rejections,
remove any screenshot or phrase implying government affiliation or
guaranteed emergency coverage.

---

## Appendix: source log (all verified August 2026)

Fees/programs: [Apple Developer Program](https://developer.apple.com/programs/whats-included/) ·
[Apple fee waivers](https://developer.apple.com/help/account/membership/fee-waivers/) ·
[Apple Small Business Program](https://developer.apple.com/app-store/small-business-program/) ·
[Play Console signup](https://support.google.com/googleplay/android-developer/answer/6112435) ·
[Play closed-testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465) ·
[Play account types / D-U-N-S](https://support.google.com/googleplay/android-developer/answer/13634885) ·
[Apple D-U-N-S](https://developer.apple.com/help/account/membership/D-U-N-S/)
Payments policy: [Apple App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) (3.1.1, 3.1.3, 1.4, 5.1.5) ·
[Apple Korea external-purchase entitlement](https://developer.apple.com/support/storekit-external-entitlement-kr) ·
[Google Play expanded billing (June 30, 2026)](https://android-developers.googleblog.com/2026/06/play-expanded-billing.html) ·
[Play service fees](https://support.google.com/googleplay/android-developer/answer/112622)
Stores: [Galaxy Store FAQ](https://developer.samsung.com/galaxy-store/faq.html) ·
[ONE store developer center](https://dev.onestore.net) ·
[ONE store service fees](https://onestore-dev.gitbook.io/dev/docs/payment/service_fee)
Infra: [Render pricing/free tier](https://render.com/docs/free) ·
[Stripe go-live checklist](https://docs.stripe.com/get-started/checklist/go-live) ·
[Stripe global availability](https://stripe.com/global) ·
[NASA FIRMS area API](https://firms.modaps.eosdis.nasa.gov/api/area/) ·
[FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key/)

*This manual contains no research metrics and quotes none in any
user-facing copy, per the project's honesty rules. When demo data is shown
anywhere — screenshots included — it is labelled 연습 모드 / DEMO.*
