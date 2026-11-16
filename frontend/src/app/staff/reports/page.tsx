"use client";

import { FormEvent, useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR } from "@/lib/format";

type Summary = {
  finalized_order_value_paise: number; collections_paise: number; refunds_paise: number; expenses_paise: number;
  net_cash_flow_paise: number; outstanding_balance_paise: number; average_order_value_paise: number;
  finalized_orders: number; new_customers: number; returning_customers: number; delayed_orders: number;
};
type ServiceSummary = { service: string; garments: number; finalized_order_value_paise: number };

function localDate(date: Date) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

function reportRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 24 * 60 * 60 * 1000);
  return { from: localDate(start), to: localDate(end) };
}

export default function StaffReportsPage() {
  const initialRange = reportRange();
  const [fromDate, setFromDate] = useState(initialRange.from);
  const [toDate, setToDate] = useState(initialRange.to);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(from = fromDate, to = toDate) {
    setBusy(true); setError("");
    try {
      const query = `from_date=${encodeURIComponent(from)}&to_date=${encodeURIComponent(to)}`;
      const [summaryResponse, serviceResponse] = await Promise.all([
        fetch(`/api/v1/staff/analytics/summary?${query}`),
        fetch(`/api/v1/staff/analytics/services?${query}`),
      ]);
      const summaryData = await summaryResponse.json();
      const serviceData = await serviceResponse.json();
      if (!summaryResponse.ok) throw new Error(summaryData.detail || "The report could not be loaded.");
      if (!serviceResponse.ok) throw new Error(serviceData.detail || "Service totals could not be loaded.");
      setSummary(summaryData); setServices(serviceData);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The report could not be loaded."); }
    finally { setBusy(false); }
  }

  // This effect fetches the initial reporting range; the response updates page state asynchronously.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load(initialRange.from, initialRange.to); }, []);

  function applyRange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load();
  }

  const csvUrl = (report: string) => `/api/v1/staff/reports/${report}.csv?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`;

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Business overview</p>
        <h1>See how the shop<br /><em>is moving.</em></h1>
        <p className="page-intro">A clear view of recorded orders, collections, refunds, expenses, and outstanding balances.</p>
        <form className="report-filter" onSubmit={applyRange}>
          <label>From<input required type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label>
          <label>To<input required type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>
          <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Updating..." : "Update report"}</button>
        </form>
        {error && <div className="form-error" role="alert">{error}</div>}
        {!summary && !error && <p role="status">Loading report...</p>}
        {summary && <>
          <div className="metric-grid report-metrics">
            <article className="metric-card"><span>Finalized order value</span><strong>{formatINR(summary.finalized_order_value_paise)}</strong></article>
            <article className="metric-card"><span>Collections</span><strong>{formatINR(summary.collections_paise)}</strong></article>
            <article className="metric-card"><span>Refunds</span><strong>{formatINR(summary.refunds_paise)}</strong></article>
            <article className="metric-card"><span>Expenses</span><strong>{formatINR(summary.expenses_paise)}</strong></article>
            <article className="metric-card metric-highlight"><span>Net cash flow</span><strong>{formatINR(summary.net_cash_flow_paise)}</strong></article>
            <article className="metric-card"><span>Current outstanding</span><strong>{formatINR(summary.outstanding_balance_paise)}</strong></article>
            <article className="metric-card"><span>Finalized orders</span><strong>{summary.finalized_orders}</strong></article>
            <article className="metric-card"><span>Average order value</span><strong>{formatINR(summary.average_order_value_paise)}</strong></article>
            <article className="metric-card"><span>New customers</span><strong>{summary.new_customers}</strong></article>
            <article className="metric-card"><span>Returning customers</span><strong>{summary.returning_customers}</strong></article>
            <article className="metric-card"><span>Past expected date</span><strong>{summary.delayed_orders}</strong></article>
          </div>
          <section className="content-card report-panel"><h2>Service activity</h2>
            {services.length === 0 ? <p>No finalized service records in this date range.</p> : <div className="record-list">{services.map((item) => <article className="record-card report-service" key={item.service}><strong>{item.service}</strong><span>{item.garments} garments</span><span>{formatINR(item.finalized_order_value_paise)}</span></article>)}</div>}
          </section>
          <section className="content-card report-panel"><h2>Download a CSV</h2><p>Choose a report for the selected date range.</p><div className="dashboard-actions"><a className="quiet-button" href={csvUrl("orders")}>Orders</a><a className="quiet-button" href={csvUrl("collections")}>Collections</a><a className="quiet-button" href={csvUrl("expenses")}>Expenses</a></div></section>
        </>}
      </main>
    </>
  );
}
