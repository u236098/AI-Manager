export const metadata = {
  title: "Kobby Manager",
  description: "AI Talent Manager for Kobby Cooper",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, -apple-system, sans-serif", color: "#1a1a1a", background: "#fafafa" }}>
        {children}
      </body>
    </html>
  );
}
