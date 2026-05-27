# `delivery` — alert delivery channels

**Status**: scaffold only.

**Purpose**: deliver the routing and exposure information to a real user
through channels they actually receive. For our target population (rural
Koreans aged 60–80) this is dominated by **village PA (마을 방송)** and
**SMS**, not push notifications.

**Inputs**: a list of `(user_id, channel, message_payload)` records emitted
by the routing module.

**Outputs**: best-effort dispatch via configured providers; an audit log of
which messages were sent, when, and through which channel.

**Algorithmic basis**: none beyond message templating and per-channel retry
policies. The interesting decision here is the *prioritisation* — when many
users are at risk simultaneously and channel bandwidth is finite, who do we
notify first? The current design (TBD) sorts by composite risk = burn
probability × estimated exposure × elderly density.
