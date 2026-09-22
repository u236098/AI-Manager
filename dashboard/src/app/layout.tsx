import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Kobby Manager",
  description: "Creator analytics and performance management for Kobby Cooper",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex">
        <Providers>
          <Sidebar />
          <main className="ml-56 flex-1 min-h-screen p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
