import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CourierAI",
  description: "Persistent autonomous game-playing agent built on Gamini",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className="antialiased bg-zinc-950 text-zinc-100"
      >
        {children}
      </body>
    </html>
  );
}
