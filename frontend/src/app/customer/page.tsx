"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppHeader from "@/components/app-header";
import { formatINR } from "@/lib/format";

type Dashboard = {
  total: number; garments: number; in_progress: number; pending: number; ready: number;
  delivered: number; cancelled: number; finalized_order_value_paise: number;
  amount_paid_paise: number; refunds_paise: number; outstanding_balance_paise: number;
};

export default function CustomerDashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/customer/dashboard")
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Please sign in to view your account.");
        setData(result);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in to view your account."));
  }, []);

  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Your account</p>
        <h1>Your clothes,<br /><em>in good hands.</em></h1>
        <p className="page-intro">A clear view of your orders, garments, and payments.</p>
        <div className="dashboard-actions">
          <Link className="button button-primary" href="/booking">Book a service <span aria-hidden="true">&rarr;</span></Link>
          <Link className="text-link" href="/customer/orders">View all orders</Link>
        </div>
        {error && <div className="form-error" role="alert">{error} <a href="/customer/login">Sign in</a></div>}
        {!data && !error && <p role="status">Loading your account...</p>}
        {data && <>
          <div className="metric-grid" aria-label="Your order summary">
            <article className="metric-card"><span>Total orders</span><strong>{data.total}</strong></article>
            <article className="metric-card"><span>Garments submitted</span><strong>{data.garments}</strong></article>
            <article className="metric-card"><span>In progress</span><strong>{data.in_progress}</strong></article>
            <article className="metric-card"><span>Ready for collection</span><strong>{data.ready}</strong></article>
            <article className="metric-card"><span>Pending requests</span><strong>{data.pending}</strong></article>
            <article className="metric-card"><span>Delivered</span><strong>{data.delivered}</strong></article>
            <article className="metric-card"><span>Total paid</span><strong>{formatINR(data.amount_paid_paise)}</strong></article>
            <article className="metric-card metric-highlight"><span>Remaining balance</span><strong>{formatINR(data.outstanding_balance_paise)}</strong></article>
          </div>
          <section className="content-card">
            <h2>Your payments</h2>
            <p>Final order value {formatINR(data.finalized_order_value_paise)} · Refunds {formatINR(data.refunds_paise)}</p>
            <a className="record-link" href="/customer/payments">See payment history &rarr;</a>
          </section>
        </>}
      </main>
    </>
  );
}
