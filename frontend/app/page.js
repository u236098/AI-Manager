export default function Home() {
  return (
    <main style={{ maxWidth: 600, margin: "80px auto", padding: "0 24px" }}>
      <h1>Kobby Manager</h1>
      <p>Creator analytics and performance management for Instagram and TikTok.</p>
      <p style={{ color: "#666", fontSize: 14 }}>
        This is the public compliance site for the Kobby Manager service.
      </p>
      <nav style={{ marginTop: 32, display: "flex", gap: 24 }}>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Terms of Service</a>
      </nav>
    </main>
  );
}
