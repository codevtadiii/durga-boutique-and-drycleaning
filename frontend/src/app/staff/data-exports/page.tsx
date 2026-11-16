"use client";

import { useState } from "react";
import AppHeader from "@/components/app-header";

type ExportResult = { id: string; download_url: string; expires_at: string; tables: number; media_files: number; size_bytes: number };

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DataExportsPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExportResult | null>(null);

  async function createExport() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/api/v1/staff/data-exports", { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Sign in as the owner to create a data export.");
      setResult(payload);
      window.location.assign(payload.download_url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The data export could not be created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Owner tools</p>
        <h1>Keep a copy<br /><em>of your records.</em></h1>
        <p className="page-intro">Create a private archive of your business data and intake photos. You can download it for safekeeping if you change hosting later.</p>
        <section className="content-card export-card">
          <h2>What’s included</h2>
          <ul>
            <li>Application database tables saved as UTF-8 JSON, with session rows omitted and credential hashes redacted</li>
            <li>Private garment intake photos and other media files</li>
            <li>A manifest listing the exported tables, files, and expiry date</li>
          </ul>
          <p className="export-sensitive">This archive contains customer names, phone numbers, order details, photos, and financial records. Store it somewhere only the owner can access.</p>
          <button className="button button-primary" type="button" disabled={busy} onClick={createExport}>
            {busy ? "Preparing your archive…" : "Create and download archive"}
          </button>
          {error && <p className="form-error export-message" role="alert">{error}</p>}
          {result && <p className="form-success export-message" role="status">Archive ready: {result.tables} data tables, {result.media_files} media files, {formatSize(result.size_bytes)}. The server copy expires after seven days.</p>}
          <p className="form-footnote">The download is available on this server for seven days. The archive is a data export; a reviewed restore procedure is still needed to import it into a database.</p>
        </section>
      </main>
    </>
  );
}
