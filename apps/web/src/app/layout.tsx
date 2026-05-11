import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AeroSpec Agent",
  description: "Aircraft concept design workbench"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
