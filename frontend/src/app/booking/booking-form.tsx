"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { formatINR } from "@/lib/format";

const MAX_SERVICE_LINES = 25;
const MAX_QUANTITY_PER_SERVICE = 25;
const MAX_ITEMS_PER_BOOKING = 40;

type Service = {
  id: string;
  name: { en: string; te: string };
  description: { en: string; te: string };
  price_paise: number | null;
  quotation_required: boolean;
  price_is_starting: boolean;
  additional_charge_paise: number;
  garment_type: string | null;
  pricing_unit: string;
};

type Category = { id: string; name: { en: string; te: string }; services: Service[] };
type SelectedItem = {
  service_id: string;
  quantity: number;
  garment_type: string;
  fabric: string;
  colour: string;
  condition_notes: string;
  special_instructions: string;
};
type PriceLine = {
  item: SelectedItem;
  service: Service;
  hasConfiguredPrice: boolean;
  requiresConfirmation: boolean;
  lineAmountPaise: number;
};

function itemTitle(service: Service) {
  const garmentName = service.garment_type?.trim();
  const serviceName = service.name.en.trim();
  return garmentName && garmentName.toLocaleLowerCase() !== serviceName.toLocaleLowerCase()
    ? `${garmentName} · ${serviceName}`
    : serviceName;
}

function servicePriceHint(service: Service) {
  const basePrice = service.price_paise ?? 0;
  const extra = service.additional_charge_paise > 0
    ? ` Configured additional charge: ${formatINR(service.additional_charge_paise)} per item.`
    : "";

  if (basePrice === 0) return `Awaiting staff quotation.${extra}`;
  if (service.price_is_starting) {
    return `Starting at ${formatINR(basePrice)} ${service.pricing_unit}; staff will confirm the final price.${extra}`;
  }
  if (service.quotation_required) {
    return `Reference price ${formatINR(basePrice)} ${service.pricing_unit}; awaiting staff quotation.${extra}`;
  }
  return `Configured price: ${formatINR(basePrice)} ${service.pricing_unit}.${extra}`;
}

function createSelectedItem(service: Service): SelectedItem {
  return {
    service_id: service.id,
    quantity: 1,
    garment_type: service.garment_type || service.name.en,
    fabric: "",
    colour: "",
    condition_notes: "",
    special_instructions: "",
  };
}

function lineAmountExpression(line: PriceLine) {
  const { service, item, hasConfiguredPrice, lineAmountPaise } = line;
  const parts: string[] = [];
  if (hasConfiguredPrice && service.price_paise) {
    parts.push(`${formatINR(service.price_paise)} × ${item.quantity}`);
  }
  if (service.additional_charge_paise > 0) {
    parts.push(`Additional charge ${formatINR(service.additional_charge_paise)} × ${item.quantity}`);
  }
  if (parts.length === 0) return "";
  return `${parts.join(" + ")} = ${formatINR(lineAmountPaise)}`;
}

export default function BookingForm() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedItems, setSelectedItems] = useState<SelectedItem[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [requestedDate, setRequestedDate] = useState("");
  const [pickupPreference, setPickupPreference] = useState("drop_off");
  const [loadingServices, setLoadingServices] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/public/services")
      .then(async (response) => {
        if (!response.ok) throw new Error("We could not load the service list. Please try again shortly.");
        setCategories((await response.json()) as Category[]);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Please try again shortly."))
      .finally(() => setLoadingServices(false));
  }, []);

  const selectedQuantity = selectedItems.reduce((total, item) => total + item.quantity, 0);
  const priceSummary = useMemo(() => {
    const lines: PriceLine[] = [];
    for (const item of selectedItems) {
      const service = categories.flatMap((category) => category.services).find((entry) => entry.id === item.service_id);
      if (!service) continue;
      const hasConfiguredPrice = service.price_paise != null && service.price_paise > 0;
      const lineAmountPaise = ((hasConfiguredPrice ? service.price_paise || 0 : 0) + service.additional_charge_paise) * item.quantity;
      lines.push({
        item,
        service,
        hasConfiguredPrice,
        requiresConfirmation: !hasConfiguredPrice || service.quotation_required || service.price_is_starting,
        lineAmountPaise,
      });
    }
    const knownSubtotalPaise = lines.reduce((total, line) => total + line.lineAmountPaise, 0);
    return {
      lines,
      knownSubtotalPaise,
      pendingLines: lines.filter((line) => line.requiresConfirmation),
      unpricedLines: lines.filter((line) => !line.hasConfiguredPrice),
      allPricesFixed: lines.length > 0 && lines.every((line) => !line.requiresConfirmation),
    };
  }, [categories, selectedItems]);

  function toggleService(service: Service, checked: boolean) {
    const alreadySelected = selectedItems.some((item) => item.service_id === service.id);
    if (checked && !alreadySelected) {
      if (selectedItems.length >= MAX_SERVICE_LINES || selectedQuantity >= MAX_ITEMS_PER_BOOKING) return;
      setSelectedItems((current) => [...current, createSelectedItem(service)]);
    } else if (!checked && alreadySelected) {
      setSelectedItems((current) => current.filter((item) => item.service_id !== service.id));
    }
    setError("");
    setMessage("");
  }

  function adjustQuantity(service: Service, difference: -1 | 1) {
    const selected = selectedItems.find((item) => item.service_id === service.id);
    if (!selected) {
      if (difference > 0) toggleService(service, true);
      return;
    }
    if (difference > 0 && (selected.quantity >= MAX_QUANTITY_PER_SERVICE || selectedQuantity >= MAX_ITEMS_PER_BOOKING)) return;

    if (difference < 0 && selected.quantity === 1) {
      toggleService(service, false);
      return;
    }
    setSelectedItems((current) => current.map((item) => item.service_id === service.id
      ? { ...item, quantity: item.quantity + difference }
      : item));
    setError("");
    setMessage("");
  }

  function updateSelectedItem(serviceId: string, values: Partial<SelectedItem>) {
    setSelectedItems((current) => current.map((item) => item.service_id === serviceId ? { ...item, ...values } : item));
  }

  function removeSelectedItem(serviceId: string) {
    setSelectedItems((current) => current.filter((item) => item.service_id !== serviceId));
    setError("");
    setMessage("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedItems.length === 0) {
      setError("Select at least one garment and service before sending your request.");
      return;
    }
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/v1/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: name,
          phone,
          address: address || null,
          pickup_preference: pickupPreference,
          preferred_language: "en",
          requested_delivery_at: requestedDate ? new Date(`${requestedDate}T06:30:00.000Z`).toISOString() : null,
          garments: selectedItems.map((item) => ({
            service_id: item.service_id,
            garment_type: item.garment_type,
            quantity: item.quantity,
            fabric: item.fabric || null,
            colour: item.colour || null,
            condition_notes: item.condition_notes || null,
            special_instructions: item.special_instructions || null,
          })),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Your request could not be sent. Please check the details and try again.");
      setMessage(`Request ${result.order_number} received. It is not confirmed yet; the shop will check the garments, price, and delivery date with you.`);
      setName("");
      setPhone("");
      setAddress("");
      setSelectedItems([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your request could not be sent. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingServices) return <p className="form-state" role="status">Loading available services...</p>;

  const services = categories.flatMap((category) => category.services);
  if (services.length === 0) {
    return (
      <div className="form-state" role="status">
        <h2>Our service list is being set up.</h2>
        <p>Please visit the shop at Sudershan Reddy Nagar, Quthbullapur, Hyderabad, Telangana – 500054, India.</p>
      </div>
    );
  }

  return (
    <form className="booking-form" onSubmit={submit}>
      <div className="form-section-title"><span>01</span><h2>Your details</h2></div>
      <label>Full name<input required autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>Mobile number<input required inputMode="tel" autoComplete="tel" minLength={10} maxLength={20} value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
      <label>Address <span className="optional-label">optional</span><textarea autoComplete="street-address" rows={2} value={address} onChange={(event) => setAddress(event.target.value)} /></label>

      <div className="form-section-title" id="service-selection"><span>02</span><h2>Select garments and services</h2></div>
      <p className="booking-selection-note">Choose every garment and service you want in this booking. Use + and − to set each quantity. You can select up to 25 service combinations and 40 items.</p>
      <div className="booking-service-catalog">
        {categories.filter((category) => category.services.length > 0).map((category) => (
          <section className="booking-service-category" key={category.id} aria-labelledby={`category-${category.id}`}>
            <div className="booking-service-category-heading"><h3 id={`category-${category.id}`}>{category.name.en}</h3><span>{category.services.length} {category.services.length === 1 ? "service" : "services"}</span></div>
            <div className="booking-service-grid">
              {category.services.map((service) => {
                const selected = selectedItems.find((item) => item.service_id === service.id);
                const quantity = selected?.quantity || 0;
                const limitReached = !selected && (selectedItems.length >= MAX_SERVICE_LINES || selectedQuantity >= MAX_ITEMS_PER_BOOKING);
                const plusDisabled = quantity >= MAX_QUANTITY_PER_SERVICE || selectedQuantity >= MAX_ITEMS_PER_BOOKING;
                return (
                  <article className={`booking-service-card${selected ? " is-selected" : ""}`} key={service.id}>
                    <div className="booking-service-card-top">
                      <label className="booking-service-checkbox">
                        <input
                          type="checkbox"
                          checked={Boolean(selected)}
                          disabled={limitReached}
                          onChange={(event) => toggleService(service, event.target.checked)}
                          aria-label={`Select ${itemTitle(service)}`}
                        />
                        <span className="booking-service-card-name">
                          <strong>{service.garment_type || service.name.en}</strong>
                          {service.garment_type && service.garment_type.toLocaleLowerCase() !== service.name.en.toLocaleLowerCase() && <span>Service: {service.name.en}</span>}
                        </span>
                      </label>
                      <div className="booking-quantity-control" aria-label={`${itemTitle(service)} quantity`}>
                        <button type="button" aria-label={`Decrease ${itemTitle(service)} quantity`} disabled={quantity === 0} onClick={() => adjustQuantity(service, -1)}>−</button>
                        <output aria-live="polite">{quantity}</output>
                        <button type="button" aria-label={`Increase ${itemTitle(service)} quantity`} disabled={plusDisabled} onClick={() => adjustQuantity(service, 1)}>+</button>
                      </div>
                    </div>
                    <p className="booking-service-price">{servicePriceHint(service)}</p>
                    {selected && service.description.en && <p className="booking-service-description">{service.description.en}</p>}
                    {quantity === MAX_QUANTITY_PER_SERVICE && <span className="booking-service-limit">Maximum quantity for this service: {MAX_QUANTITY_PER_SERVICE}</span>}
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      {selectedQuantity >= MAX_ITEMS_PER_BOOKING && <p className="booking-selection-limit" role="status">This booking has reached the limit of {MAX_ITEMS_PER_BOOKING} items.</p>}
      {selectedItems.length >= MAX_SERVICE_LINES && <p className="booking-selection-limit" role="status">This booking has reached the limit of {MAX_SERVICE_LINES} service combinations.</p>}

      {selectedItems.length > 0 && <section className="booking-selected-list" aria-labelledby="selected-details-title">
        <div className="booking-selected-heading"><div><p className="eyebrow"><span className="eyebrow-line" /> Item details</p><h3 id="selected-details-title">Details for each selected service</h3></div><span>{selectedQuantity} {selectedQuantity === 1 ? "item" : "items"}</span></div>
        {selectedItems.map((item) => {
          const service = services.find((entry) => entry.id === item.service_id);
          if (!service) return null;
          return <article className="booking-selected-item" key={item.service_id}>
            <div className="booking-selected-item-heading">
              <div><h4>{itemTitle(service)}</h4><p>Quantity: {item.quantity} · {servicePriceHint(service)}</p></div>
              <button className="remove-link" type="button" onClick={() => removeSelectedItem(item.service_id)}>Remove</button>
            </div>
            <label>Garment or item type<input required value={item.garment_type} readOnly={Boolean(service.garment_type)} onChange={(event) => updateSelectedItem(item.service_id, { garment_type: event.target.value })} /></label>
            <div className="form-two-column">
              <label>Fabric <span className="optional-label">optional</span><input value={item.fabric} onChange={(event) => updateSelectedItem(item.service_id, { fabric: event.target.value })} /></label>
              <label>Colour <span className="optional-label">optional</span><input value={item.colour} onChange={(event) => updateSelectedItem(item.service_id, { colour: event.target.value })} /></label>
            </div>
            <label>Existing stains or damage <span className="optional-label">optional</span><textarea rows={2} value={item.condition_notes} onChange={(event) => updateSelectedItem(item.service_id, { condition_notes: event.target.value })} /></label>
            <label>Special instructions <span className="optional-label">optional</span><textarea rows={2} value={item.special_instructions} onChange={(event) => updateSelectedItem(item.service_id, { special_instructions: event.target.value })} /></label>
          </article>;
        })}
      </section>}

      {selectedItems.length > 0 && <section className="booking-estimate" aria-live="polite" aria-labelledby="estimate-title">
        <div className="booking-summary-heading"><div><p className="eyebrow"><span className="eyebrow-line" /> Review before sending</p><h3 id="estimate-title">Your booking summary</h3><p>{selectedQuantity} {selectedQuantity === 1 ? "item" : "items"} across {selectedItems.length} {selectedItems.length === 1 ? "service" : "services"}</p></div><a href="#service-selection" className="booking-edit-link">Edit selection</a></div>
        <ul className="booking-summary-lines">
          {priceSummary.lines.map((line) => <li key={line.service.id}>
            <div className="booking-summary-line-copy"><strong>{itemTitle(line.service)}</strong><span>{line.item.quantity} {line.item.quantity === 1 ? "item" : "items"} · {servicePriceHint(line.service)}</span></div>
            <div className="booking-summary-line-amount">
              {line.hasConfiguredPrice
                ? <><span>{lineAmountExpression(line)}</span><strong>{formatINR(line.lineAmountPaise)}</strong></>
                : line.lineAmountPaise > 0
                  ? <><span>{lineAmountExpression(line)}</span><strong>{formatINR(line.lineAmountPaise)} known charges</strong></>
                  : <strong className="booking-awaiting-price">Awaiting staff quotation</strong>}
            </div>
          </li>)}
        </ul>
        <p className="booking-estimate-total">
          <span>{priceSummary.allPricesFixed ? "Estimated total" : "Configured amount so far"}</span>
          {priceSummary.knownSubtotalPaise > 0 ? <strong>{formatINR(priceSummary.knownSubtotalPaise)}</strong> : <strong className="booking-awaiting-price">Awaiting staff quotation</strong>}
        </p>
        {priceSummary.unpricedLines.length > 0 && <p className="booking-final-bill">Final billing: {priceSummary.knownSubtotalPaise > 0 ? `${formatINR(priceSummary.knownSubtotalPaise)} + ` : ""}staff quotation for {priceSummary.unpricedLines.map((line) => itemTitle(line.service)).join(", ")}.</p>}
        {priceSummary.pendingLines.length > 0 && priceSummary.unpricedLines.length === 0 && <p className="booking-final-bill">Staff will confirm the final price for the starting or reference-priced services after inspection.</p>}
        {priceSummary.pendingLines.some((line) => line.hasConfiguredPrice) && <p className="booking-estimate-note">The configured amount includes starting or reference prices that may change after inspection.</p>}
        {priceSummary.unpricedLines.length > 0 && <ul className="booking-awaiting-list">{priceSummary.unpricedLines.map((line) => <li key={line.service.id}>{itemTitle(line.service)}: awaiting staff quotation{line.service.additional_charge_paise > 0 ? `; configured additional charge ${formatINR(line.service.additional_charge_paise)} per item is included above` : ""}</li>)}</ul>}
        <p className="form-footnote">Fixed prices and configured additional charges are calculated from the current catalogue. Staff confirms the final price after inspecting the garments.</p>
      </section>}

      <div className="form-section-title"><span>03</span><h2>Timing and handover</h2></div>
      <label>Preferred delivery date <span className="optional-label">a request, subject to confirmation</span><input type="date" min={new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date())} value={requestedDate} onChange={(event) => setRequestedDate(event.target.value)} /></label>
      <label>How will you hand over the garments?<select value={pickupPreference} onChange={(event) => setPickupPreference(event.target.value)}><option value="drop_off">I will bring them to the shop</option><option value="pickup">I would like to request pickup</option><option value="delivery">I would like to discuss delivery</option></select></label>

      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success" role="status">{message}</p>}
      <button className="button button-primary submit-button" disabled={submitting || selectedItems.length === 0} type="submit">{submitting ? "Sending request..." : "Confirm booking request"}<span aria-hidden="true">&rarr;</span></button>
      <p className="form-footnote">This is a request only. Shop staff will verify each garment and confirm the price and date with you.</p>
    </form>
  );
}
