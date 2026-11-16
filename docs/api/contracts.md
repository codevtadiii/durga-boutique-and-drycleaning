# API surface

This document lists the API routes currently implemented in the starter. FastAPI also publishes generated OpenAPI documentation at `/docs` while the API is running. JSON requests use UUID identifiers and ISO-8601 timestamps; monetary values are integer paise, formatted as INR by the UI. The business timezone defaults to `Asia/Kolkata`.

Mutations that use the browser session require the configured same-origin header check. Staff routes also enforce server-side permissions, and customer routes take customer ownership from the signed-in session.

## Public and authentication routes

| Method and path | Access | Purpose |
| --- | --- | --- |
| `GET /health` / `GET /ready` | Public | Process and database readiness |
| `GET /api/v1/public/services` | Public | Active bilingual catalogue; fixed prices, starting prices, or a null price awaiting staff confirmation |
| `POST /api/v1/bookings` | Public | Save an unconfirmed booking request and garment details |
| `POST /api/v1/auth/customer/register` | Public | Submit a registration request for staff review, including separate WhatsApp preferences |
| `POST /api/v1/auth/customer/pin/login` | Public, rate-limited | Customer PIN login; sets an opaque HttpOnly session cookie |
| `POST /api/v1/auth/staff/pin/login` | Public, rate-limited | Staff PIN login |
| `GET /api/v1/auth/session` | Authenticated | Current identity and permission summary |
| `POST /api/v1/auth/logout` | Authenticated | Revoke the current session |

## Customer routes

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/customer/dashboard` | Current customer's order, garment, and balance summary |
| `GET /api/v1/customer/orders` | Private order history, up to 200 recent orders |
| `GET /api/v1/customer/orders/{order_id}` | Own order, garments, intake photo IDs, and timeline |
| `POST /api/v1/customer/orders/{order_id}/approvals` | Approve or decline a proposed price/date |
| `GET /api/v1/customer/payments` | Own payment history |
| `GET /api/v1/customer/notification-preferences` / `PUT /api/v1/customer/notification-preferences` | Read or update language and independent WhatsApp order/marketing preferences |
| `POST /api/v1/customer/qr` | Rotate the customer's private QR lookup token |
| `GET /api/v1/customer/orders/{order_id}/garments/{garment_id}/photos/{file_id}` | Retrieve an intake photo for the owning customer |

## Staff routes

| Method and path | Permission | Purpose |
| --- | --- | --- |
| `GET /api/v1/staff/customers?query=` | `customer:read` | Search verified customers by name or phone |
| `GET /api/v1/staff/registration-requests` | `customer:read` | List pending customer registration requests |
| `POST /api/v1/staff/registration-requests/{request_id}/approve` | `customer:create` | Approve a request and establish the customer's PIN |
| `POST /api/v1/staff/customers` | `customer:create` | Create a staff-assisted verified customer profile |
| `PATCH /api/v1/staff/customers/{customer_id}/pin` | `customer:manage` | Reset a PIN and revoke the customer's sessions |
| `POST /api/v1/staff/customer-qr/resolve` | `customer:lookup` | Resolve and audit a customer QR lookup |
| `GET /api/v1/staff/orders?status=&query=&delayed_only=` | `order:read` | Search/review orders by status, number, phone, or overdue state |
| `GET /api/v1/staff/orders/{order_id}` | `order:read` | View order, garment, photo IDs, and timeline details |
| `POST /api/v1/staff/orders/{order_id}/verify` | `order:verify` | Record physical garment count, condition, services, customer, and proposed date/price |
| `PATCH /api/v1/staff/orders/{order_id}/status` | `order:status` | Apply an allowed order status transition with a timeline note |
| `PATCH /api/v1/staff/orders/{order_id}/delivery-date` | `order:delivery` | Propose a revised delivery date for customer approval |
| `POST /api/v1/staff/garments/{garment_id}/photos` | `garment:photo` | Upload a private, normalized intake photo |
| `GET /api/v1/staff/garments/{garment_id}/photos/{file_id}` | `garment:photo` | Retrieve an intake photo |
| `GET /api/v1/staff/service-categories`, `POST /api/v1/staff/service-categories` | `service:manage` | List or create catalogue categories |
| `GET /api/v1/staff/services`, `POST /api/v1/staff/services`, `PATCH /api/v1/staff/services/{service_id}`, `DELETE /api/v1/staff/services/{service_id}` | `service:manage` | Manage prices/quotes, additional charges, garment type, and service availability; delete unused services or archive those referenced by orders |
| `POST /api/v1/staff/orders/{order_id}/payments` | `payment:record` | Record a successful manual payment with an idempotency key |
| `POST /api/v1/staff/orders/{order_id}/payments/{payment_id}/refunds` | `refund:record` | Record a refund with reason and idempotency key |
| `GET /api/v1/staff/payment-orders?query=` | `payment:read` | Search confirmed orders by order number without exposing customer contact details |
| `GET /api/v1/staff/orders/{order_id}/payments` | `payment:read` | Read payments and refunds for an order |
| `GET /api/v1/staff/orders/{order_id}/balance` | `payment:read` | Read finalized value, collections, refunds, and outstanding balance |
| `GET /api/v1/staff/expense-categories`, `POST /api/v1/staff/expense-categories` | `expense:read/write` | List or create expense categories |
| `GET /api/v1/staff/expenses`, `POST /api/v1/staff/expenses` | `expense:read/write` | List or record categorized expenses |
| `GET /api/v1/staff/analytics/summary?from_date=&to_date=` | `analytics:read` | Summarize orders, sales, collections, refunds, expenses, and balances |
| `GET /api/v1/staff/analytics/services?from_date=&to_date=` | `analytics:read` | Aggregate garment counts and finalized values by service |
| `GET /api/v1/staff/reports/{orders\|collections\|expenses}.csv?from_date=&to_date=` | `report:export` | Export a bounded date range to CSV |
| `GET /api/v1/staff/daily-closings/{date}` | `closing:read` | Preview totals or view a saved daily close |
| `POST /api/v1/staff/daily-closings/{date}/close` | `closing:write` | Snapshot transactions/expenses and save counted cash and variance |
| `GET /api/v1/staff/notifications` | `notification:read` | Review notification and manual-send records |
| `POST /api/v1/staff/orders/{order_id}/whatsapp-draft` | `notification:send` | Generate an opted-in customer's click-to-chat draft |
| `POST /api/v1/staff/notifications/{notification_id}/manual-sent` | `notification:send` | Record staff-confirmed manual send; does not claim delivery |
| `POST /api/v1/staff/data-exports` | `backup:export` (owner) | Build a seven-day archive of JSON database tables and private media |
| `GET /api/v1/staff/data-exports/{export_id}/download` | `backup:export` (requesting owner only) | Download the private archive before it expires |

## Workflow and deployment notes

- A public booking is a request only. Staff must verify the customer and physical garments, enter a quote for variable-price services, and propose the price/date before a customer can approve them.
- Customer approval stores either an approval or a decline. A revised delivery date stays pending until approval; the accepted date remains unchanged in the meantime.
- The reminder worker creates deduplicated notification records for upcoming or overdue orders. It does not send messages. A staff member opens the click-to-chat draft and explicitly records a manual send.
- No WhatsApp provider webhook, official automated sender, owner settings API, payment gateway, or natural-language advisor route is implemented yet. Owner export archives are available, but they do not include a one-click restore/import procedure.
- Uploads are size-limited, re-encoded, and kept outside the public web root. The API checks staff/customer access before returning an image.
- Payment/refund retries must reuse the original idempotency key with the same request details. The API does not call a payment processor.
- CSV export is bounded to 367 days and 10,000 rows per report. Report access is permission-checked and audited.

## Planned follow-on API work

The next planned backend work is owner settings, an import/restore procedure, scheduled backup automation, approved official WhatsApp provider/webhook integration, and a read-only deterministic advisor over named analytics functions. These are not part of the current API surface.
