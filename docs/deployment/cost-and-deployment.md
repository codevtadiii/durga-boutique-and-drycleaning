# Zero-cost choices and limits

## Baseline

The development and initial operational baseline is self-hosted and open-source:

| Area | Choice | Cost/limit assumption |
| --- | --- | --- |
| Web UI | Next.js, React, TypeScript, Tailwind CSS | Open-source packages; requires a computer/server to run |
| API | Python, FastAPI, Pydantic, SQLAlchemy, Alembic | Open-source packages; no paid API required |
| Database | PostgreSQL | Open-source; storage, backups, and maintenance remain the business's responsibility |
| Local environment | Docker Compose or documented local runtimes | No hosting subscription; consumes local hardware, storage, electricity, and internet if accessed remotely |
| Images | Private local filesystem adapter | No storage provider bill; local disk must be backed up and monitored |
| Data export | Owner-only JSON table and private-media archive | Archive download expires after seven days; store a copy securely. Import/restore tooling and scheduled backups remain unimplemented |
| Background work | Lightweight polling worker that records due reminders in PostgreSQL | No paid queue service; worker must run for timely reminder records; it does not send messages |
| Analytics | Direct, permission-checked database aggregates | No external account or API key is used; a natural-language or deterministic advisor has not been implemented |
| Messaging | Manual click-to-chat fallback | Manual messaging uses the user's WhatsApp account. No official WhatsApp sender or webhook is implemented. Automated service may involve Meta eligibility, template approval, policy, and current pricing; verify directly before building an integration |
| Payments | Cash/UPI/card/bank transfer recorded manually | No gateway account is needed for recording. Online collection integrations may charge and remain optional |

## External service report

No hosting company, domain, AI provider, SMS/OTP gateway, WhatsApp automation provider, payment gateway, or cloud file store is selected as a mandatory dependency. This avoids claiming that changing free tiers are currently available or allowed for this business. Before adding any provider, compare current terms, commercial-use permissions, data location, quotas, downtime behavior, and charges in a dated decision record.

## Local operation and public deployment

Local development can run without a subscription. To make the app available publicly requires an always-on host and HTTPS. A genuinely no-cost host is not guaranteed; free-tier eligibility, quotas, suspension rules, and commercial-use terms change. The platform remains usable on a local shop network if external hosting or integrations are unavailable.

Production requires secure environment secrets, HTTPS, regular PostgreSQL and media backups, tested restore procedures, access controls, and monitoring. The owner archive provides a manual export copy, but there is no scheduled backup or tested restore procedure in the starter. A local backup on the same disk is not sufficient protection from device failure. A second copy can use existing owner-controlled storage; any external storage choice should be evaluated before personal data is uploaded.

## Optional integration rules

- WhatsApp automation stays off until the owner provides authorized official Meta credentials and approved templates. Never use WhatsApp Web bots or scraping.
- AI keys are not part of the baseline. A local model can be evaluated later with hardware and privacy requirements documented; no advisor is implemented yet.
- A payment gateway is not needed to log a cash or UPI receipt. Any gateway must verify server-side payment callbacks and must never store card credentials or UPI PINs.
- Backups and exports must protect customer names, phone numbers, addresses, order photos, and financial records. Export access is owner-only and audited.
