export const metadata = {
  title: "Terms of Service — Kobby Manager",
};

export default function Terms() {
  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 24px", lineHeight: 1.7 }}>
      <h1>Terms of Service</h1>
      <p><strong>Effective date:</strong> 9 September 2026</p>
      <p><strong>Last updated:</strong> 9 September 2026</p>

      <p>
        These terms govern the use of Kobby Manager (&quot;the App&quot;), a personal creator
        analytics and performance-management service created by Kobby Cooper.
      </p>

      <h2>1. Description of Service</h2>
      <p>
        Kobby Manager is an application that connects to social-media platform APIs
        (TikTok, Instagram) to retrieve public account data and analyse content performance.
        It generates recommendations, briefs, and reports to assist the account owner in
        managing their creator presence.
      </p>

      <h2>2. Intended Use</h2>
      <p>
        The App is intended for personal use by the account owner to manage their own
        social-media accounts. It is not a public service and is not offered to third parties.
      </p>

      <h2>3. Platform Compliance</h2>
      <p>
        The App accesses third-party platforms through their official APIs and complies with
        their respective developer terms of service, including:
      </p>
      <ul>
        <li>TikTok Developer Terms of Service</li>
        <li>Meta Platform Terms</li>
      </ul>
      <p>
        The App does not scrape, crawl, or access data outside of authorised API endpoints.
      </p>

      <h2>4. Data Handling</h2>
      <p>
        All data accessed through the App is handled in accordance with our{" "}
        <a href="/privacy">Privacy Policy</a>. Data is stored in managed application
        infrastructure and is not sold or used for advertising profiles.
      </p>

      <h2>5. No Warranty</h2>
      <p>
        The App is provided &quot;as is&quot; without warranty of any kind. The developer
        is not liable for any loss of data, account issues, or other damages arising from
        the use of the App.
      </p>

      <h2>6. Limitation of Liability</h2>
      <p>
        The developer shall not be liable for any indirect, incidental, special, or
        consequential damages resulting from the use or inability to use the App.
      </p>

      <h2>7. Changes to These Terms</h2>
      <p>
        These terms may be updated from time to time. Changes will be reflected on this
        page with an updated effective date.
      </p>

      <h2>8. Contact</h2>
      <p>
        For questions about these terms, contact: <strong>kobbycooper.gh@gmail.com</strong>
      </p>

      <p style={{ marginTop: 40 }}>
        <a href="/">← Back to home</a>
      </p>
    </main>
  );
}
