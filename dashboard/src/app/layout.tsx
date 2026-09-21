import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Providers } from "./providers";

const geist = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Kobby Manager",
  description: "AI Talent Manager for Kobby Cooper",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased`}>
      <body className="min-h-full flex">
        <Providers>
          <Sidebar />
          <main className="ml-56 flex-1 min-h-screen p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
