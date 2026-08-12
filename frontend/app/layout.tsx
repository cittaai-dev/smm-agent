import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const spaceMono = Space_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "smm-agent",
  description: "Market Research agent — SOP-01",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${spaceMono.variable}`}>
      <body className="min-h-screen bg-bg font-sans text-text">
        <Providers>
          <div className="mx-auto max-w-3xl p-6">
            <header className="mb-6">
              <a href="/" className="text-lg font-semibold">
                smm-agent
              </a>
            </header>
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
