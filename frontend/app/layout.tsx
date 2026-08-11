import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "smm-agent",
  description: "Market Research agent — SOP-01",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">
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
