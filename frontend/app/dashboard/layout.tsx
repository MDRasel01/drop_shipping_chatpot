'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [companyName, setCompanyName] = useState('Your Company');

  useEffect(() => {
    const stored = localStorage.getItem('company_name');
    if (stored) setCompanyName(stored);
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    router.push('/login');
  };

  const navItems = [
    { label: 'Overview', href: '/dashboard', icon: '📊' },
    { label: 'Knowledge & Instructions', href: '/dashboard/instructions', icon: '📝' },
    { label: 'Unknown Questions', href: '/dashboard/questions', icon: '❓' },
    { label: 'Widget & Embed', href: '/dashboard/widget', icon: '💬' },
  ];

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between p-6">
        <div>
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-lg shadow-sm">
              AI
            </div>
            <div>
              <div className="font-bold text-slate-900 leading-tight">SupportOS</div>
              <div className="text-xs text-slate-400 font-medium truncate max-w-[140px]">
                {companyName}
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="space-y-1">
            {navItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-semibold transition-colors ${
                    active
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <span className="text-base">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Footer profile & logout */}
        <div className="border-t border-slate-200 pt-4">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
            <span>Tier: <strong className="text-blue-600">Starter</strong></span>
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" title="Online" />
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left rounded-lg px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-red-600 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <header className="h-16 border-b border-slate-200 bg-white px-8 flex items-center justify-between">
          <h1 className="text-lg font-bold text-slate-900">
            {navItems.find((i) => i.href === pathname)?.label || 'Dashboard'}
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 bg-slate-100 px-3 py-1.5 rounded-full font-medium">
              API Engine: v1.0 Operational
            </span>
          </div>
        </header>

        <main className="flex-1 p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
