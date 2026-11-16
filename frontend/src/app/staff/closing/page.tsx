"use client";

import { FormEvent, useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR, readableStatus } from "@/lib/format";

type Closing = {
  business_date: string;
  transaction_totals_by_method: { collections?: Record<string, number>; refunds?: Record<string, number>; net_by_method?: Record<string, number> };
  expense_totals_by_category: Record<string, number>;
  expense_total_paise: number;
  expected_cash_paise: number;
  counted_cash_paise: number | null;
  cash_variance_paise: number | null;
  notes: string | null;
  closed_at: string | null;
};

function localBusinessDate() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function toPaise(value: string) {
  if (!/^\d{1,8}(\.\d{0,2})?$/.test(value)) return null;
  const [rupees, fraction = ""] = value.split(".");
  return Number(rupees) * 100 + Number(fraction.padEnd(2, "0"));
}

export default function DailyClosingPage() {
  const [date, setDate] = useState(localBusinessDate());
  const [closing, setClosing] = useState<Closing | null>(null);
  const [countedCash, setCountedCash] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(selectedDate: string) {
    const response = await fetch(`/api/v1/staff/daily-closings/${selectedDate}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not load this closing report.");
    setClosing(result);
    setCountedCash(result.counted_cash_paise == null ? "" : (result.counted_cash_paise / 100).toFixed(2));
    setNotes(result.notes || "");
  }

  // This effect fetches the selected business date; the response updates page state asynchronously.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(date).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load closing report.")); }, [date]);

  async function closeDay(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cash = toPaise(countedCash);
    if (cash == null) { setError("Enter the cash count in rupees, using up to two decimal places."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/daily-closings/${date}/close`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ counted_cash_paise: cash, notes: notes || null }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The day could not be closed.");
      setClosing(result);
      setNotice("Daily closing saved. The recorded totals are kept as a snapshot.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The day could not be closed."); }
    finally { setBusy(false); }
  }

  const collections = closing?.transaction_totals_by_method.collections || {};
  const refunds = closing?.transaction_totals_by_method.refunds || {};
  const methods = [...new Set([...Object.keys(collections), ...Object.keys(refunds)])].sort();

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> End of day</p>
        <h1>Close with<br /><em>a clear picture.</em></h1>
        <p className="page-intro">Collections and expenses come from recorded transactions. Count the cash in the drawer and note any difference.</p>
        <label className="closing-date">Business date<input type="date" max={localBusinessDate()} value={date} onChange={(event) => setDate(event.target.value)} /></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        {notice && <div className="form-success" role="status">{notice}</div>}
        {!closing && !error && <p role="status">Loading recorded totals...</p>}
        {closing && <>
          <section className="closing-panel">
            <h2>Collections by method</h2>
            {methods.length === 0 && <p>No collections or refunds are recorded for this date.</p>}
            {methods.map((method) => <div className="summary-line" key={method}><span>{readableStatus(method)}</span><strong>{formatINR(collections[method] || 0)}</strong>{(refunds[method] || 0) > 0 && <small>Refunds: {formatINR(refunds[method])}</small>}</div>)}
            <h2>Expenses</h2>
            {Object.entries(closing.expense_totals_by_category).map(([category, amount]) => <div className="summary-line" key={category}><span>{category}</span><strong>{formatINR(amount)}</strong></div>)}
            {Object.keys(closing.expense_totals_by_category).length === 0 && <p>No expenses are recorded for this date.</p>}
            <div className="summary-total"><span>Expected cash</span><strong>{formatINR(closing.expected_cash_paise)}</strong></div>
            {closing.closed_at && <p className="closing-locked">Closed and saved at {new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(new Date(closing.closed_at))}</p>}
          </section>
          {!closing.closed_at ? <form className="booking-form closing-form" onSubmit={closeDay}>
            <label>Cash counted in drawer (Rs)<input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={countedCash} onChange={(event) => setCountedCash(event.target.value)} placeholder="0.00" /></label>
            <label>Notes about any difference <span className="optional-label">optional</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <div className="summary-total"><span>Cash variance</span><strong>{countedCash && toPaise(countedCash) != null ? formatINR(toPaise(countedCash)! - closing.expected_cash_paise) : "Enter cash count"}</strong></div>
            <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Saving..." : "Save daily closing"}</button>
          </form> : <section className="closing-panel"><div className="summary-total"><span>Cash counted</span><strong>{formatINR(closing.counted_cash_paise || 0)}</strong></div><div className="summary-total"><span>Cash variance</span><strong>{formatINR(closing.cash_variance_paise || 0)}</strong></div><p>Corrections require an audited adjustment. This closing record cannot be silently changed.</p></section>}
        </>}
      </main>
    </>
  );
}
