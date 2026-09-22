export const metadata = {
  title: "Privacy Policy — Kobby Manager",
};

export default function Privacy() {
  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 24px", lineHeight: 1.7 }}>
      <h1>Privacy Policy</h1>
      <p><strong>Effective date:</strong> 9 September 2026</p>
      <p><strong>Last updated:</strong> 9 September 2026</p>

      <p>
        Kobby Manager (&quot;the App&quot;) is a personal creator analytics and performance-management service built by
        Kobby Cooper (&quot;we&quot;, &quot;us&quot;) for managing his own creator accounts.
        This policy explains what data the App accesses, how it is used, and how it is stored.
      </p>

      <h2>1. Data We Access</h2>
      <p>When you connect a social-media account (TikTok, Instagram), the App accesses:</p>
      <ul>
        <li>Public profile information (username, display name, avatar URL, follower/following counts)</li>
        <li>Video metadata (title, description, post date, duration, cover image URL, share URL)</li>
        <li>Public engagement metrics (view count, like count, comment count, share count)</li>
      </ul>
      <p>
        The App does <strong>not</strong> access private messages, contacts, financial information,
        precise location, or any data belonging to other users.
      </p>

      <h2>2. How We Use the Data</h2>
      <p>All accessed data is used exclusively to:</p>
      <ul>
        <li>Analyse content performance and identify growth patterns</li>
        <li>Generate personalised content recommendations</li>
        <li>Track account metrics over time</li>
        <li>Produce daily and weekly management briefs</li>
      </ul>
      <p>
        Data is processed for the account owner through the Kobby Manager backend and stored in
        its managed PostgreSQL database. It is <strong>not</strong> sold, shared for advertising,
        or used to build advertising profiles. The service sends requests only to the connected
        social-platform APIs and the infrastructure required to operate the application.
      </p>

      <h2>3. Data Storage</h2>
      <p>
        Data is stored in a managed PostgreSQL database. Platform access and refresh tokens are
        encrypted with an application-managed Fernet key before storage. Database credentials,
        encryption keys, and provider secrets are kept in environment-based secret storage and
        are not returned by the API or MCP tools.
      </p>

      <h2>4. Data Retention</h2>
      <p>
        Data is retained in managed application infrastructure for as long as the account owner chooses to use the App.
        Historical metrics are kept to enable long-term trend analysis.
      </p>

      <h2>5. Data Deletion</h2>
      <p>
        The account owner can request deletion of all stored data at any time through the service owner.
        To disconnect a platform account and delete its stored data, the owner can use the
        App&apos;s account management interface or delete the corresponding database records directly.
      </p>
      <p>
        To revoke the App&apos;s access to your TikTok account, visit{" "}
        <a href="https://www.tiktok.com/setting/security" target="_blank" rel="noopener noreferrer">
          TikTok Security Settings
        </a>{" "}
        and remove Kobby Manager from the list of authorised applications.
      </p>

      <h2>6. Children&apos;s Privacy</h2>
      <p>
        The App is not intended for use by anyone under the age of 18. We do not knowingly
        collect data from minors.
      </p>

      <h2>7. Changes to This Policy</h2>
      <p>
        If this policy is updated, the changes will be reflected on this page with an updated
        effective date.
      </p>

      <h2>8. Contact</h2>
      <p>
        For privacy questions, contact: <strong>kobbycooper.gh@gmail.com</strong>
      </p>

      <p style={{ marginTop: 40 }}>
        <a href="/">← Back to home</a>
      </p>
    </main>
  );
}
