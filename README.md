# Durga Boutique and Dry Cleaning

A mobile-first business platform for customer bookings and shop operations. The interface uses a calm cream, ink, and burgundy palette with gold details, clear status labels, and responsive layouts.

## Project guide

- [System architecture](docs/architecture/overview.md)
- [Database model and implementation notes](docs/database/schema.md)
- [API surface](docs/api/contracts.md)
- [UI design system](docs/ux/ui-system.md)
- [Zero-cost choices and deployment limits](docs/deployment/cost-and-deployment.md)

## Available in this starter

- Public service catalogue with fixed and inspection-based quotation prices, item-specific offerings, and booking requests. A request is not a confirmed price or delivery promise until staff checks the customer and garments and the customer approves the proposal.
- Customer registration requests, PIN login, order dashboard and history, proposed price/date approval, notification preferences, and a private customer QR code.
- Staff PIN login, customer search and QR lookup, service catalogue management (including history-safe delete/archive), per-item quotation entry, order status/overdue filters, order verification and status updates, garment intake photos, and delivery-date revision.
- Payment and refund recording, expense categories and entries, daily cash closing, an analytics dashboard, and CSV reports.
- Owner-only data export archive containing database table data as JSON and private media files, with a seven-day download window and audit trail. Authentication sessions are omitted and credential hashes are redacted.
- Delivery reminder and delay records. WhatsApp messages are prepared as click-to-chat drafts only when the customer opted in; staff sends the message manually and records that action.

The landing page avoids fabricated prices, contact details, or customer reviews. The default service offerings are seeded with no prices; staff must enter actual rates or keep each item in quotation mode before live bookings.

## Run locally

Requirements: Docker Desktop (or Docker Engine) with Compose, and enough disk space for the database and private image storage.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The web app is at `http://localhost:3000`; API health and readiness are at `http://localhost:8000/health` and `http://localhost:8000/ready`. Services bind to loopback by default. Before sharing the app or exposing it to a network, replace the placeholder database and session secrets, set the correct public origin, and enable secure cookies behind HTTPS.

Create the first owner from the API container. The command prompts for a mobile number and PIN; the PIN is stored as a password hash.

```powershell
docker compose exec api python -m app.seed_owner
```

The owner can create manager, order staff, or finance staff accounts with:

```powershell
docker compose exec api python -m app.create_staff
```

Run the backend regression checks with:

```powershell
docker compose exec api python -m unittest discover -s tests -v
```

Apply the additive schema update and insert the default service offerings. The commands are safe to repeat; unrelated configured service prices are preserved.

```powershell
docker compose exec api alembic -c alembic.ini upgrade head
docker compose exec api python -m app.seed_catalogue
docker compose exec api python -m app.seed_official_prices
```

The official price list adds 24 garment/service records across dry cleaning, chemical wash, saree, and kids' clothing. Prices marked with `+` appear as starting prices and require a staff-confirmed final amount. Unpriced catalogue entries retain an editable ₹0 staff value and appear to customers as **Price awaiting confirmation**. A matching pre-import Saree dry-cleaning entry was reconciled to the supplied ₹160+ rate and recorded in the audit log; its order snapshots remain unchanged. Other already-configured prices are preserved. Staff can edit rates from **Services**. A service referenced by an order is archived on deletion so order history remains intact.

After signing in at `/staff/login`, add the real categories, prices, and turnaround times from **Services**. The **Finance** page records payments, refunds, and expenses; **Daily close** reconciles the day's recorded totals. To enable manual click-to-chat drafts, set `SHOP_WHATSAPP_NUMBER` in `.env` and restart the API container.

## Backups

The owner **Data exports** page creates a time-limited JSON and media archive. Keep a copy outside the hosting account. For a PostgreSQL backup, run from the project directory and store the resulting file on a separate trusted drive or backup service:

```powershell
docker compose exec db pg_dump -U durga_app -d durga_business -Fc -f /tmp/durga-business.dump
docker compose cp db:/tmp/durga-business.dump .
```

Restore only into a verified target database after taking a separate copy of its current data:

```powershell
docker compose cp durga-business.dump db:/tmp/durga-business.dump
docker compose exec db pg_restore -U durga_app -d durga_business --clean --if-exists /tmp/durga-business.dump
```

## Current limitations

This is an implementation starter and is **not production-ready**. The development Compose setup uses `AUTO_CREATE_SCHEMA=true`; the added migration upgrades an existing starter schema, but a full initial migration for a brand-new production database still needs review. No dependency lockfiles have been generated. External backup scheduling is not configured; the commands above require the owner to store backups away from the hosting account.

The owner archive is a portable data export, not a one-click database restore package; a reviewed restore/import procedure and backup schedule remain future work. The worker creates reminder/delay records; it does not send WhatsApp messages automatically. Official WhatsApp callbacks, a payment gateway, SMS/OTP verification, customer self-service profile editing, a natural-language AI advisor, and a complete production deployment setup remain future work. Review [deployment and cost limits](docs/deployment/cost-and-deployment.md) before choosing a hosting or messaging provider.
