"use client";

import { useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR, formatShopDate } from "@/lib/format";

type Payment = { id: string; method: string; status: string; amount_paise: number; transaction_reference: string | null; paid_at: string };

export default function CustomerPaymentsPage() {
  const [payments, setPayments] = useState<Payment[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/v1/customer/payments")
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Please sign in to view your payments."); setPayments(data); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in to view your payments."));
  }, []);
  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Payment history</p>
        <h1>Simple, clear<br /><em>payment records.</em></h1>
        <p className="page-intro">Each payment is listed with its date, method, amount, and reference when available.</p>
        {error && <div className="form-error" role="alert">{error} <a href="/customer/login">Sign in</a></div>}
        {!payments && !error && <p role="status">Loading payments...</p>}
        {payments?.length === 0 && <div className="empty-state">No payments are recorded yet.</div>}
        {payments && payments.length > 0 && <div className="record-list">{payments.map((payment) => <article className="record-card" key={payment.id}>
          <div className="record-top"><div><h2>{formatINR(payment.amount_paise)}</h2><p>{formatShopDate(payment.paid_at)}</p></div><span className="status-pill status-ready">{payment.status}</span></div>
          <p>Method: {payment.method.replaceAll("_", " ")}</p>
          {payment.transaction_reference && <p>Reference: {payment.transaction_reference}</p>}
        </article>)}</div>}
      </main>
    </>
  );
}
