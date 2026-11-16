const services = [
  {
    number: "01",
    title: "Dry cleaning",
    description: "Care for sarees, dresses, shirts, suits, and delicate garments.",
    label: "Garment care",
  },
  {
    number: "02",
    title: "Boutique services",
    description: "Stitching, alterations, embroidery, and custom tailoring.",
    label: "Made to fit",
  },
];

export default function HomePage() {
  return (
    <>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <a className="brand" href="#home" aria-label="Durga Boutique and Dry Cleaning home">
          <span className="brand-mark" aria-hidden="true">D</span>
          <span className="brand-name">Durga <span>Boutique &amp; Dry Cleaning</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <a href="#services">Services</a>
          <a href="#about">Our approach</a>
          <a href="#visit">Visit us</a>
        </nav>
        <a className="header-link" href="/booking">Book a service <span aria-hidden="true">&nearr;</span></a>
      </header>

      <main id="main-content" tabIndex={-1}>
      <section className="hero" id="home" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-line" /> A little more care, in every detail</p>
          <h1 id="hero-title">Good clothes deserve <em>good care.</em></h1>
          <p className="hero-description">
            Thoughtful garment care and boutique services, brought together for the clothes you love.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="/booking">Book a service <span aria-hidden="true">&rarr;</span></a>
            <a className="text-link" href="#visit">Find our shop <span aria-hidden="true">&nearr;</span></a>
          </div>
          <div className="hero-note"><span className="note-dot" /> Serving our neighbours in Quthbullapur, Hyderabad</div>
        </div>

        <div className="hero-art" aria-hidden="true">
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div className="art-sun" />
          <div className="fabric-card">
            <div className="fabric-fold fold-top" />
            <div className="fabric-fold fold-bottom" />
            <div className="fabric-stitch" />
            <span className="fabric-label">made with care</span>
          </div>
          <div className="art-caption"><span>01 / 02</span><span>Care meets craft</span></div>
          <div className="art-stamp" aria-hidden="true"><span>CARE</span><span className="stamp-star">&#10041;</span><span>CRAFT</span></div>
        </div>
      </section>

      <section className="service-section" id="services" aria-labelledby="services-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow"><span className="eyebrow-line" /> What we do</p>
            <h2 id="services-title">Two kinds of care.<br /><em>One familiar place.</em></h2>
          </div>
          <p className="section-intro">From a favourite saree to a perfect fit, find the service that feels right for you.</p>
        </div>
        <div className="service-grid">
          {services.map((service) => (
            <article className="service-card" key={service.number}>
              <div className="service-card-top"><span>{service.number}</span><span className="service-label">{service.label}</span></div>
              <h3>{service.title}</h3>
              <p>{service.description}</p>
              <a className="card-link" href="/booking">Request this service <span aria-hidden="true">&nearr;</span></a>
              <span className={`card-art card-art-${service.number}`} aria-hidden="true"><span /></span>
            </article>
          ))}
        </div>
      </section>

      <section className="approach-section" id="about" aria-labelledby="approach-title">
        <div className="approach-mark" aria-hidden="true"><span>D</span><i>&#10041;</i></div>
        <div className="approach-copy">
          <p className="eyebrow"><span className="eyebrow-line" /> Our approach</p>
          <h2 id="approach-title">The details matter.<br /><em>So does how you feel.</em></h2>
          <p>Every garment has its own story. We bring boutique attention to the little details, with clear conversations about the service, price, and expected date before work begins.</p>
        </div>
        <div className="approach-aside"><span>01</span><p>Ask us about the right care for your garment.</p><span className="aside-rule" /><span>02</span><p>We confirm the details with you before we begin.</p></div>
      </section>

      <section className="visit-section" id="visit" aria-labelledby="visit-title">
        <div>
          <p className="eyebrow"><span className="eyebrow-line" /> Come say hello</p>
          <h2 id="visit-title">A familiar face,<br /><em>right around the corner.</em></h2>
        </div>
        <address>Sudershan Reddy Nagar, Quthbullapur,<br />Hyderabad, Telangana – 500054, India</address>
      </section>

      </main>
      <footer className="site-footer">
        <a className="brand footer-brand" href="#home"><span className="brand-mark" aria-hidden="true">D</span><span className="brand-name">Durga <span>Boutique &amp; Dry Cleaning</span></span></a>
        <p>Thoughtful care for the clothes you love.</p>
        <span>Quthbullapur | Hyderabad</span>
      </footer>
    </>
  );
}
