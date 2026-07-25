import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NHL ML Lab",
  description: "NHL predictions, schedules, rosters, and lineups",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-nhl-gray text-nhl-dark min-h-screen">
        <header className="bg-nhl-red text-white p-4 shadow-lg">
          <div className="max-w-7xl mx-auto">
            <a href="/" className="text-2xl font-bold hover:text-gray-200 transition">
              NHL ML Lab
            </a>
          </div>
        </header>
        <main className="max-w-7xl mx-auto p-6">{children}</main>
        <footer className="bg-nhl-dark text-white p-4 mt-12 text-center text-sm">
          NHL ML Lab — Predictions & Data
        </footer>
      </body>
    </html>
  );
}