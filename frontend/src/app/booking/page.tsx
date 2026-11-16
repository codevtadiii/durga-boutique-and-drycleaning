import BookingForm from "./booking-form";
import Link from "next/link";

export const metadata = {
  title: "Book a service | Durga Boutique and Dry Cleaning",
};

export default function BookingPage() {
  return (
    <main className="form-page">
      <Link className="back-link" href="/">&larr; Back to home</Link>
      <div className="form-heading">
        <p className="eyebrow"><span className="eyebrow-line" /> A simple first step</p>
        <h1>Tell us what<br /><em>needs a little care.</em></h1>
        <p>Send a request and our team will check the garments, price, and expected date with you before confirming the order.</p>
      </div>
      <BookingForm />
    </main>
  );
}
