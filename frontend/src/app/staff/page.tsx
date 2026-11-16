"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppHeader from "@/components/app-header";
import { formatShopDate, readableStatus, statusClass } from "@/lib/format";

type Order = { id: string; order_number: string; customer_name: string; phone: string; status: string; expected_delivery_at: string | null; is_delayed: boolean; created_at: string };

export default function StaffDashboardPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/v1/staff/orders")
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Please sign in with a staff account."); setOrders(data); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in with a staff account."));
  }, []);
  const pending = orders?.filter((item) => ["booking_received", "awaiting_verification", "awaiting_customer_approval"].includes(item.status)).length ?? 0;
  const processing = orders?.filter((item) => ["order_confirmed", "received_at_shop", "processing", "quality_check", "out_for_delivery"].includes(item.status)).length ?? 0;
  const ready = orders?.filter((item) => item.status === "ready_for_collection").length ?? 0;
  const delayed = orders?.filter((item) => item.is_delayed).length ?? 0;

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Shop work desk</p>
        <h1>Good work starts<br /><em>with a clear queue.</em></h1>
        <p className="page-intro">Check recent orders, see what needs attention, and keep each customer updated.</p>
        {error && <div className="form-error" role="alert">{error} <a href="/staff/login">Staff sign in</a></div>}
        {orders && <>
          <div className="metric-grid">
            <article className="metric-card"><span>Needs attention</span><strong>{pending}</strong></article>
            <article className="metric-card"><span>In progress</span><strong>{processing}</strong></article>
            <article className="metric-card"><span>Ready</span><strong>{ready}</strong></article>
            <article className="metric-card metric-highlight"><span>Past expected date</span><strong>{delayed}</strong></article>
          </div>
          <div className="dashboard-actions"><Link className="button button-primary" href="/staff/orders">Open order queue <span aria-hidden="true">&rarr;</span></Link><Link className="text-link" href="/staff/closing">Daily closing</Link></div>
          <section><h2 className="section-title-small">Recent orders</h2>
            <div className="record-list">{orders.slice(0, 6).map((order) => <article className="record-card" key={order.id}>
              <div className="record-top"><div><h2>{order.order_number}</h2><p>{order.customer_name} · {order.phone}</p></div><span className={`status-pill ${order.is_delayed ? "status-delayed" : statusClass(order.status)}`}>{order.is_delayed ? "Past expected date" : readableStatus(order.status)}</span></div>
              <p>Expected: {formatShopDate(order.expected_delivery_at)}</p>
              <a className="record-link" href={`/staff/orders/${order.id}`}>Open order <span aria-hidden="true">&rarr;</span></a>
            </article>)}</div>
          </section>
        </>}
        {!orders && !error && <p role="status">Loading recent orders...</p>}
      </main>
    </>
  );
}
