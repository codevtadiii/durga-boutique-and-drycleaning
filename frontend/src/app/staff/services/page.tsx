"use client";

import { FormEvent, useEffect, useState } from "react";
import AppHeader from "@/components/app-header";
import { formatINR } from "@/lib/format";

type Category = { id: string; name_en: string; name_te: string; active: boolean };
type CategoryNameForm = Pick<Category, "name_en" | "name_te">;
type Service = {
  id: string;
  category_id: string;
  name_en: string;
  name_te: string;
  description_en: string;
  description_te: string;
  price_paise: number;
  quotation_required: boolean;
  price_is_starting: boolean;
  additional_charge_paise: number;
  garment_type: string | null;
  pricing_unit: string;
  turnaround_days: number | null;
  active: boolean;
};

const emptyService = {
  category_id: "", name_en: "", name_te: "", price_rupees: "", quotation_required: false, price_is_starting: false,
  additional_rupees: "", garment_type: "", pricing_unit: "per item", turnaround_days: "",
};
type ServiceForm = typeof emptyService;

function rupeesToPaise(value: string) {
  return value.trim() ? Math.round(Number(value) * 100) : null;
}

function servicePriceLabel(service: Service) {
  if (service.price_paise === 0) return "₹0.00 · Price awaiting confirmation";
  if (service.price_is_starting) return `Starting at ${formatINR(service.price_paise)} · Price awaiting confirmation`;
  if (service.quotation_required) return `Reference price ${formatINR(service.price_paise)} · Price awaiting confirmation`;
  return `${formatINR(service.price_paise)} ${service.pricing_unit}`;
}

export default function ServicesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [categoryForm, setCategoryForm] = useState({ name_en: "", name_te: "" });
  const [editingCategoryId, setEditingCategoryId] = useState("");
  const [categoryEditForm, setCategoryEditForm] = useState<CategoryNameForm>({ name_en: "", name_te: "" });
  const [deleteCategoryTarget, setDeleteCategoryTarget] = useState<Category | null>(null);
  const [serviceForm, setServiceForm] = useState<ServiceForm>(emptyService);
  const [editingId, setEditingId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Service | null>(null);
  const [editForm, setEditForm] = useState<ServiceForm>(emptyService);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [categoryResponse, serviceResponse] = await Promise.all([
      fetch("/api/v1/staff/service-categories"), fetch("/api/v1/staff/services"),
    ]);
    const categoryData = await categoryResponse.json();
    const serviceData = await serviceResponse.json();
    if (!categoryResponse.ok) throw new Error(categoryData.detail || "Sign in with a manager or owner account to manage services.");
    if (!serviceResponse.ok) throw new Error(serviceData.detail || "The catalogue could not be loaded.");
    setCategories(categoryData);
    setServices(serviceData);
    setServiceForm((current) => ({ ...current, category_id: current.category_id || categoryData.find((item: Category) => item.active)?.id || "" }));
  }

  // The fetch completes asynchronously and its result is the external source for this page's state.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "The catalogue could not be loaded.")); }, []);

  useEffect(() => {
    if (!deleteTarget && !deleteCategoryTarget) return;
    function handleDialogKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) {
        setDeleteTarget(null);
        setDeleteCategoryTarget(null);
      }
    }
    window.addEventListener("keydown", handleDialogKey);
    return () => window.removeEventListener("keydown", handleDialogKey);
  }, [deleteTarget, deleteCategoryTarget, busy]);

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch("/api/v1/staff/service-categories", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(categoryForm),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The category could not be saved.");
      setCategoryForm({ name_en: "", name_te: "" }); setNotice("Category added."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The category could not be saved."); }
    finally { setBusy(false); }
  }

  function startCategoryEdit(category: Category) {
    setEditingCategoryId(category.id);
    setCategoryEditForm({ name_en: category.name_en, name_te: category.name_te });
  }

  async function saveCategoryEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingCategoryId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/service-categories/${editingCategoryId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(categoryEditForm),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "The catalogue name could not be updated.");
      setEditingCategoryId("");
      setNotice(`${result.name_en} catalogue name updated.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The catalogue name could not be updated."); }
    finally { setBusy(false); }
  }

  async function deleteCatalogue() {
    if (!deleteCategoryTarget || busy) return;
    const category = deleteCategoryTarget;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/service-categories/${category.id}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "The catalogue could not be deleted.");
      setCategories((current) => current.filter((item) => item.id !== category.id));
      setServices((current) => current.filter((item) => item.category_id !== category.id));
      setDeleteCategoryTarget(null);
      setEditingCategoryId("");
      setNotice(result.action === "archived"
        ? `${category.name_en} was removed. ${result.services_archived} service(s) with order history were archived; ${result.services_deleted} unused service(s) deleted.`
        : `${category.name_en} catalogue and its unused services were deleted.`);
      try {
        await load();
      } catch {
        setError(`${category.name_en} was removed, but the catalogue could not refresh. Reload this page to sync it.`);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The catalogue could not be deleted."); }
    finally { setBusy(false); }
  }

  function servicePayload(form: ServiceForm) {
    return {
      category_id: form.category_id,
      name_en: form.name_en,
      name_te: form.name_te,
      price_paise: rupeesToPaise(form.price_rupees) ?? (form.quotation_required ? 0 : null),
      quotation_required: form.quotation_required,
      price_is_starting: form.price_is_starting,
      additional_charge_paise: rupeesToPaise(form.additional_rupees) ?? 0,
      garment_type: form.garment_type.trim() || null,
      pricing_unit: form.pricing_unit,
      turnaround_days: form.turnaround_days === "" ? null : Number(form.turnaround_days),
    };
  }

  async function saveService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch("/api/v1/staff/services", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...servicePayload(serviceForm), active: true }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The service could not be saved.");
      setServiceForm({ ...emptyService, category_id: serviceForm.category_id });
      setNotice("Service added to the booking list."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The service could not be saved."); }
    finally { setBusy(false); }
  }

  function removeService(service: Service) {
    setError("");
    setDeleteTarget(service);
  }

  async function permanentlyDeleteService() {
    if (!deleteTarget || busy) return;
    const service = deleteTarget;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/v1/staff/services/${service.id}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "The service could not be removed.");
      setServices((current) => current.filter((item) => item.id !== service.id));
      setNotice(result.action === "archived" ? `${service.name_en} archived. Existing order history is preserved.` : `${service.name_en} permanently deleted.`);
      setDeleteTarget(null);
      if (editingId === service.id) setEditingId("");
      try {
        await load();
      } catch {
        setError(`${service.name_en} was removed, but the catalogue could not refresh. Reload this page to sync it.`);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The service could not be removed."); }
    finally { setBusy(false); }
  }

  function startEdit(service: Service) {
    setEditingId(service.id);
    setEditForm({
      category_id: service.category_id, name_en: service.name_en, name_te: service.name_te,
      price_rupees: (service.price_paise / 100).toFixed(2),
      quotation_required: service.quotation_required,
      price_is_starting: service.price_is_starting,
      additional_rupees: (service.additional_charge_paise / 100).toFixed(2),
      garment_type: service.garment_type || "", pricing_unit: service.pricing_unit,
      turnaround_days: service.turnaround_days == null ? "" : String(service.turnaround_days),
    });
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = servicePayload(editForm);
      const response = await fetch(`/api/v1/staff/services/${editingId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "The service could not be updated.");
      setEditingId(""); setNotice("Service details updated."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The service could not be updated."); }
    finally { setBusy(false); }
  }

  function fields(form: ServiceForm, setForm: (value: ServiceForm) => void, includeCategory: boolean) {
    return <>
      {includeCategory && <label>Category<select required value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })}>{categories.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select></label>}
      <div className="form-two-column">
        <label>Service name in English<input required minLength={2} maxLength={120} value={form.name_en} onChange={(event) => setForm({ ...form, name_en: event.target.value })} /></label>
        <label>Service name in Telugu<input required minLength={2} maxLength={120} value={form.name_te} onChange={(event) => setForm({ ...form, name_te: event.target.value })} /></label>
      </div>
      <label className="checkbox-label"><input type="checkbox" checked={form.quotation_required} onChange={(event) => setForm({ ...form, quotation_required: event.target.checked, price_is_starting: event.target.checked ? form.price_is_starting : false })} /> Final price needs staff confirmation after item inspection</label>
      <div className="form-two-column">
        <label>Price in rupees{form.quotation_required && <span className="optional-label">Use 0 if no starting amount is set</span>}<input required={!form.quotation_required} type="number" min="0" max="1000000" step="0.01" value={form.price_rupees} onChange={(event) => setForm({ ...form, price_rupees: event.target.value, price_is_starting: event.target.value ? form.price_is_starting : false })} /></label>
        <label>Price unit<input required minLength={2} maxLength={30} placeholder="per item, pair, kg, set" value={form.pricing_unit} onChange={(event) => setForm({ ...form, pricing_unit: event.target.value })} /></label>
      </div>
      <label className="checkbox-label"><input type="checkbox" checked={form.price_is_starting} disabled={!form.price_rupees || Number(form.price_rupees) <= 0} onChange={(event) => setForm({ ...form, price_is_starting: event.target.checked, quotation_required: event.target.checked || form.quotation_required })} /> This is a starting price; staff confirms the final amount</label>
      <div className="form-two-column">
        <label>Additional charge in rupees<input type="number" min="0" max="1000000" step="0.01" value={form.additional_rupees} onChange={(event) => setForm({ ...form, additional_rupees: event.target.value })} /></label>
        <label>Garment or item type <span className="optional-label">Optional</span><input maxLength={100} placeholder="Saree, blanket, shoes..." value={form.garment_type} onChange={(event) => setForm({ ...form, garment_type: event.target.value })} /></label>
      </div>
      <label>Turnaround time in days <span className="optional-label">Optional</span><input type="number" min="0" max="365" step="1" value={form.turnaround_days} onChange={(event) => setForm({ ...form, turnaround_days: event.target.value })} /></label>
    </>;
  }

  function serviceCard(service: Service) {
    return <article className="record-card" key={service.id}>
      <div className="record-top"><div><h2>{service.name_en}</h2><p>{service.name_te} · {servicePriceLabel(service)}{service.additional_charge_paise > 0 ? ` · + ${formatINR(service.additional_charge_paise)} additional` : ""}{service.garment_type ? ` · ${service.garment_type}` : ""}{service.turnaround_days != null ? ` · about ${service.turnaround_days} days` : ""}</p></div><span className={`status-pill ${service.active ? "status-ready" : ""}`}>{service.active ? "Available" : "Hidden"}</span></div>
      {editingId === service.id ? <form className="simple-form service-edit-form" onSubmit={saveEdit}>
        {fields(editForm, setEditForm, false)}
        <div className="dashboard-actions"><button className="button button-primary" type="submit" disabled={busy}>Save changes</button><button className="quiet-button" type="button" disabled={busy} onClick={() => setEditingId("")}>Cancel</button><button className="quiet-button catalogue-delete" type="button" disabled={busy} onClick={() => removeService(service)}>Delete service</button></div>
      </form> : <div className="dashboard-actions"><button className="quiet-button catalogue-edit" type="button" disabled={busy} onClick={() => startEdit(service)}>Edit details</button><button className="quiet-button catalogue-delete" type="button" disabled={busy} onClick={() => removeService(service)}>Delete service</button></div>}
    </article>;
  }

  function catalogueSection(category: Category, categoryServices: Service[]) {
    return <section className="catalogue-section" key={category.id} aria-labelledby={`catalogue-${category.id}`}>
      <div className="catalogue-section-heading">
        {editingCategoryId === category.id ? <form className="catalogue-rename-form" onSubmit={saveCategoryEdit}>
          <label>Catalogue name in English<input required minLength={2} maxLength={100} value={categoryEditForm.name_en} onChange={(event) => setCategoryEditForm({ ...categoryEditForm, name_en: event.target.value })} /></label>
          <label>Catalogue name in Telugu<input required minLength={2} maxLength={100} value={categoryEditForm.name_te} onChange={(event) => setCategoryEditForm({ ...categoryEditForm, name_te: event.target.value })} /></label>
          <div className="catalogue-rename-actions"><button className="button button-primary" type="submit" disabled={busy}>Save name</button><button className="quiet-button" type="button" disabled={busy} onClick={() => setEditingCategoryId("")}>Cancel</button></div>
        </form> : <div><h3 id={`catalogue-${category.id}`}>{category.name_en}</h3><p>{category.name_te} · {categoryServices.length} {categoryServices.length === 1 ? "service" : "services"}</p></div>}
        <div className="catalogue-section-heading-actions">
          <button className="quiet-button catalogue-add-button" type="button" disabled={busy || !category.active} onClick={() => {
            setServiceForm({ ...emptyService, category_id: category.id });
            document.getElementById("add-service-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}>Add service here</button>
          <button className="quiet-button" type="button" disabled={busy} onClick={() => startCategoryEdit(category)}>Edit catalogue</button>
          <button className="quiet-button catalogue-delete" type="button" disabled={busy} onClick={() => {
            setError("");
            setDeleteCategoryTarget(category);
          }}>Delete catalogue</button>
        </div>
      </div>
      {categoryServices.length ? <div className="record-list">{categoryServices.map(serviceCard)}</div> : <p className="catalogue-empty">No services in this catalogue yet.</p>}
    </section>;
  }

  return (
    <>
      <AppHeader audience="staff" />
      <main id="main-content" className="app-page" tabIndex={-1}>
        <p className="eyebrow"><span className="eyebrow-line" /> Service setup</p>
        <h1>Make your services<br /><em>easy to choose.</em></h1>
        <p className="page-intro">Set each service&apos;s item type, price or quotation status, additional charge, and turnaround. Customers only see configured prices.</p>
        {error && <div className="form-error" role="alert">{error}</div>}
        {notice && <div className="form-success" role="status">{notice}</div>}
        <section className="content-card catalogue-panel">
          <h2>Service categories</h2>
          {categories.length === 0 && <p>Create a category first, such as dry cleaning or tailoring.</p>}
          {categories.length > 0 && <div className="category-tags">{categories.map((category) => <span key={category.id}>{category.name_en} · {category.name_te}</span>)}</div>}
          <form className="simple-form catalogue-form" onSubmit={saveCategory}>
            <div className="form-two-column"><label>Category name in English<input required minLength={2} maxLength={100} value={categoryForm.name_en} onChange={(event) => setCategoryForm({ ...categoryForm, name_en: event.target.value })} /></label><label>Category name in Telugu<input required minLength={2} maxLength={100} value={categoryForm.name_te} onChange={(event) => setCategoryForm({ ...categoryForm, name_te: event.target.value })} /></label></div>
            <button className="quiet-button" type="submit" disabled={busy}>Add category</button>
          </form>
        </section>
        <section className="content-card catalogue-panel" id="add-service-form">
          <h2>Add a service</h2>
          {categories.length === 0 ? <p>Add a category before creating a service.</p> : <form className="simple-form catalogue-form" onSubmit={saveService}>
            {fields(serviceForm, setServiceForm, true)}
            <button className="button button-primary" type="submit" disabled={busy}>Add service</button>
          </form>}
        </section>
        <section>
          <h2 className="section-title-small">Current catalogue</h2>
          {services.length === 0 && <div className="empty-state">No services yet. Add offerings and set a price or quotation status.</div>}
          {(categories.length > 0 || services.length > 0) && <div className="catalogue-sections">{categories.map((category) => catalogueSection(category, services.filter((service) => service.category_id === category.id)))}
            {services.some((service) => !categories.some((category) => category.id === service.category_id)) && <section className="catalogue-section"><div className="catalogue-section-heading"><h3>Other services</h3></div><div className="record-list">{services.filter((service) => !categories.some((category) => category.id === service.category_id)).map(serviceCard)}</div></section>}
          </div>}
        </section>
        {deleteTarget && <div className="catalogue-dialog-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !busy) setDeleteTarget(null);
        }}>
          <div className="catalogue-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-service-title" aria-describedby="delete-service-warning" tabIndex={-1} onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
            const first = buttons[0];
            const last = buttons[buttons.length - 1];
            if (!first || !last) {
              event.preventDefault();
              event.currentTarget.focus();
            } else if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === event.currentTarget)) {
              event.preventDefault();
              first.focus();
            }
          }}>
            <p className="eyebrow"><span className="eyebrow-line" /> Delete service</p>
            {error && <div className="form-error catalogue-dialog-error" role="alert">{error}</div>}
            <h2 id="delete-service-title">Permanently delete “{deleteTarget.name_en}”?</h2>
            <p className="catalogue-delete-name">Service: <strong>{deleteTarget.name_en}</strong></p>
            <p>If previous orders use this service, it will be archived so their history stays intact. Services without order history will be permanently deleted.</p>
            <p id="delete-service-warning">Are you sure you want to permanently delete this service? This action cannot be undone.</p>
            <div className="dashboard-actions catalogue-dialog-actions">
              <button className="quiet-button" type="button" autoFocus disabled={busy} onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button className="button catalogue-permanent-button" type="button" disabled={busy} onClick={permanentlyDeleteService}>{busy ? "Deleting…" : "Permanently Delete"}</button>
            </div>
          </div>
        </div>}
        {deleteCategoryTarget && <div className="catalogue-dialog-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !busy) setDeleteCategoryTarget(null);
        }}>
          <div className="catalogue-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-catalogue-title" aria-describedby="delete-catalogue-warning" tabIndex={-1}>
            <p className="eyebrow"><span className="eyebrow-line" /> Delete catalogue</p>
            {error && <div className="form-error catalogue-dialog-error" role="alert">{error}</div>}
            <h2 id="delete-catalogue-title">Delete “{deleteCategoryTarget.name_en}”?</h2>
            <p className="catalogue-delete-name">Catalogue: <strong>{deleteCategoryTarget.name_en}</strong></p>
            <p id="delete-catalogue-warning">Its services will be removed from new bookings. Services used in past orders will be archived, and order and payment history will be preserved. Unused services will be permanently deleted.</p>
            <div className="dashboard-actions catalogue-dialog-actions">
              <button className="quiet-button" type="button" autoFocus disabled={busy} onClick={() => setDeleteCategoryTarget(null)}>Cancel</button>
              <button className="button catalogue-permanent-button" type="button" disabled={busy} onClick={deleteCatalogue}>{busy ? "Deleting…" : "Delete catalogue"}</button>
            </div>
          </div>
        </div>}
      </main>
    </>
  );
}
