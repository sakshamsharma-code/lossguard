import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "LossGuard",
  description: "Risk-and-exposure-aware return-fraud intervention engine",
  favicon: "/favicon.svg",
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
