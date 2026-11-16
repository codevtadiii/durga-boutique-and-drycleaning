"use client";

import { useParams } from "next/navigation";
import Image from "next/image";
import { useEffect, useState } from "react";
import Link from "next/link";
import AppHeader from "@/components/app-header";
import { formatINR, formatShopDate, readableStatus, statusClass } from "@/lib/format";

type OrderDetail = {
  id: string; order_number: string; status: string; expected_delivery_at: string | null;
  proposed_delivery_at: string | null; proposed_total_paise: number | null; confirmed_total_paise: number | null;
  delivery_date_pending_approval: boolean;
  garments: { id: string; type: string; service: string; quantity: number; unit_price_paise: number | null; line_total_paise: number | null; pricing_unit: string; price_paise: number | null; fabric: string | null; colour: string | null; condition_notes: string | null; special_instructions: string | null; status: string; photos: string[] }[];
  timeline: { status: string; note: string | null; at: string }[];
};

export default function CustomerOrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const response = await fetch(`/api/v1/customer/orders/${orderId}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Please sign in to view this order.");
    setOrder(result);
  }

  // This effect fetches the selected order; the response updates page state asynchronously.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load order.")); }, [orderId]);

  async function decide(decision: "approved" | "rejected") {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/v1/customer/orders/${orderId}/approvals`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Your choice could not be saved.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your choice could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <Link className="back-link" href="/customer/orders">&larr; All orders</Link>
        {error && <div className="form-error" role="alert">{error} <a href="/customer/login">Sign in</a></div>}
        {!order && !error && <p role="status">Loading order...</p>}
        {order && <>
          <p className="eyebrow"><span className="eyebrow-line" /> Order details</p>
          <h1>{order.order_number}</h1>
          <span className={`status-pill ${statusClass(order.status)}`}>{readableStatus(order.status)}</span>
          <div className="metric-grid">
            <article className="metric-card"><span>Garments</span><strong>{order.garments.reduce((total, garment) => total + garment.quantity, 0)}</strong></article>
            <article className="metric-card"><span>Expected date</span><strong className="metric-date">{formatShopDate(order.expected_delivery_at)}</strong></article>
            <article className="metric-card"><span>Confirmed price</span><strong>{order.confirmed_total_paise == null ? "Pending" : formatINR(order.confirmed_total_paise)}</strong></article>
          </div>
          {order.proposed_total_paise != null && order.proposed_delivery_at && (
            <section className="approval-card">
              <p className="eyebrow"><span className="eyebrow-line" /> Please review</p>
              <h2>{order.delivery_date_pending_approval ? "A revised date is proposed" : "Confirm your order"}</h2>
              <p>Proposed total: <strong>{formatINR(order.proposed_total_paise)}</strong></p>
              <p>Proposed date: <strong>{formatShopDate(order.proposed_delivery_at)}</strong></p>
              <p>Work starts after you approve the confirmed price and expected date.</p>
              {error && <p className="form-error" role="alert">{error}</p>}
              <div className="dashboard-actions"><button className="button button-primary" disabled={busy} onClick={() => decide("approved")} type="button">Approve price and date</button><button className="quiet-button" disabled={busy} onClick={() => decide("rejected")} type="button">Ask the shop to review</button></div>
            </section>
          )}
          <section className="content-card"><h2>Garments</h2>
            {order.garments.map((garment, index) => <article className="garment-row" key={garment.id}>
              <div><strong>{index + 1}. {garment.type}</strong><p>Service: {garment.service} · Quantity: {garment.quantity}</p><p>{garment.unit_price_paise == null ? "Awaiting staff quotation" : `Unit price: ${formatINR(garment.unit_price_paise)} ${garment.pricing_unit} · Line subtotal: ${formatINR(garment.line_total_paise ?? garment.price_paise ?? 0)}`}</p><p>{[garment.fabric, garment.colour].filter(Boolean).join(" · ") || "Garment details recorded at the shop"}</p>{garment.condition_notes && <p>Condition: {garment.condition_notes}</p>}{garment.special_instructions && <p>Instructions: {garment.special_instructions}</p>}</div>
              <div className="photo-strip">{garment.photos.map((photoId) => <Image key={photoId} className="photo-thumb" width={180} height={180} unoptimized src={`/api/v1/customer/orders/${order.id}/garments/${garment.id}/photos/${photoId}`} alt={`Intake photo of ${garment.type}`} />)}</div>
            </article>)}
          </section>
          <section className="content-card"><h2>Order timeline</h2>
            <ol className="timeline">{order.timeline.map((item, index) => <li key={`${item.at}-${index}`}><span className="timeline-dot" /><div><strong>{readableStatus(item.status)}</strong><p>{item.note || "Order updated"}</p><time dateTime={item.at}>{formatShopDate(item.at)}</time></div></li>)}</ol>
          </section>
        </>}
      </main>
    </>
  );
}
