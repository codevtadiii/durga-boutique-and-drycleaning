"use client";

import { useEffect, useState } from "react";
import AppHeader from "@/components/app-header";

type Preferences = { whatsapp_order_updates: boolean; whatsapp_marketing: boolean; language: string };

export default function CustomerPreferencesPage() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/v1/customer/notification-preferences")
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Please sign in to manage your preferences."); setPreferences(data); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in to manage your preferences."));
  }, []);

  async function save() {
    if (!preferences) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const response = await fetch("/api/v1/customer/notification-preferences", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preferences),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Your preferences could not be saved.");
      setPreferences(result);
      setNotice("Your preferences have been saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your preferences could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Your choices</p>
        <h1>Choose what<br /><em>you hear from us.</em></h1>
        <p className="page-intro">You can change these choices at any time. Offers and order updates are separate.</p>
        {error && <div className="form-error" role="alert">{error} <a href="/customer/login">Sign in</a></div>}
        {!preferences && !error && <p role="status">Loading preferences...</p>}
        {preferences && <section className="content-card preferences-card">
          <label className="consent-row"><input type="checkbox" checked={preferences.whatsapp_order_updates} onChange={(event) => setPreferences({ ...preferences, whatsapp_order_updates: event.target.checked })} /><span><strong>Order and delivery updates</strong><br />WhatsApp messages about your bookings, order status, delivery dates, and payments.</span></label>
          <label className="consent-row"><input type="checkbox" checked={preferences.whatsapp_marketing} onChange={(event) => setPreferences({ ...preferences, whatsapp_marketing: event.target.checked })} /><span><strong>Occasional offers</strong><br />Optional promotional messages from the shop.</span></label>
          <label className="preference-language">Preferred language<select value={preferences.language} onChange={(event) => setPreferences({ ...preferences, language: event.target.value })}><option value="en">English</option><option value="te">తెలుగు</option></select></label>
          {notice && <p className="form-success" role="status">{notice}</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary" type="button" disabled={busy} onClick={save}>{busy ? "Saving..." : "Save preferences"}</button>
        </section>}
      </main>
    </>
  );
}
