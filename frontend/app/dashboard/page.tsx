'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function DashboardOverviewPage() {
  const [stats, setStats] = useState({
    messages_used: 1,
    messages_limit: 10000,
    usage_percentage: 0.01,
    active_agents: 1,
    subscription_tier: 'Starter',
  });

  useEffect(() => {
    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId) {
      fetch(`/api/v1/saas/dashboard?tenant_id=${tenantId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setStats(data);
        })
        .catch(() => {});
    }
  }, []);

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Welcome Banner */}
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-600 to-indigo-700 p-8 text-white shadow-sm">
        <h2 className="text-2xl font-bold">Welcome to your AI Support Command Center</h2>
        <p className="mt-2 text-blue-100 text-sm max-w-2xl leading-relaxed">
          Your AI customer support assistant is online. Configure your business instructions, review unanswered customer questions, and install the embeddable chat widget on your website.
        </p>
        <div className="mt-6 flex gap-4">
          <Link
            href="/dashboard/instructions"
            className="rounded-lg bg-white px-4 py-2 text-xs font-bold text-blue-700 shadow-sm hover:bg-blue-50 transition-colors"
          >
            Configure Instructions
          </Link>
          <Link
            href="/dashboard/widget"
            className="rounded-lg border border-white/30 bg-white/10 px-4 py-2 text-xs font-bold text-white hover:bg-white/20 transition-colors"
          >
            Get Widget Code
          </Link>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Message Quota */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>MONTHLY USAGE</span>
            <span className="text-blue-600">{stats.usage_percentage}%</span>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">
            {stats.messages_used.toLocaleString()}
            <span className="text-sm font-medium text-slate-400">
              {' '}/ {stats.messages_limit.toLocaleString()}
            </span>
          </div>
          {/* Progress bar */}
          <div className="mt-4 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(2, Math.min(100, stats.usage_percentage))}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">Monthly message quota resets in 24 days.</p>
        </div>

        {/* Card 2: Active Agents */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 mb-2">AI AGENT POOL</div>
          <div className="text-3xl font-extrabold text-slate-900">
            {stats.active_agents}{' '}
            <span className="text-sm font-medium text-emerald-600">Active</span>
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Logical agent pool powered by Google Gemini 1.5 Flash.
          </p>
        </div>

        {/* Card 3: Subscription */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 mb-2">SUBSCRIPTION TIER</div>
          <div className="text-3xl font-extrabold text-slate-900">{stats.subscription_tier}</div>
          <p className="mt-4 text-xs text-slate-500">
            Includes up to 5 concurrent AI Agents & pgvector RAG memory.
          </p>
        </div>
      </div>

      {/* Quick Setup Checklist */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 mb-4">Setup Checklist (Core MVP)</h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm text-slate-700">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">✓</span>
            <span>Company Account Created & Database Tenant Partitioned</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-700">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-bold">2</span>
            <span>Add Business Instructions and Click <strong>Publish</strong> to generate Gemini 768d vector embeddings.</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-700">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500 text-xs font-bold">3</span>
            <span>Embed widget script tag on your website to start resolving customer questions automatically.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
