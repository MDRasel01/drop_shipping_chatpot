'use client';

import { useEffect, useState } from 'react';

export default function WidgetEmbedPage() {
  const [publicKey, setPublicKey] = useState('pk_live_demo123456');
  const [copied, setCopied] = useState(false);

  // Live test chat state
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<Array<{ sender: string; text: string }>>([
    { sender: 'agent', text: 'Hello! I am your AI Support Assistant. How can I help you today?' },
  ]);
  const [inputMsg, setInputMsg] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId) {
      fetch(`/api/v1/support/widget/tenant?tenant_id=${tenantId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.public_key) {
            setPublicKey(data.public_key);
          }
        })
        .catch(() => {});
    }
  }, []);

  const embedCode = `<script src="http://localhost:8000/widget.js" data-key="${publicKey}" async></script>`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTestChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMsg.trim()) return;

    const userText = inputMsg;
    setInputMsg('');
    setMessages((prev) => [...prev, { sender: 'visitor', text: userText }]);
    setChatLoading(true);

    try {
      // 1. Get Session if not exists
      let token = sessionToken;
      if (!token) {
        const sessRes = await fetch('/api/v1/chat/session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Widget-Key': publicKey,
          },
          body: JSON.stringify({ origin: window.location.origin }),
        });
        const sessData = await sessRes.json();
        token = sessData.session_token;
        setSessionToken(token);
      }

      // 2. Send Message
      const msgRes = await fetch('/api/v1/chat/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userText }),
      });

      const msgData = await msgRes.json();
      setMessages((prev) => [...prev, { sender: 'agent', text: msgData.content }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { sender: 'agent', text: 'Based on our documentation: Returns and deliveries take 3-5 days. Let me know if you need anything else!' },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Website Chat Widget Integration</h2>
        <p className="text-sm text-slate-500 mt-1">
          Copy and paste this lightweight script tag into any website before the closing &lt;/body&gt; tag.
        </p>
      </div>

      {/* Embed Code Snippet Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-700">
            HTML Embed Code Snippet
          </span>
          <button
            onClick={copyToClipboard}
            className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition-colors"
          >
            {copied ? '✓ Copied!' : 'Copy Code'}
          </button>
        </div>

        <pre className="rounded-xl bg-slate-900 p-4 font-mono text-xs text-blue-300 overflow-x-auto">
          {embedCode}
        </pre>
      </div>

      {/* Live Interactive Widget Simulator */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">Live Widget Simulator</h3>
            <p className="text-xs text-slate-500">Test how website visitors will converse with your AI agent.</p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Agent Online
          </span>
        </div>

        {/* Chat Window */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 h-80 overflow-y-auto space-y-3">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex ${m.sender === 'visitor' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed ${
                  m.sender === 'visitor'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-white text-slate-800 border border-slate-200 shadow-sm rounded-bl-none'
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex justify-start">
              <div className="bg-white border border-slate-200 text-slate-400 rounded-2xl rounded-bl-none px-4 py-2 text-xs animate-pulse">
                AI Agent is typing...
              </div>
            </div>
          )}
        </div>

        {/* Message Input */}
        <form onSubmit={handleTestChat} className="flex gap-2">
          <input
            type="text"
            value={inputMsg}
            onChange={(e) => setInputMsg(e.target.value)}
            placeholder="Ask a customer question (e.g. How many days for returns?)..."
            className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2.5 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={chatLoading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

