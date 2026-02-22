import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "leaflet/dist/leaflet.css";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LookOut — Live Hazard Map",
  description: "AI-powered traffic and hazard detection for safer roads",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={plusJakarta.variable}>
      <body className="min-h-screen bg-[#0a0e17] text-[#e2e8f0] antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
