"use client";

import { FormEvent, useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR, formatShopDate, readableStatus } from "@/lib/format";

type PaymentOrder = { order_id: string; order_number: string; status: string; finalized_order_value_paise: number; outstanding_balance_paise: number };
type Refund = { id: string; amount_paise: number; method: string; reason: string; refunded_at: string };
type Payment = { id: string; method: string; status: string; amount_paise: number; transaction_reference: string | null; paid_at: string; refunds: Refund[] };
type Balance = { finalized_order_value_paise: number; collections_paise: number; refunds_paise: number; outstanding_balance_paise: number };
type Category = { id: string; name: string };
type Expense = { id: string; category_id: string; amount_paise: number; description: string | null; spent_at: string };

const methods = ["cash", "upi", "card", "bank_transfer", "other"];
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());

export default function FinancePage() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<PaymentOrder[]>([]);
  const [selected, setSelected] = useState<PaymentOrder | null>(null);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [categoryName, setCategoryName] = useState("");
  const [expenseCategory, setExpenseCategory] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("");
  const [expenseDescription, setExpenseDescription] = useState("");
  const [expenseDate, setExpenseDate] = useState(today());
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [paymentReference, setPaymentReference] = useState("");
  const [paymentKey, setPaymentKey] = useState("");
  const [refundPaymentId, setRefundPaymentId] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundMethod, setRefundMethod] = useState("cash");
  const [refundReason, setRefundReason] = useState("");
  const [refundKey, setRefundKey] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const canRecordPayments = permissions.includes("payment:record");
  const canRefund = permissions.includes("refund:record");
  const canManageExpenses = permissions.includes("expense:write");

  async function jsonRequest(url: string, init?: RequestInit) {
    const response = await fetch(url, init);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "This request could not be completed.");
    return result;
  }

  async function loadSupportData() {
    const session = await jsonRequest("/api/v1/auth/session");
    setPermissions(session.permissions || []);
    const [categoryRows, expenseRows] = await Promise.all([
      jsonRequest("/api/v1/staff/expense-categories"),
      jsonRequest("/api/v1/staff/expenses"),
    ]);
    setCategories(categoryRows);
    setExpenses(expenseRows);
    setExpenseCategory((current) => current || categoryRows[0]?.id || "");
  }

  // This effect loads lookup data from the API; its response updates page state asynchronously.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { loadSupportData().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please sign in with a finance-enabled account.")); }, []);

  async function searchOrders(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice(""); setSelected(null); setBalance(null); setPayments([]);
    try {
      const result = await jsonRequest(`/api/v1/staff/payment-orders?query=${encodeURIComponent(query)}`);
      setMatches(result);
      if (!result.length) setNotice("No confirmed orders matched that order number.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Order search failed."); }
  }

  async function chooseOrder(order: PaymentOrder) {
    setSelected(order); setError(""); setNotice(""); setBusy(true);
    try {
      const [balanceResult, paymentRows] = await Promise.all([
        jsonRequest(`/api/v1/staff/orders/${order.order_id}/balance`),
        jsonRequest(`/api/v1/staff/orders/${order.order_id}/payments`),
      ]);
      const updatedOrder = { ...order, ...balanceResult };
      setSelected(updatedOrder);
      setMatches((current) => current.map((item) => item.order_id === order.order_id ? { ...item, ...balanceResult } : item));
      setBalance(balanceResult); setPayments(paymentRows);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Order payment details could not be loaded."); }
    finally { setBusy(false); }
  }

  async function savePayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(""); setNotice("");
    const requestKey = paymentKey || crypto.randomUUID();
    setPaymentKey(requestKey);
    try {
      await jsonRequest(`/api/v1/staff/orders/${selected.order_id}/payments`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_paise: Math.round(Number(paymentAmount) * 100), idempotency_key: requestKey, method: paymentMethod, transaction_reference: paymentReference || null }),
      });
      setNotice("Payment recorded."); setPaymentAmount(""); setPaymentReference(""); setPaymentKey("");
      await chooseOrder(selected);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Payment could not be recorded. You can retry without changing its details."); }
    finally { setBusy(false); }
  }

  async function saveRefund(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !refundPaymentId) return;
    setBusy(true); setError(""); setNotice("");
    const requestKey = refundKey || crypto.randomUUID();
    setRefundKey(requestKey);
    try {
      await jsonRequest(`/api/v1/staff/orders/${selected.order_id}/payments/${refundPaymentId}/refunds`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_paise: Math.round(Number(refundAmount) * 100), idempotency_key: requestKey, method: refundMethod, reason: refundReason }),
      });
      setNotice("Refund recorded."); setRefundPaymentId(""); setRefundAmount(""); setRefundReason(""); setRefundKey("");
      await chooseOrder(selected);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Refund could not be recorded. You can retry without changing its details."); }
    finally { setBusy(false); }
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await jsonRequest("/api/v1/staff/expense-categories", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: categoryName }) });
      setCategoryName(""); setNotice("Expense category added."); await loadSupportData(); setExpenseCategory(result.id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Category could not be saved."); }
    finally { setBusy(false); }
  }

  async function saveExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await jsonRequest("/api/v1/staff/expenses", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id: expenseCategory, amount_paise: Math.round(Number(expenseAmount) * 100), description: expenseDescription || null, spent_at: new Date(`${expenseDate}T12:00:00+05:30`).toISOString() }),
      });
      setExpenseAmount(""); setExpenseDescription(""); setNotice("Expense recorded."); await loadSupportData();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Expense could not be recorded."); }
    finally { setBusy(false); }
  }

  const categoryNames = new Map(categories.map((category) => [category.id, category.name]));
  const refundPayment = payments.find((payment) => payment.id === refundPaymentId);
  const refundRemainingPaise = refundPayment ? refundPayment.amount_paise - refundPayment.refunds.reduce((sum, refund) => sum + refund.amount_paise, 0) : 0;

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Shop accounts</p>
        <h1>Keep each rupee<br /><em>easy to follow.</em></h1>
        <p className="page-intro">Record cash and digital payments against an order, track expenses, and keep daily closing accurate.</p>
        {error && <div className="form-error" role="alert">{error}</div>}
        {notice && <div className="form-success" role="status">{notice}</div>}
        <section className="content-card finance-panel">
          <h2>Find a confirmed order</h2>
          <form className="search-row" onSubmit={searchOrders}><label className="sr-only" htmlFor="payment-order-search">Search by order number</label><input id="payment-order-search" required minLength={3} maxLength={24} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Enter part of an order number" /><button className="button button-primary" type="submit">Search</button></form>
          {matches.map((order) => <button key={order.order_id} className={`customer-choice ${selected?.order_id === order.order_id ? "selected" : ""}`} type="button" onClick={() => chooseOrder(order)}><strong>{order.order_number}</strong><span>{readableStatus(order.status)} · Due {formatINR(order.outstanding_balance_paise)}</span></button>)}
        </section>
        {selected && balance && <section className="content-card finance-panel">
          <p className="eyebrow"><span className="eyebrow-line" /> {selected.order_number}</p>
          <div className="metric-grid"><article className="metric-card"><span>Order value</span><strong>{formatINR(balance.finalized_order_value_paise)}</strong></article><article className="metric-card"><span>Collected</span><strong>{formatINR(balance.collections_paise)}</strong></article><article className="metric-card"><span>Refunded</span><strong>{formatINR(balance.refunds_paise)}</strong></article><article className="metric-card metric-highlight"><span>Still due</span><strong>{formatINR(balance.outstanding_balance_paise)}</strong></article></div>
          {payments.map((payment) => <article className="finance-transaction" key={payment.id}>
            <div className="record-top"><div><strong>{formatINR(payment.amount_paise)}</strong><p>{payment.method.replaceAll("_", " ")} · {formatShopDate(payment.paid_at)}</p>{payment.transaction_reference && <p>Reference: {payment.transaction_reference}</p>}</div><span className="status-pill status-ready">{payment.status}</span></div>
            {payment.refunds.map((refund) => <p className="refund-line" key={refund.id}>Refund {formatINR(refund.amount_paise)} by {refund.method.replaceAll("_", " ")} · {refund.reason}</p>)}
            {canRefund && payment.amount_paise > payment.refunds.reduce((sum, refund) => sum + refund.amount_paise, 0) && <button className="quiet-button" type="button" disabled={busy} onClick={() => { setRefundPaymentId(payment.id); setRefundKey(""); setRefundAmount(""); }}>Record a refund</button>}
          </article>)}
          {canRecordPayments && balance.outstanding_balance_paise > 0 && <form className="staff-form finance-form" onSubmit={savePayment}>
            <h2>Record a payment</h2>
            <div className="form-two-column"><label>Amount in rupees<input required type="number" min="0.01" max={(balance.outstanding_balance_paise / 100).toFixed(2)} step="0.01" value={paymentAmount} onChange={(event) => { setPaymentAmount(event.target.value); setPaymentKey(""); }} /></label><label>Method<select value={paymentMethod} onChange={(event) => { setPaymentMethod(event.target.value); setPaymentKey(""); }}>{methods.map((method) => <option key={method} value={method}>{method.replaceAll("_", " ")}</option>)}</select></label></div>
            <label>Reference <span className="optional-label">Optional</span><input maxLength={120} value={paymentReference} onChange={(event) => { setPaymentReference(event.target.value); setPaymentKey(""); }} /></label>
            <button className="button button-primary" type="submit" disabled={busy}>Save payment</button>
          </form>}
          {refundPaymentId && <form className="staff-form finance-form refund-form" onSubmit={saveRefund}>
            <h2>Record a refund</h2><p>Up to {formatINR(refundRemainingPaise)} remains available for this payment.</p>
            <div className="form-two-column"><label>Amount in rupees<input required type="number" min="0.01" max={(refundRemainingPaise / 100).toFixed(2)} step="0.01" value={refundAmount} onChange={(event) => { setRefundAmount(event.target.value); setRefundKey(""); }} /></label><label>Refund method<select value={refundMethod} onChange={(event) => { setRefundMethod(event.target.value); setRefundKey(""); }}>{methods.map((method) => <option key={method} value={method}>{method.replaceAll("_", " ")}</option>)}</select></label></div>
            <label>Reason<input required minLength={3} maxLength={500} value={refundReason} onChange={(event) => { setRefundReason(event.target.value); setRefundKey(""); }} /></label>
            <div className="dashboard-actions"><button className="button button-primary" type="submit" disabled={busy}>Save refund</button><button className="quiet-button" type="button" onClick={() => { setRefundPaymentId(""); setRefundKey(""); }}>Cancel</button></div>
          </form>}
        </section>}
        <section className="content-card finance-panel">
          <h2>Expense categories</h2>
          {categories.length === 0 && <p>Add categories such as supplies, utilities, or rent to organise daily expenses.</p>}
          {categories.length > 0 && <div className="category-tags">{categories.map((category) => <span key={category.id}>{category.name}</span>)}</div>}
          {canManageExpenses && <form className="search-row" onSubmit={saveCategory}><label className="sr-only" htmlFor="expense-category">New expense category</label><input id="expense-category" required minLength={2} maxLength={80} value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Add a category" /><button className="quiet-button" type="submit" disabled={busy}>Add category</button></form>}
        </section>
        {canManageExpenses && categories.length > 0 && <section className="content-card finance-panel">
          <h2>Record an expense</h2>
          <form className="staff-form finance-form" onSubmit={saveExpense}>
            <div className="form-two-column"><label>Category<select required value={expenseCategory} onChange={(event) => setExpenseCategory(event.target.value)}>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Amount in rupees<input required type="number" min="0.01" max="1000000" step="0.01" value={expenseAmount} onChange={(event) => setExpenseAmount(event.target.value)} /></label></div>
            <div className="form-two-column"><label>Date<input required type="date" value={expenseDate} onChange={(event) => setExpenseDate(event.target.value)} /></label><label>Description <span className="optional-label">Optional</span><input maxLength={1000} value={expenseDescription} onChange={(event) => setExpenseDescription(event.target.value)} /></label></div>
            <button className="button button-primary" type="submit" disabled={busy}>Save expense</button>
          </form>
        </section>}
        <section>
          <h2 className="section-title-small">Recent expenses</h2>
          {expenses.length === 0 && <div className="empty-state">No expenses have been recorded yet.</div>}
          <div className="record-list">{expenses.slice(0, 30).map((expense) => <article className="record-card finance-expense" key={expense.id}><strong>{formatINR(expense.amount_paise)}</strong><span>{categoryNames.get(expense.category_id) || "Expense"}</span><span>{formatShopDate(expense.spent_at)}</span><p>{expense.description}</p></article>)}</div>
        </section>
        <div className="dashboard-actions"><a className="text-link" href="/staff/closing">Open daily closing <span aria-hidden="true">&rarr;</span></a></div>
      </main>
    </>
  );
}
