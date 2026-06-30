import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EI-OS — Enterprise Intelligence OS",
  description: "Causal reasoning over GitHub PRs, Slack messages, and customer complaints. Powered by Lemma SDK.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#0a0a0f]">
        {children}
      </body>
    </html>
  );
}
