"use client";

import { useEffect, useState } from "react";

type Audience = "customer" | "staff";

export default function AppHeader({ audience }: { audience: Audience }) {
  const [canExport, setCanExport] = useState(false);
  const [canManageServices, setCanManageServices] = useState(false);
  const [canManageFinance, setCanManageFinance] = useState(false);
  const [canViewReports, setCanViewReports] = useState(false);
  useEffect(() => {
    if (audience !== "staff") return;
    fetch("/api/v1/auth/session")
      .then(async (response) => response.ok ? response.json() : null)
      .then((session) => {
        setCanExport(Boolean(session?.permissions?.includes("backup:export")));
        setCanManageServices(Boolean(session?.permissions?.includes("service:manage")));
        setCanManageFinance(Boolean(session?.permissions?.includes("payment:read") || session?.permissions?.includes("expense:read")));
        setCanViewReports(Boolean(session?.permissions?.includes("analytics:read")));
      })
      .catch(() => { setCanExport(false); setCanManageServices(false); setCanManageFinance(false); setCanViewReports(false); });
  }, [audience]);

  const links: [string, string][] = audience === "customer"
    ? [["Home", "/customer"], ["Orders", "/customer/orders"], ["Payments", "/customer/payments"], ["My QR", "/customer/qr"], ["Preferences", "/customer/preferences"]]
    : [["Home", "/staff"], ["Orders", "/staff/orders"], ["Updates", "/staff/notifications"], ["Daily close", "/staff/closing"]];
  if (audience === "staff") {
    if (canManageFinance) links.push(["Finance", "/staff/finance"]);
    if (canViewReports) links.push(["Reports", "/staff/reports"]);
    if (canManageServices) links.push(["Services", "/staff/services"]);
    if (canExport) links.push(["Data export", "/staff/data-exports"]);
  }

  async function logout() {
    await fetch("/api/v1/auth/logout", { method: "POST" });
    window.location.assign(audience === "customer" ? "/customer/login" : "/staff/login");
  }

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="app-header">
        <a className="brand" href={audience === "customer" ? "/customer" : "/staff"}>
          <span className="brand-mark" aria-hidden="true">D</span>
          <span className="brand-name">Durga <span>Boutique &amp; Dry Cleaning</span></span>
        </a>
        <nav aria-label={`${audience} menu`} className="app-nav">
          {links.map(([label, href]) => <a key={href} href={href}>{label}</a>)}
        </nav>
        <button className="quiet-button" onClick={logout} type="button">Sign out</button>
      </header>
    </>
  );
}
