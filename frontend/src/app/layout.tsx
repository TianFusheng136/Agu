import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI 短线市场雷达",
  description: "面向中国 A 股短线投资者的市场资金方向研究辅助工具",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
