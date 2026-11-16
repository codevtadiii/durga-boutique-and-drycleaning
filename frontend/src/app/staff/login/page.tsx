import PhonePinForm from "@/components/phone-pin-form";
import Link from "next/link";

export const metadata = { title: "Staff sign in | Durga Boutique and Dry Cleaning" };

export default function StaffLoginPage() {
  return (
    <main className="form-page login-page">
      <Link className="back-link" href="/">&larr; Back to home</Link>
      <div className="login-card">
        <div className="brand-mark login-mark" aria-hidden="true">D</div>
        <p className="eyebrow"><span className="eyebrow-line" /> Staff access</p>
        <h1>Good to see<br /><em>you again.</em></h1>
        <p className="login-intro">Use your mobile number and shop PIN to open the work desk.</p>
        <PhonePinForm audience="staff" />
      </div>
    </main>
  );
}
