import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'PowerNext-AI | CPRI Black-Box Test Bench System',
  description: 'Condition Monitoring, Anomaly Detection & Reference Hotspot Estimation Platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
