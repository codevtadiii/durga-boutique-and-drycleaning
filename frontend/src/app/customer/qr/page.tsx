"use client";

import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import AppHeader from "@/components/app-header";

export default function CustomerQrPage() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createQr() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/customer/qr", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Please sign in again and try once more.");
      setValue(result.qr_value);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Quick shop lookup</p>
        <h1>Your customer<br /><em>QR code.</em></h1>
        <p className="page-intro">Show this to shop staff so they can find your customer profile quickly. This code is for staff lookup only; it is not a sign-in code.</p>
        <section className="qr-card" aria-live="polite">
          {value ? <QRCodeSVG value={value} size={236} level="M" marginSize={4} title="Your Durga customer lookup QR code" /> : <div className="qr-placeholder" aria-hidden="true">D</div>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary" type="button" onClick={createQr} disabled={busy}>{busy ? "Creating code..." : value ? "Refresh my QR code" : "Show my QR code"}</button>
          <p className="form-footnote">Refreshing the code revokes the previous one.</p>
        </section>
      </main>
    </>
  );
}
