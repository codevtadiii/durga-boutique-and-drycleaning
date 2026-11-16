"use client";

import { FormEvent, useState } from "react";

export default function CustomerRegisterPage() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("en");
  const [updates, setUpdates] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const response = await fetch("/api/v1/auth/customer/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: name, phone, preferred_language: language, whatsapp_order_updates: updates, whatsapp_marketing: marketing }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Your request could not be saved. Please try again.");
      setMessage("Your request is saved. Please visit the shop with your mobile number so staff can verify you and set up your PIN.");
      setName("");
      setPhone("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your request could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="form-page login-page">
      <a className="back-link" href="/customer/login">&larr; Customer sign in</a>
      <div className="login-card register-card">
        <p className="eyebrow"><span className="eyebrow-line" /> A short first step</p>
        <h1>Let us get<br /><em>to know you.</em></h1>
        <p className="login-intro">Share your name and mobile number. Shop staff will verify your identity and set up your private PIN in person.</p>
        <form className="simple-form" onSubmit={submit}>
          <label>Full name<input required autoComplete="name" minLength={2} maxLength={160} value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>Mobile number<input required inputMode="tel" autoComplete="tel" minLength={10} maxLength={20} value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
          <label>Preferred language<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="te">తెలుగు</option></select></label>
          <fieldset className="consent-options"><legend>WhatsApp preferences</legend>
            <label className="checkbox-label"><input type="checkbox" checked={updates} onChange={(event) => setUpdates(event.target.checked)} /> Send me order and delivery updates</label>
            <label className="checkbox-label"><input type="checkbox" checked={marketing} onChange={(event) => setMarketing(event.target.checked)} /> Send me occasional offers</label>
          </fieldset>
          {error && <p className="form-error" role="alert">{error}</p>}
          {message && <p className="form-success" role="status">{message}</p>}
          <button className="button button-primary submit-button" disabled={busy} type="submit">{busy ? "Sending..." : "Ask for an account"}<span aria-hidden="true">&rarr;</span></button>
        </form>
      </div>
    </main>
  );
}
