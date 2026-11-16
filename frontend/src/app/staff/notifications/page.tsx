"use client";

import { useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatShopDate, readableStatus } from "@/lib/format";

type Notice = { id: string; order_id: string | null; order_number: string | null; event_type: string; channel: string; state: string; created_at: string };

export default function StaffNotificationsPage() {
  const [items, setItems] = useState<Notice[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  async function load() {
    const response = await fetch("/api/v1/staff/notifications");
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Please sign in with a staff account.");
    setItems(result);
  }

  // This effect fetches notification records; the response updates page state asynchronously.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load updates.")); }, []);

  async function sendDraft(item: Notice) {
    if (!item.order_id) return;
    setBusyId(item.id);
    setError("");
    try {
      const response = await fetch(`/api/v1/staff/orders/${item.order_id}/whatsapp-draft`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notification_id: item.id }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "A WhatsApp draft is unavailable for this update.");
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not prepare this message."); }
    finally { setBusyId(""); }
  }

  async function markSent(id: string) {
    setBusyId(id);
    setError("");
    try {
      const response = await fetch(`/api/v1/staff/notifications/${id}/manual-sent`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "This update could not be marked as sent.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update this message."); }
    finally { setBusyId(""); }
  }

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Customer updates</p>
        <h1>Stay on top<br /><em>of every promise.</em></h1>
        <p className="page-intro">WhatsApp stays manual until the official integration is configured. Opening a draft does not mark it sent or delivered.</p>
        {error && <div className="form-error" role="alert">{error}</div>}
        {items.length === 0 && <div className="empty-state">No reminders or updates are waiting right now.</div>}
        <div className="record-list">{items.map((item) => <article className="record-card" key={item.id}>
          <div className="record-top"><div><h2>{item.order_number || "Shop alert"}</h2><p>{readableStatus(item.event_type)} · {formatShopDate(item.created_at)}</p></div><span className={`status-pill ${item.state === "manual_required" ? "status-pending" : ""}`}>{readableStatus(item.state)}</span></div>
          {item.state === "customer_opted_out" && <p>Customer has not opted in to WhatsApp order updates. Do not send a message.</p>}
          {item.state === "manual_required" && item.order_id && <div className="dashboard-actions"><button className="button button-primary" type="button" disabled={busyId === item.id} onClick={() => sendDraft(item)}>Open WhatsApp draft</button><button className="quiet-button" type="button" disabled={busyId === item.id} onClick={() => markSent(item.id)}>I sent this message</button></div>}
          {item.state === "manually_sent" && <p>Staff marked the message sent. Delivery was not independently confirmed.</p>}
          {item.order_id && <a className="record-link" href={`/staff/orders/${item.order_id}`}>View order</a>}
        </article>)}</div>
      </main>
    </>
  );
}
