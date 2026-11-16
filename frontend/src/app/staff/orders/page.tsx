"use client";

import { FormEvent, useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatShopDate, readableStatus, statusClass } from "@/lib/format";

type Order = { id: string; order_number: string; customer_name: string; phone: string; status: string; expected_delivery_at: string | null; is_delayed: boolean };
type Customer = { id: string; full_name: string; phone: string; preferred_language: string };

export default function StaffOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [delayedOnly, setDelayedOnly] = useState(false);
  const [qrValue, setQrValue] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [error, setError] = useState("");

  async function loadOrders(search = query, status = statusFilter, overdue = delayedOnly) {
    const params = new URLSearchParams();
    if (search.trim()) params.set("query", search.trim());
    if (status) params.set("status", status);
    if (overdue) params.set("delayed_only", "true");
    const queryString = params.toString();
    const url = queryString ? `/api/v1/staff/orders?${queryString}` : "/api/v1/staff/orders";
    const response = await fetch(url);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Please sign in with a staff account.");
    setOrders(result);
  }

  // The fetch completes asynchronously and its result is the external source for this page's state.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { loadOrders().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load orders.")); }, []);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try { await loadOrders(query, statusFilter, delayedOnly); } catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed."); }
  }

  async function resolveQr(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setCustomer(null);
    try {
      const response = await fetch("/api/v1/staff/customer-qr/resolve", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ qr_value: qrValue }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "This QR code could not be looked up.");
      setCustomer(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "This QR code could not be looked up."); }
  }

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Order work queue</p>
        <h1>Find the order.<br /><em>Keep it moving.</em></h1>
        <form className="search-row" onSubmit={search}><label className="sr-only" htmlFor="order-search">Search orders by number or customer mobile</label><input id="order-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Order number or mobile number" /><button className="button button-primary" type="submit">Apply filters</button></form>
        <div className="form-two-column order-filters"><label>Order status<select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); loadOrders(query, event.target.value, delayedOnly).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load orders.")); }}><option value="">All statuses</option><option value="booking_received">Booking received</option><option value="awaiting_verification">Awaiting verification</option><option value="awaiting_customer_approval">Awaiting customer approval</option><option value="order_confirmed">Order confirmed</option><option value="received_at_shop">Received at shop</option><option value="processing">Processing</option><option value="quality_check">Quality check</option><option value="ready_for_collection">Ready for collection</option><option value="out_for_delivery">Out for delivery</option><option value="delivered">Delivered</option><option value="cancelled">Cancelled</option></select></label><label className="checkbox-label"><input type="checkbox" checked={delayedOnly} onChange={(event) => { setDelayedOnly(event.target.checked); loadOrders(query, statusFilter, event.target.checked).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load orders.")); }} /> Past expected delivery date</label></div>
        <section className="content-card qr-lookup">
          <h2>Quick customer lookup</h2>
          <p>Scan a Durga customer QR with your device or scanner, then paste the code here. The QR is for staff lookup only.</p>
          <form className="search-row" onSubmit={resolveQr}><label className="sr-only" htmlFor="customer-qr">Customer QR value</label><input id="customer-qr" value={qrValue} onChange={(event) => setQrValue(event.target.value)} placeholder="durga-customer:..." /><button className="button button-primary" type="submit">Find customer</button></form>
          {customer && <div className="customer-result"><strong>{customer.full_name}</strong><span>{customer.phone}</span><span>Language: {customer.preferred_language === "te" ? "Telugu" : "English"}</span></div>}
        </section>
        {error && <div className="form-error" role="alert">{error} <a href="/staff/login">Staff sign in</a></div>}
        <div className="record-list">{orders.map((order) => <article className="record-card" key={order.id}>
          <div className="record-top"><div><h2>{order.order_number}</h2><p>{order.customer_name} · {order.phone}</p></div><span className={`status-pill ${order.is_delayed ? "status-delayed" : statusClass(order.status)}`}>{order.is_delayed ? "Past expected date" : readableStatus(order.status)}</span></div>
          <p>Expected date: {formatShopDate(order.expected_delivery_at)}</p>
          <a className="record-link" href={`/staff/orders/${order.id}`}>Open order <span aria-hidden="true">&rarr;</span></a>
        </article>)}</div>
        {orders.length === 0 && <div className="empty-state">No orders match this search.</div>}
      </main>
    </>
  );
}
