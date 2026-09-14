import { useEffect, useState } from "react";
import { ApiError, postCheckout, type BillingPlan } from "../api/client";
import { IconCheck, IconPhone } from "../components/Icons";
import { useI18n } from "../i18n";
import { getPref, setPref, type FamilyContact } from "../lib/prefs";

/**
 * Family (Guardian Plus). Honesty first: every life-safety feature is free
 * forever (spec §1.1) — the paid tier is convenience only, and the screen
 * says so before any subscribe button. Family phone numbers live ONLY in
 * this device's localStorage.
 */
export function FamilyScreen() {
  const { t, pick } = useI18n();
  const [contacts, setContacts] = useState<FamilyContact[]>(
    () => getPref("family") ?? [],
  );
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState<BillingPlan | null>(null);
  const [billingNotice, setBillingNotice] = useState<{
    kind: "ok" | "warn";
    text: string;
  } | null>(null);

  // Returning from Stripe Checkout (?billing=success|cancel).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const billing = params.get("billing");
    if (billing === "success") {
      setBillingNotice({ kind: "ok", text: t("billing_success") });
    } else if (billing === "cancel") {
      setBillingNotice({ kind: "warn", text: t("billing_cancelled") });
    }
    if (billing) {
      params.delete("billing");
      const rest = params.toString();
      window.history.replaceState(
        null,
        "",
        window.location.pathname + (rest ? `?${rest}` : ""),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveContacts = (next: FamilyContact[]) => {
    setContacts(next);
    setPref("family", next);
  };

  const addContact = () => {
    const n = name.trim();
    const p = phone.trim();
    if (!n || !p) return;
    saveContacts([...contacts, { name: n, phone: p }]);
    setName("");
    setPhone("");
  };

  const subscribe = async (plan: BillingPlan) => {
    setBusy(plan);
    setBillingNotice(null);
    try {
      const origin = window.location.origin;
      const res = await postCheckout({
        plan,
        success_url: `${origin}/?billing=success`,
        cancel_url: `${origin}/?billing=cancel`,
      });
      setBillingNotice({ kind: "ok", text: t("billing_redirecting") });
      window.location.href = res.checkout_url;
    } catch (e) {
      if (e instanceof ApiError && e.code === "billing_not_configured") {
        setBillingNotice({ kind: "warn", text: t("billing_not_configured") });
      } else if (e instanceof ApiError && e.body) {
        setBillingNotice({
          kind: "warn",
          text: pick(e.body, "detail") || t("error_title"),
        });
      } else {
        setBillingNotice({ kind: "warn", text: t("error_title") });
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="screen-pad">
      <h1 className="section-title">{t("family_title")}</h1>

      {/* what is free — stated first, plainly */}
      <section className="card" style={{ borderColor: "var(--safe)" }}>
        <h2 className="card-title" style={{ color: "var(--safe)" }}>
          {t("free_title")}
        </h2>
        <p className="card-body">{t("free_note")}</p>
        <ul className="check-list">
          {[t("free_1"), t("free_2"), t("free_3"), t("free_4")].map((item) => (
            <li key={item}>
              <span className="mark" style={{ color: "var(--safe)" }}>
                <IconCheck size={24} />
              </span>
              {item}
            </li>
          ))}
        </ul>
      </section>

      {/* what Plus adds — convenience, honestly labelled */}
      <section className="card">
        <h2 className="card-title">
          {t("plus_name")} — {t("plus_title")}
        </h2>
        <p className="card-body">{t("plus_note")}</p>
        <ul className="check-list">
          {[t("plus_1"), t("plus_2"), t("plus_3"), t("plus_4")].map((item) => (
            <li key={item}>
              <span className="mark" style={{ color: "var(--viz-deep)" }}>
                <IconCheck size={24} />
              </span>
              {item}
            </li>
          ))}
        </ul>
        <div className="row wrap" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="btn-big-secondary"
            style={{ flex: 1 }}
            disabled={busy !== null}
            onClick={() => void subscribe("monthly")}
          >
            {busy === "monthly" ? "…" : t("subscribe_monthly")}
          </button>
          <button
            type="button"
            className="btn-big-secondary"
            style={{ flex: 1 }}
            disabled={busy !== null}
            onClick={() => void subscribe("yearly")}
          >
            {busy === "yearly" ? "…" : t("subscribe_yearly")}
          </button>
        </div>
      </section>

      {billingNotice && (
        <p className={`notice${billingNotice.kind === "ok" ? " ok" : ""}`} role="status">
          {billingNotice.text}
        </p>
      )}

      {/* local family phone list */}
      <section className="card">
        <h2 className="card-title">{t("fam_list_title")}</h2>
        <p
          className="card-body"
          style={{ color: "var(--ink-secondary)", fontSize: "var(--fs-small)" }}
        >
          {t("fam_note")}
        </p>
        {contacts.length === 0 && (
          <p className="card-body">{t("fam_empty")}</p>
        )}
        {contacts.map((c, i) => (
          <div
            key={`${c.phone}-${i}`}
            className="row"
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: "1px solid var(--hairline)",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 800 }}>{c.name}</div>
              <div style={{ color: "var(--ink-secondary)" }}>{c.phone}</div>
            </div>
            <a
              className="btn-pill"
              href={`tel:${c.phone}`}
              style={{
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <IconPhone size={24} />
              {t("fam_call")}
            </a>
            <button
              type="button"
              className="btn-pill"
              onClick={() => saveContacts(contacts.filter((_, j) => j !== i))}
            >
              {t("fam_remove")}
            </button>
          </div>
        ))}
        <label className="field-label" htmlFor="fam-name">
          {t("fam_name_ph")}
        </label>
        <input
          id="fam-name"
          className="text-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />
        <label className="field-label" htmlFor="fam-phone">
          {t("fam_phone_ph")}
        </label>
        <input
          id="fam-phone"
          className="text-input"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          inputMode="tel"
          autoComplete="tel"
        />
        <button
          type="button"
          className="btn-big-secondary"
          style={{ width: "100%", marginTop: 16 }}
          onClick={addContact}
        >
          {t("fam_add")}
        </button>
      </section>
    </div>
  );
}
