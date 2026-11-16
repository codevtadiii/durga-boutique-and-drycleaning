"use client";

import { FormEvent, useState } from "react";

export default function PhonePinForm({ audience }: { audience: "customer" | "staff" }) {
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const route = audience === "customer" ? "customer/pin/login" : "staff/pin/login";
      const response = await fetch(`/api/v1/auth/${route}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, pin }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "We could not sign you in. Check your details and try again.");
      window.location.assign(audience === "customer" ? "/customer" : "/staff");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not sign you in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="simple-form" onSubmit={submit}>
      <label>Mobile number<input required inputMode="tel" autoComplete="tel" minLength={10} maxLength={20} value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
      <label>6 to 12 digit PIN<input required inputMode="numeric" autoComplete="current-password" minLength={6} maxLength={12} pattern="[0-9]{6,12}" type="password" value={pin} onChange={(event) => setPin(event.target.value)} /></label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="button button-primary submit-button" disabled={busy} type="submit">{busy ? "Signing in..." : "Sign in"}<span aria-hidden="true">&rarr;</span></button>
    </form>
  );
}
