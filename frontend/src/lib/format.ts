export function formatINR(paise: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(paise / 100);
}

export function formatShopDate(value: string | null | undefined) {
  if (!value) return "To be confirmed";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "Asia/Kolkata" }).format(new Date(value));
}

export function readableStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function statusClass(value: string) {
  if (["ready_for_collection", "delivered"].includes(value)) return "status-ready";
  if (value === "cancelled") return "status-cancelled";
  if (["processing", "quality_check", "out_for_delivery"].includes(value)) return "status-processing";
  if (["booking_received", "awaiting_verification", "awaiting_customer_approval"].includes(value)) return "status-pending";
  return "";
}
