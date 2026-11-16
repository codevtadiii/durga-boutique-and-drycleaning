import PhonePinForm from "@/components/phone-pin-form";
import Link from "next/link";

export const metadata = { title: "Customer sign in | Durga Boutique and Dry Cleaning" };

export default function CustomerLoginPage() {
  return (
    <main className="form-page login-page">
      <Link className="back-link" href="/">&larr; Back to home</Link>
      <div className="login-card">
        <div className="brand-mark login-mark" aria-hidden="true">D</div>
        <p className="eyebrow"><span className="eyebrow-line" /> Welcome back</p>
        <h1>Your orders,<br /><em>all in one place.</em></h1>
        <p className="login-intro">Sign in with the mobile number and PIN set up with our shop team.</p>
        <PhonePinForm audience="customer" />
        <p className="login-help">New here? <a href="/customer/register">Ask the shop to set up your account</a></p>
      </div>
    </main>
  );
}
