import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "nadlan-genie",
  description:
    "Local-first MVP for finding undervalued Israeli residential listings.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
