"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppHeader from "@/components/app-header";
import { formatINR, formatShopDate, readableStatus, statusClass } from "@/lib/format";

type Service = { id: string; name_en: string; category_name_en: string; price_paise: number; quotation_required: boolean; price_is_starting: boolean; additional_charge_paise: number; garment_type: string | null; pricing_unit: string; active: boolean };
type Customer = { id: string; full_name: string; phone: string; preferred_language: string };
type Garment = { garment_id: string | null; service_id: string; service_name: string; quantity: number; unit_price_paise: number | null; line_total_paise: number | null; pricing_unit: string; garment_type: string; fabric: string; colour: string; condition_notes: string; special_instructions: string; quoted_price_rupees: string; photos: string[] };
type Detail = { id: string; order_number: string; customer_id: string | null; customer_name: string; phone: string; status: string; is_delayed: boolean; expected_delivery_at: string | null; proposed_delivery_at: string | null; requested_delivery_at: string | null; proposed_total_paise: number | null; confirmed_total_paise: number | null; booking_contact: { full_name: string; phone: string } | null; garments: { id: string; service_id: string; service_name: string; quantity: number; unit_price_paise: number | null; line_total_paise: number | null; pricing_unit: string; type: string; fabric: string | null; colour: string | null; condition_notes: string | null; special_instructions: string | null; photos: string[] }[] };

function dateInput(value: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function dateToIso(value: string) {
  return new Date(`${value}T06:30:00.000Z`).toISOString();
}

const nextStatuses: Record<string, string[]> = {
  booking_received: ["cancelled"], awaiting_verification: ["cancelled"], awaiting_customer_approval: ["cancelled"],
  order_confirmed: ["received_at_shop", "cancelled"], received_at_shop: ["processing", "cancelled"],
  processing: ["quality_check", "cancelled"], quality_check: ["processing", "ready_for_collection"],
  ready_for_collection: ["out_for_delivery", "delivered", "processing"], out_for_delivery: ["delivered", "ready_for_collection"],
};

export default function StaffOrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<Detail | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [garments, setGarments] = useState<Garment[]>([]);
  const [customerQuery, setCustomerQuery] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [qrValue, setQrValue] = useState("");
  const [identityChecked, setIdentityChecked] = useState(false);
  const [deliveryDate, setDeliveryDate] = useState("");
  const [revisionDate, setRevisionDate] = useState("");
  const [cancellationReason, setCancellationReason] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const serviceSummary = useMemo(() => {
    const grouped = new Map<string, { key: string; type: string; service: string; quantity: number; unitPricePaise: number | null; lineTotalPaise: number; pricingUnit: string; awaitingQuote: boolean }>();
    for (const garment of garments) {
      const key = `${garment.service_id}|${garment.unit_price_paise ?? "quote"}|${garment.pricing_unit}|${garment.garment_type}`;
      const existing = grouped.get(key);
      if (existing) {
        existing.quantity += garment.quantity;
        existing.lineTotalPaise += garment.line_total_paise || 0;
        existing.awaitingQuote ||= garment.unit_price_paise == null;
      } else {
        grouped.set(key, {
          key,
          type: garment.garment_type,
          service: garment.service_name,
          quantity: garment.quantity,
          unitPricePaise: garment.unit_price_paise,
          lineTotalPaise: garment.line_total_paise || 0,
          pricingUnit: garment.pricing_unit,
          awaitingQuote: garment.unit_price_paise == null,
        });
      }
    }
    return [...grouped.values()];
  }, [garments]);

  async function loadOrder() {
    const [orderResponse, serviceResponse] = await Promise.all([fetch(`/api/v1/staff/orders/${orderId}`), fetch("/api/v1/staff/services")]);
    const orderResult = await orderResponse.json();
    const serviceResult = await serviceResponse.json();
    if (!orderResponse.ok) throw new Error(orderResult.detail || "Please sign in with a staff account.");
    if (!serviceResponse.ok) throw new Error(serviceResult.detail || "Service choices are unavailable.");
    const loaded = orderResult as Detail;
    setOrder(loaded);
    setServices(serviceResult);
    setGarments(loaded.garments.map((garment) => ({
      garment_id: garment.id, service_id: garment.service_id, service_name: garment.service_name,
      quantity: garment.quantity, unit_price_paise: garment.unit_price_paise,
      line_total_paise: garment.line_total_paise, pricing_unit: garment.pricing_unit, garment_type: garment.type,
      fabric: garment.fabric || "", colour: garment.colour || "", condition_notes: garment.condition_notes || "",
      special_instructions: garment.special_instructions || "", quoted_price_rupees: "", photos: garment.photos,
    })));
    setDeliveryDate(dateInput(loaded.proposed_delivery_at || loaded.requested_delivery_at));
    setRevisionDate(dateInput(loaded.expected_delivery_at));
    if (loaded.customer_id) setCustomer({ id: loaded.customer_id, full_name: loaded.customer_name, phone: loaded.phone, preferred_language: "en" });
  }

  // The fetch completes asynchronously and its result is the external source for this page's state.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { loadOrder().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load this order.")); }, [orderId]);

  async function searchCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch(`/api/v1/staff/customers?query=${encodeURIComponent(customerQuery)}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Customer search failed.");
      setCustomers(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Customer search failed."); }
  }

  async function lookupQr(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch("/api/v1/staff/customer-qr/resolve", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ qr_value: qrValue }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "This QR code could not be looked up.");
      setCustomer(result);
      setCustomers([]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "This QR code could not be looked up."); }
  }

  function updateGarment(index: number, field: "garment_type" | "fabric" | "colour" | "condition_notes" | "special_instructions" | "quoted_price_rupees", value: string) {
    setGarments((current) => current.map((garment, itemIndex) => itemIndex === index ? { ...garment, [field]: value } : garment));
  }

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!customer) { setError("Find and select the customer before verification."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/orders/${orderId}/verify`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id: customer.id, identity_checked_in_person: identityChecked, expected_delivery_at: dateToIso(deliveryDate), garments: garments.map((garment) => ({ garment_id: garment.garment_id, service_id: garment.service_id, garment_type: garment.garment_type, fabric: garment.fabric || null, colour: garment.colour || null, condition_notes: garment.condition_notes || null, special_instructions: garment.special_instructions || null, quoted_price_paise: garment.quoted_price_rupees.trim() ? Math.round(Number(garment.quoted_price_rupees) * 100) : null })) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The order could not be verified.");
      setNotice(`Garments checked. Proposed total ${formatINR(result.proposed_total_paise)} and date are waiting for customer approval.`);
      await loadOrder();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The order could not be verified."); }
    finally { setBusy(false); }
  }

  async function addPhoto(index: number, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !garments[index].garment_id) return;
    const data = new FormData();
    data.set("file", file);
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/garments/${garments[index].garment_id}/photos`, { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The photo could not be saved.");
      setNotice("Intake photo saved with this garment.");
      await loadOrder();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The photo could not be saved."); }
    finally { setBusy(false); event.target.value = ""; }
  }

  async function changeStatus(next: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/orders/${orderId}/status`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next, cancellation_reason: next === "cancelled" ? cancellationReason : null }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The status could not be updated.");
      setNotice(`Order status changed to ${readableStatus(result.status)}.`);
      await loadOrder();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The status could not be updated."); }
    finally { setBusy(false); }
  }

  async function reviseDate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/orders/${orderId}/delivery-date`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_delivery_at: dateToIso(revisionDate) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The date could not be changed.");
      setNotice(result.message);
      await loadOrder();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The date could not be changed."); }
    finally { setBusy(false); }
  }

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <Link className="back-link" href="/staff/orders">&larr; Order queue</Link>
        {error && <div className="form-error" role="alert">{error}</div>}
        {notice && <div className="form-success" role="status">{notice}</div>}
        {!order && !error && <p role="status">Loading order...</p>}
        {order && <>
          <p className="eyebrow"><span className="eyebrow-line" /> Order workbench</p>
          <div className="order-heading"><div><h1>{order.order_number}</h1><p>{order.customer_name} · {order.phone}</p></div><span className={`status-pill ${order.is_delayed ? "status-delayed" : statusClass(order.status)}`}>{order.is_delayed ? "Past expected date" : readableStatus(order.status)}</span></div>
          <div className="metric-grid"><article className="metric-card"><span>Garments</span><strong>{garments.reduce((total, garment) => total + garment.quantity, 0)}</strong></article><article className="metric-card"><span>Expected</span><strong className="metric-date">{formatShopDate(order.expected_delivery_at)}</strong></article><article className="metric-card"><span>Proposed total</span><strong>{order.proposed_total_paise == null ? "—" : formatINR(order.proposed_total_paise)}</strong></article><article className="metric-card"><span>Confirmed total</span><strong>{order.confirmed_total_paise == null ? "—" : formatINR(order.confirmed_total_paise)}</strong></article></div>

          {["booking_received", "awaiting_verification"].includes(order.status) && <section className="content-card">
            <p className="eyebrow"><span className="eyebrow-line" /> Physical verification</p><h2>Check each garment with the customer</h2>
            <form className="search-row" onSubmit={searchCustomer}><label className="sr-only" htmlFor="customer-search">Search customer by name or mobile</label><input id="customer-search" value={customerQuery} onChange={(event) => setCustomerQuery(event.target.value)} placeholder="Find customer by name or mobile" /><button className="button button-primary" type="submit">Search</button></form>
            <form className="search-row" onSubmit={lookupQr}><label className="sr-only" htmlFor="qr-value">Scanned customer QR value</label><input id="qr-value" value={qrValue} onChange={(event) => setQrValue(event.target.value)} placeholder="Or scan/paste customer QR" /><button className="button button-primary" type="submit">Look up QR</button></form>
            {customers.map((candidate) => <button type="button" className={`customer-choice ${customer?.id === candidate.id ? "selected" : ""}`} key={candidate.id} onClick={() => setCustomer(candidate)}><strong>{candidate.full_name}</strong><span>{candidate.phone}</span></button>)}
            {customer && <p className="selected-customer">Selected: <strong>{customer.full_name}</strong> · {customer.phone}</p>}
            <form className="staff-form" onSubmit={verify}>
              <label className="checkbox-label"><input type="checkbox" required checked={identityChecked} onChange={(event) => setIdentityChecked(event.target.checked)} /> I checked this customer&apos;s identity in person or matched their QR code</label>
              <label>Proposed expected delivery date<input required type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} /></label>
              <h3>Garments and service</h3>
              {serviceSummary.length > 0 && <div className="staff-booking-summary" aria-label="Requested service summary">
                {serviceSummary.map((line) => <div key={line.key}>
                  <strong>{line.type} · {line.service}</strong>
                  <span>{line.quantity} {line.quantity === 1 ? "item" : "items"} · {line.awaitingQuote ? `Awaiting staff quotation${line.lineTotalPaise > 0 ? ` · known additional charges ${formatINR(line.lineTotalPaise)}` : ""}` : `${formatINR(line.unitPricePaise || 0)} ${line.pricingUnit} · line subtotal ${formatINR(line.lineTotalPaise)}`}</span>
                </div>)}
              </div>}
              {garments.map((garment, index) => <div className="verify-garment" key={garment.garment_id || `new-${index}`}>
                <div className="staff-booking-line"><strong>{garment.garment_type} · {garment.service_name}</strong><span>{garment.quantity} {garment.quantity === 1 ? "item" : "items"} · {garment.unit_price_paise == null ? "Awaiting staff quotation" : `Selected unit price ${formatINR(garment.unit_price_paise)} ${garment.pricing_unit} · line subtotal ${formatINR(garment.line_total_paise ?? 0)}`}</span></div>
                <div className="form-two-column">
                  <label>Garment type<input required value={garment.garment_type} onChange={(event) => updateGarment(index, "garment_type", event.target.value)} /></label>
                  <label>Service<select required value={garment.service_id} onChange={(event) => {
                    const service = services.find((item) => item.id === event.target.value);
                    setGarments((current) => current.map((line, lineIndex) => {
                      if (lineIndex !== index) return line;
                      const needsQuote = !service || service.quotation_required || service.price_is_starting || service.price_paise === 0;
                      const basePrice = service && !needsQuote ? service.price_paise : null;
                      return {
                        ...line,
                        service_id: event.target.value,
                        service_name: service?.name_en || "",
                        pricing_unit: service?.pricing_unit || line.pricing_unit,
                        unit_price_paise: basePrice,
                        line_total_paise: basePrice == null || !service ? null : (basePrice + service.additional_charge_paise) * line.quantity,
                        garment_type: service?.garment_type || service?.name_en || line.garment_type,
                        quoted_price_rupees: "",
                      };
                    }));
                  }}><option value="">Choose configured service</option>{services.filter((service) => service.active).map((service) => <option key={service.id} value={service.id}>{service.category_name_en} · {service.name_en} · {service.price_paise === 0 ? "Price awaiting confirmation" : service.price_is_starting ? `Starting at ${formatINR(service.price_paise)} · confirm final price` : service.quotation_required ? `Reference ${formatINR(service.price_paise)} · confirm final price` : formatINR(service.price_paise)}{service.additional_charge_paise > 0 ? ` + ${formatINR(service.additional_charge_paise)}` : ""}</option>)}</select></label>
                  <label>Fabric<input value={garment.fabric} onChange={(event) => updateGarment(index, "fabric", event.target.value)} /></label>
                  <label>Colour<input value={garment.colour} onChange={(event) => updateGarment(index, "colour", event.target.value)} /></label>
                </div>
                {(() => {
                  const service = services.find((item) => item.id === garment.service_id);
                  if (!service || !service.quotation_required) return null;
                  return <label>Staff quotation in rupees<input required type="number" min="0.01" max="1000000" step="0.01" value={garment.quoted_price_rupees} onChange={(event) => updateGarment(index, "quoted_price_rupees", event.target.value)} /><span className="optional-label">Quote before any additional charge shown above</span></label>;
                })()}
                <label>Existing stains or damage<textarea rows={2} value={garment.condition_notes} onChange={(event) => updateGarment(index, "condition_notes", event.target.value)} /></label>
                <label>Special instructions<textarea rows={2} value={garment.special_instructions} onChange={(event) => updateGarment(index, "special_instructions", event.target.value)} /></label>
                {garment.garment_id && <label className="photo-upload">Add intake photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" disabled={busy} onChange={(event) => addPhoto(index, event)} /></label>}
                {garment.photos.map((photoId) => <span className="photo-saved" key={photoId}>Intake photo saved</span>)}
                <button className="remove-link" type="button" onClick={() => setGarments((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove garment from verified count</button>
              </div>)}
              <button className="quiet-button" type="button" onClick={() => setGarments((current) => {
                const service = services.find((item) => item.active);
                const needsQuote = !service || service.quotation_required || service.price_is_starting || service.price_paise === 0;
                const basePrice = service && !needsQuote ? service.price_paise : null;
                return [...current, { garment_id: null, service_id: service?.id || "", service_name: service?.name_en || "", quantity: 1, unit_price_paise: basePrice, line_total_paise: basePrice == null || !service ? null : basePrice + service.additional_charge_paise, pricing_unit: service?.pricing_unit || "per item", garment_type: service?.garment_type || "Other garment", fabric: "", colour: "", condition_notes: "", special_instructions: "", quoted_price_rupees: "", photos: [] }];
              })}>Add verified garment</button>
              <p className="form-footnote">Fixed prices come from the catalogue. Enter a staff quotation for variable-price services. Configured additional charges are added separately. The customer approves the complete total before the order is confirmed.</p>
              <button className="button button-primary" disabled={busy || garments.length === 0} type="submit">{busy ? "Saving verification..." : "Save and request approval"}</button>
            </form>
          </section>}

          {order.confirmed_total_paise != null && !["delivered", "cancelled"].includes(order.status) && <section className="content-card">
            <h2>Delivery date update</h2><p>A changed date waits for customer approval. Old pending reminders are made obsolete.</p>
            <form className="search-row" onSubmit={reviseDate}><label className="sr-only" htmlFor="revision-date">Proposed revised expected delivery date</label><input id="revision-date" required type="date" value={revisionDate} onChange={(event) => setRevisionDate(event.target.value)} /><button className="button button-primary" type="submit" disabled={busy}>Propose revised date</button></form>
          </section>}

          {nextStatuses[order.status]?.length > 0 && <section className="content-card">
            <h2>Update order status</h2>
            {nextStatuses[order.status].includes("cancelled") && <label className="status-reason">Cancellation reason<input value={cancellationReason} onChange={(event) => setCancellationReason(event.target.value)} /></label>}
            <div className="dashboard-actions">{nextStatuses[order.status].map((next) => <button className={next === "cancelled" ? "quiet-button" : "button button-primary"} key={next} type="button" disabled={busy || (next === "cancelled" && !cancellationReason)} onClick={() => changeStatus(next)}>{next === "cancelled" ? "Cancel order" : `Mark ${readableStatus(next)}`}</button>)}</div>
          </section>}
        </>}
      </main>
    </>
  );
}
