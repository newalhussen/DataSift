import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "DataSift", description: "CSV data-quality analyzer" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-line bg-card">
          <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 5h18l-7 8v6l-4-2v-4z" /></svg>
            <span className="font-semibold">DataSift</span>
            <span className="text-sm text-muted">CSV data-quality analyzer</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
