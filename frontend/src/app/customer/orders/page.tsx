"use client";

import { useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR, formatShopDate, readableStatus, statusClass } from "@/lib/format";

type Order = {
  id: string; order_number: string; status: string; expected_delivery_at: string | null;
  proposed_delivery_at: string | null; proposed_total_paise: number | null; confirmed_total_paise: number | null;
  garments: { id: string }[];
};

export default function CustomerOrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/customer/orders")
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Please sign in to view your orders.");
        setOrders(result);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in to view your orders."));
  }, []);

  return (
    <>
      <AppHeader audience="customer" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Your order history</p>
        <h1>Every order,<br /><em>easy to follow.</em></h1>
        <p className="page-intro">See the status, garment count, expected date, and confirmed price for each order.</p>
        {error && <div className="form-error" role="alert">{error} <a href="/customer/login">Sign in</a></div>}
        {!orders && !error && <p role="status">Loading your orders...</p>}
        {orders?.length === 0 && <div className="empty-state">There are no orders on this account yet. <a className="record-link" href="/booking">Book a service</a></div>}
        {orders && orders.length > 0 && <div className="record-list">
          {orders.map((order) => <article className="record-card" key={order.id}>
            <div className="record-top"><div><h2>{order.order_number}</h2><p>{order.garments.length} garments</p></div><span className={`status-pill ${statusClass(order.status)}`}>{readableStatus(order.status)}</span></div>
            <p>Expected date: {formatShopDate(order.expected_delivery_at)}</p>
            {order.proposed_delivery_at && <p>Proposed revised date: {formatShopDate(order.proposed_delivery_at)}</p>}
            <p>Confirmed price: {order.confirmed_total_paise == null ? "Waiting for confirmation" : formatINR(order.confirmed_total_paise)}</p>
            <a className="record-link" href={`/customer/orders/${order.id}`}>View order <span aria-hidden="true">&rarr;</span></a>
          </article>)}
        </div>}
      </main>
    </>
  );
}
