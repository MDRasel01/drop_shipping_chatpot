'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Chatbot {
  id: string;
  tenant_id: string;
  name: string;
  avatar_url?: string;
  description?: string;
  welcome_message: string;
  system_instructions?: string;
  status: string;
  is_active: boolean;
  max_capacity: number;
  active_conversations: number;
  available_capacity: number;
  slug?: string;
  live_url?: string;
}

export default function ChatbotsPage() {
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [editingBot, setEditingBot] = useState<Chatbot | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    avatar_url: '',
    description: '',
    welcome_message: 'Hello! How can I assist you today?',
    system_instructions: 'You are a professional, helpful, and concise customer support representative.',
    max_capacity: 5,
    slug: '',
  });

  const tenantId = typeof window !== 'undefined' ? localStorage.getItem('tenant_id') : null;

  const fetchChatbots = async () => {
    if (!tenantId) return;
    try {
      const res = await fetch(`/api/v1/dashboard/chatbots?tenant_id=${tenantId}`);
      if (!res.ok) throw new Error('Failed to load chatbots pool');
      const data = await res.json();
      setChatbots(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChatbots();
  }, [tenantId]);

  const handleOpenCreateModal = () => {
    setEditingBot(null);
    setFormData({
      name: '',
      avatar_url: '',
      description: '',
      welcome_message: 'Hello! How can I assist you today?',
      system_instructions: 'You are a professional, polite, and concise customer support assistant. Follow verified company instructions.',
      max_capacity: 5,
      slug: '',
    });
    setShowModal(true);
  };

  const handleOpenEditModal = (bot: Chatbot) => {
    setEditingBot(bot);
    setFormData({
      name: bot.name,
      avatar_url: bot.avatar_url || '',
      description: bot.description || '',
      welcome_message: bot.welcome_message,
      system_instructions: bot.system_instructions || '',
      max_capacity: bot.max_capacity,
      slug: bot.slug || '',
    });
    setShowModal(true);
  };

  const handleSaveChatbot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantId) return;
    setError(null);

    try {
      if (editingBot) {
        // Update existing chatbot
        const res = await fetch(`/api/v1/dashboard/chatbots/${editingBot.id}?tenant_id=${tenantId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Failed to update chatbot');
        }
      } else {
        // Create new chatbot (Default: Inactive)
        const res = await fetch(`/api/v1/dashboard/chatbots?tenant_id=${tenantId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Failed to create chatbot');
        }
      }

      setShowModal(false);
      fetchChatbots();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleToggleActive = async (bot: Chatbot) => {
    if (!tenantId) return;
    const endpoint = bot.is_active
      ? `/api/v1/dashboard/chatbots/${bot.id}/deactivate?tenant_id=${tenantId}`
      : `/api/v1/dashboard/chatbots/${bot.id}/activate?tenant_id=${tenantId}`;

    try {
      const res = await fetch(endpoint, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update chatbot state');
      }
      fetchChatbots();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (botId: string) => {
    if (!tenantId || !confirm('Are you sure you want to remove this chatbot instance?')) return;
    try {
      const res = await fetch(`/api/v1/dashboard/chatbots/${botId}?tenant_id=${tenantId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete chatbot');
      fetchChatbots();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const copyLiveUrl = (slug?: string) => {
    if (!slug) return;
    const fullUrl = `${window.location.origin}/live/${slug}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedSlug(slug);
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  const activeCount = chatbots.filter((b) => b.is_active).length;
  const totalCapacity = chatbots.filter((b) => b.is_active).reduce((acc, b) => acc + b.max_capacity, 0);
  const activeChats = chatbots.filter((b) => b.is_active).reduce((acc, b) => acc + b.active_conversations, 0);

  return (
    <div className="max-w-6xl space-y-8">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Multi-Chatbot Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Build and deploy independently customizable chatbots. Toggle them ON to join the live assignment pool or open their dedicated Live Chat URL.
          </p>
        </div>
        <button
          onClick={handleOpenCreateModal}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
        >
          <span>＋</span> Create Chatbot
        </button>
      </div>

      {/* Pool Concurrency Stats Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-500">TOTAL CHATBOTS</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{chatbots.length}</div>
          <div className="text-xs text-slate-400 mt-1">Configured instances</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-500">ACTIVE IN POOL</div>
          <div className="mt-1 text-2xl font-bold text-emerald-600">
            {activeCount}{' '}
            <span className="text-sm font-medium text-slate-400">/ {chatbots.length} ON</span>
          </div>
          <div className="text-xs text-slate-400 mt-1">Ready for auto-assignment</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-500">POOL CONCURRENCY</div>
          <div className="mt-1 text-2xl font-bold text-blue-600">
            {activeChats}{' '}
            <span className="text-sm font-medium text-slate-400">/ {totalCapacity} chats</span>
          </div>
          <div className="text-xs text-slate-400 mt-1">Current live utilization</div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-xs font-bold underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Chatbots Grid */}
      {loading ? (
        <div className="py-16 text-center text-sm text-slate-400">Loading multi-chatbot pool...</div>
      ) : chatbots.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-2xl">
            🤖
          </div>
          <h3 className="mt-4 text-base font-bold text-slate-900">No Chatbots Created Yet</h3>
          <p className="mt-1 text-sm text-slate-500 max-w-md mx-auto">
            You have not configured any chatbot instances yet. Create your first chatbot to start accepting customer conversations.
          </p>
          <button
            onClick={handleOpenCreateModal}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Create Your First Chatbot
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {chatbots.map((bot) => {
            const loadPercent = Math.min(100, Math.round((bot.active_conversations / bot.max_capacity) * 100));

            return (
              <div
                key={bot.id}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between hover:border-slate-300 transition-all"
              >
                <div>
                  {/* Top: Avatar, Name & ON/OFF Switch */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      {bot.avatar_url ? (
                        <img
                          src={bot.avatar_url}
                          alt={bot.name}
                          className="h-12 w-12 rounded-xl object-cover border border-slate-200"
                        />
                      ) : (
                        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 font-bold text-white text-lg shadow-sm">
                          {bot.name.slice(0, 2).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <h3 className="font-bold text-slate-900 leading-tight text-base">
                          {bot.name}
                        </h3>
                        <span className="text-[11px] font-mono text-slate-400">
                          ID: {bot.id.slice(0, 8)}
                        </span>
                      </div>
                    </div>

                    {/* ON / OFF Switch */}
                    <div className="flex flex-col items-end">
                      <button
                        type="button"
                        onClick={() => handleToggleActive(bot)}
                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          bot.is_active ? 'bg-emerald-500' : 'bg-slate-200'
                        }`}
                        title={bot.is_active ? 'Turn OFF (Stop accepting new chats)' : 'Turn ON (Join live pool)'}
                      >
                        <span
                          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                            bot.is_active ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                      <span className="text-[10px] font-bold uppercase mt-1 text-slate-400">
                        {bot.is_active ? 'ON' : 'OFF'}
                      </span>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <div className="mt-4 flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        bot.status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : bot.status === 'busy'
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : bot.status === 'draining'
                          ? 'bg-purple-50 text-purple-700 border border-purple-200'
                          : 'bg-slate-100 text-slate-600 border border-slate-200'
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          bot.status === 'active'
                            ? 'bg-emerald-500 animate-pulse'
                            : bot.status === 'busy'
                            ? 'bg-amber-500'
                            : bot.status === 'draining'
                            ? 'bg-purple-500'
                            : 'bg-slate-400'
                        }`}
                      />
                      {bot.status.toUpperCase()}
                    </span>
                    <span className="text-xs text-slate-400">
                      {bot.is_active ? 'In Live Pool' : 'Not accepting chats'}
                    </span>
                  </div>

                  {/* Concurrency Gauge */}
                  <div className="mt-5">
                    <div className="flex justify-between text-xs font-semibold text-slate-500 mb-1.5">
                      <span>Concurrency Load</span>
                      <span>
                        {bot.active_conversations} / {bot.max_capacity} chats
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          loadPercent >= 90
                            ? 'bg-red-500'
                            : loadPercent >= 60
                            ? 'bg-amber-500'
                            : 'bg-blue-600'
                        }`}
                        style={{ width: `${Math.max(4, loadPercent)}%` }}
                      />
                    </div>
                  </div>

                  {/* Standalone Live URL preview */}
                  <div className="mt-5 rounded-xl border border-slate-100 bg-slate-50 p-3">
                    <div className="text-[11px] font-semibold text-slate-400 mb-1">
                      STANDALONE LIVE CHAT URL
                    </div>
                    <div className="flex items-center justify-between text-xs font-mono text-slate-700">
                      <span className="truncate max-w-[170px]">/live/{bot.slug}</span>
                      <button
                        onClick={() => copyLiveUrl(bot.slug)}
                        className="text-blue-600 hover:text-blue-700 font-sans font-semibold text-xs ml-2"
                      >
                        {copiedSlug === bot.slug ? '✓ Copied' : 'Copy'}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Card Actions */}
                <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
                  <Link
                    href={`/live/${bot.slug}`}
                    target="_blank"
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-700"
                  >
                    Open Live Chat ↗
                  </Link>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleOpenEditModal(bot)}
                      className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(bot.id)}
                      className="rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Chatbot Create / Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl my-8">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-5">
              <h2 className="text-lg font-bold text-slate-900">
                {editingBot ? 'Edit Chatbot Profile' : 'Create New Chatbot'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveChatbot} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Chatbot Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Maya - Billing Specialist"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Avatar Image URL
                </label>
                <input
                  type="url"
                  placeholder="https://example.com/avatar.jpg"
                  value={formData.avatar_url}
                  onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Welcome Message
                </label>
                <textarea
                  rows={2}
                  value={formData.welcome_message}
                  onChange={(e) => setFormData({ ...formData, welcome_message: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  AI System Instructions & Persona
                </label>
                <textarea
                  rows={3}
                  placeholder="Define persona, tone of voice, answering guidelines..."
                  value={formData.system_instructions}
                  onChange={(e) => setFormData({ ...formData, system_instructions: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                    Max Capacity (Concurrency)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={formData.max_capacity}
                    onChange={(e) => setFormData({ ...formData, max_capacity: parseInt(e.target.value) || 5 })}
                    className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <span className="text-[11px] text-slate-400">Max concurrent active chats</span>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                    Live URL Slug
                  </label>
                  <input
                    type="text"
                    placeholder="my-assistant"
                    value={formData.slug}
                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                    className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <span className="text-[11px] text-slate-400 truncate block">
                    chat.domain.com/live/{formData.slug || 'slug'}
                  </span>
                </div>
              </div>

              {!editingBot && (
                <div className="rounded-xl bg-blue-50 p-3 text-xs text-blue-700 border border-blue-100">
                  ℹ️ Newly created chatbots are <strong>Inactive by default</strong>. You can configure and review them before switching them <strong>ON</strong> to join the live assignment pool.
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  {editingBot ? 'Save Changes' : 'Create Chatbot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

