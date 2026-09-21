export default function Home() {
  return (
    <main style={{ maxWidth: 600, margin: "80px auto", padding: "0 24px" }}>
      <h1>Kobby Manager</h1>
      <p>AI Talent Manager for content creators.</p>
      <p style={{ color: "#666", fontSize: 14 }}>
        This is the public compliance site. The application itself runs locally.
      </p>
      <nav style={{ marginTop: 32, display: "flex", gap: 24 }}>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Terms of Service</a>
      </nav>
    </main>
  );
}
