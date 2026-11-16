# UI design system

## Visual direction

The interface should feel polished and trustworthy while staying calm and obvious for local customers and busy shop staff. Burgundy is the brand action color, with white and warm near-white surfaces, charcoal text, and light gray separators. Gold is a small decorative accent only; it never carries text or status meaning.

| Token | Hex | Use |
| --- | --- | --- |
| Brand / primary | `#8B1E3F` | Main buttons, selected navigation, links on light backgrounds |
| Brand hover | `#6F1732` | Hover and pressed states |
| Ink | `#241F21` | Body text and headings |
| Canvas | `#FFFDFC` | Main page background |
| Surface | `#FFFFFF` | Cards and dialogs |
| Soft surface | `#F7F3F4` | Secondary panels and table headers |
| Border | `#E7DEE1` | Dividers and control outlines |
| Muted text | `#625A5D` | Hints and secondary labels |
| Accent | `#B58A4A` | Small decorative details only |
| Success | `#176B45` | Paid, delivered, completed |
| Warning | `#8A5200` | Awaiting confirmation, due soon |
| Danger | `#A32020` | Overdue, failed, cancelled |
| Info | `#245B86` | Processing and neutral updates |

Text is never distinguished by color alone: status badges include short words and, where useful, familiar icons. Primary burgundy is used on white/near-white surfaces; text contrast and keyboard focus are checked during UI implementation.

## Navigation and customer tasks

The customer experience should put **Book a service**, **Track an order**, and **My payments** first, with a contact action only after the owner configures verified shop details. The current landing page and customer screens do not invent shop contact details. A phone-first sign-in/register path uses short forms, large touch targets, clear progress, and no unexplained abbreviations. On the dashboard the next expected action and delivery date appear before analytics.

Order tracking uses a plain-language timeline, expected date or revised date, and garment count. Balances show total, paid, and remaining amounts separately. Photos are shown beside the associated garment and intake condition. Delayed orders display their expected date; a direct contact action awaits verified shop contact settings.

## Staff workflow

Staff screens use a compact labeled header navigation that wraps for narrow screens. The work queue starts with order/customer search and an explicit QR lookup field, with status and delay labels on each recent order. A hardware scanner can enter the QR value; an in-app camera scanner and queue filters are future work. The matched name and phone are shown before staff attaches the customer to an order.

Order verification uses a step-by-step form: identify customer, count garments, record condition/photos, select configured services, confirm proposed price/date, and request approval. Payment entry keeps amount and method prominent, with refunds and expenses grouped on the finance screen. Daily close groups recorded collections by method, shows expenses and expected cash, and asks for counted cash before submission.

## Accessibility and language

- Design from 360px Android widths upward; avoid dense tables on phones and provide card/list equivalents.
- Use readable base text, large touch targets, visible focus, keyboard support, semantic headings/labels, and accessible form errors.
- Keep key actions consistently placed and pair icons with words.
- English and Telugu strings are translation keys, never concatenated fragments. Dates, digits, and currency use locale-aware formatting.
- Avoid excessive motion, carousels, tiny gray text, icon-only controls, and fabricated reviews or prices.
- Loading, empty, success, offline, and error states use plain language and a clear next step.
