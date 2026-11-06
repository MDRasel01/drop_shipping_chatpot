'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';

interface ChatMessage {
  id: string;
  sender: 'visitor' | 'agent';
  content: string;
  time: string;
  isEscalated?: boolean;
}

interface PublicChatbotInfo {
  chatbot_name: string;
  avatar_url?: string;
  welcome_message: string;
  status: string; // online, busy, offline
  theme_color: string;
  slug: string;
}

export default function StandaloneLiveChatPage() {
  const params = useParams();
  const slug = params?.slug as string;

  const [botInfo, setBotInfo] = useState<PublicChatbotInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chat Session State
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMsg, setInputMsg] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [assignedBotName, setAssignedBotName] = useState<string | null>(null);
  const [assignedBotAvatar, setAssignedBotAvatar] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isConnecting, isSending]);

  // 1. Fetch Public Chatbot Info & Initialize Visitor Session
  useEffect(() => {
    if (!slug) return;

    const initChat = async () => {
      try {
        // Fetch public branding
        const infoRes = await fetch(`/api/v1/public/live/${slug}`);
        if (!infoRes.ok) {
          throw new Error('This live chat link is not active or does not exist.');
        }
        const infoData: PublicChatbotInfo = await infoRes.json();
        setBotInfo(infoData);
        setAssignedBotName(infoData.chatbot_name);
        setAssignedBotAvatar(infoData.avatar_url || null);

        // Initialize Anonymous Visitor Session
        const sessRes = await fetch(`/api/v1/public/live/${slug}/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ origin: window.location.origin }),
        });

        if (!sessRes.ok) {
          throw new Error('Unable to establish live chat session.');
        }

        const sessData = await sessRes.json();
        setSessionToken(sessData.session_token);
        setConversationId(sessData.conversation_id);

        // Add Welcome Message
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        setMessages([
          {
            id: 'welcome',
            sender: 'agent',
            content: sessData.welcome_message,
            time: now,
          },
        ]);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    initChat();
  }, [slug]);

  // 2. Send Visitor Message Turn
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMsg.trim() || !sessionToken || isSending) return;

    const userText = inputMsg.trim();
    setInputMsg('');

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: ChatMessage = {
      id: `vis_${Date.now()}`,
      sender: 'visitor',
      content: userText,
      time: now,
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);

    // If first customer message, show the 1-3s connecting indicator
    const isFirstCustomerMessage = messages.filter((m) => m.sender === 'visitor').length === 0;
    if (isFirstCustomerMessage) {
      setIsConnecting(true);
    }

    try {
      const startTime = Date.now();

      const res = await fetch(`/api/v1/public/live/${slug}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({ message: userText }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Message failed to send');
      }

      // Ensure at least 1.2s connecting animation for realistic multi-chatbot routing experience on first message
      const elapsed = Date.now() - startTime;
      if (isFirstCustomerMessage && elapsed < 1200) {
        await new Promise((resolve) => setTimeout(resolve, 1200 - elapsed));
      }

      setIsConnecting(false);

      if (data.assigned_chatbot_name) {
        setAssignedBotName(data.assigned_chatbot_name);
      }
      if (data.assigned_chatbot_avatar) {
        setAssignedBotAvatar(data.assigned_chatbot_avatar);
      }

      const replyMsg: ChatMessage = {
        id: data.message_id,
        sender: 'agent',
        content: data.content,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isEscalated: data.is_escalated,
      };

      setMessages((prev) => [...prev, replyMsg]);
    } catch (err: any) {
      setIsConnecting(false);
      const errMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: 'agent',
        content: '⚠️ Unable to connect to assistant right now. Please try again in a few moments.',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent mx-auto"></div>
          <p className="mt-4 text-sm font-semibold text-slate-600">Connecting to Live Chat...</p>
        </div>
      </div>
    );
  }

  if (error || !botInfo) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-2xl">
            💬
          </div>
          <h2 className="mt-4 text-lg font-bold text-slate-900">Live Chat Unavailable</h2>
          <p className="mt-2 text-sm text-slate-500">{error || 'This chatbot link is not currently available.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      {/* Top Banner & Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            {assignedBotAvatar ? (
              <img
                src={assignedBotAvatar}
                alt={assignedBotName || 'AI Assistant'}
                className="h-10 w-10 rounded-xl object-cover border border-slate-200"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 font-bold text-white shadow-sm">
                {(assignedBotName || 'AI').slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-slate-900">
                  {assignedBotName || botInfo.chatbot_name}
                </h1>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  ONLINE
                </span>
              </div>
              <p className="text-xs text-slate-400">Verified AI Customer Support</p>
            </div>
          </div>

          <div className="text-right hidden sm:block">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              MULTI-CHATBOT LIVE POOL
            </span>
          </div>
        </div>
      </header>

      {/* Messages Stream Container */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-6 space-y-4">
          {/* Security & Anonymous Badge */}
          <div className="text-center my-2">
            <span className="inline-block rounded-full bg-slate-200/60 px-3 py-1 text-[11px] font-medium text-slate-600">
              🔒 End-to-end encrypted anonymous visitor session
            </span>
          </div>

          {messages.map((msg) => {
            const isVisitor = msg.sender === 'visitor';

            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isVisitor ? 'justify-end' : 'justify-start'}`}
              >
                {!isVisitor && (
                  <div className="flex-shrink-0">
                    {assignedBotAvatar ? (
                      <img
                        src={assignedBotAvatar}
                        alt="Bot"
                        className="h-8 w-8 rounded-lg object-cover border border-slate-200 mt-1"
                      />
                    ) : (
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 font-bold text-white text-xs mt-1">
                        AI
                      </div>
                    )}
                  </div>
                )}

                <div className={`max-w-[85%] sm:max-w-md ${isVisitor ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                      isVisitor
                        ? 'bg-blue-600 text-white rounded-br-sm'
                        : 'bg-white text-slate-900 border border-slate-200 rounded-bl-sm'
                    }`}
                  >
                    {msg.content}
                  </div>

                  <div
                    className={`mt-1 flex items-center gap-1.5 text-[10px] text-slate-400 px-1 ${
                      isVisitor ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <span>{msg.time}</span>
                    {msg.isEscalated && (
                      <span className="font-semibold text-amber-600">· Escalated</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Connecting State (Customer loading experience) */}
          {isConnecting && (
            <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-2xl p-4 text-blue-800 text-sm animate-pulse">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              <div>
                <p className="font-bold">Connecting you to an available chatbot...</p>
                <p className="text-xs text-blue-600">Selecting least-loaded assistant from active pool.</p>
              </div>
            </div>
          )}

          {/* Typing Indicator */}
          {isSending && !isConnecting && (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-1 pl-11">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.3s]"></span>
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.15s]"></span>
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce"></span>
              </span>
              <span>{assignedBotName || 'Assistant'} is formulating answer...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Bar */}
      <footer className="sticky bottom-0 z-10 border-t border-slate-200 bg-white p-4">
        <div className="mx-auto max-w-3xl">
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input
              type="text"
              autoFocus
              placeholder="Type your question or request..."
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              disabled={isSending}
              className="flex-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm focus:border-blue-600 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-600 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!inputMsg.trim() || isSending}
              className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <span>Send</span>
              <span>➤</span>
            </button>
          </form>

          <div className="mt-2 text-center text-[10px] text-slate-400">
            Powered by Google Gemini 1.5 & SupportOS Multi-Chatbot Engine
          </div>
        </div>
      </footer>
    </div>
  );
}

