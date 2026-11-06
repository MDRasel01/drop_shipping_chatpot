import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI Customer Support SaaS | Instruction-Driven Multi-Tenant Platform',
  description: 'Multi-Tenant AI-Powered Instruction-Driven Customer Support SaaS built on Google Gemini API.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 antialiased selection:bg-blue-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}

