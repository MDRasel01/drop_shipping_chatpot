import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-xl shadow-md shadow-blue-500/20">
              AI
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">
              SupportOS
            </span>
          </div>
          <nav className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
            >
              Start Free Trial
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="relative overflow-hidden pt-24 pb-20">
          <div className="mx-auto max-w-7xl px-6 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-xs font-semibold text-blue-700 mb-8">
              <span>🚀 Powered by Google Gemini API & pgvector RAG</span>
            </div>
            <h1 className="mx-auto max-w-4xl text-5xl font-extrabold tracking-tight text-slate-900 sm:text-6xl leading-tight">
              Instruction-Driven Customer Support AI That Never Hallucinates
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600 leading-relaxed">
              Empower your website with an AI support assistant that answers customers strictly based on your verified business instructions, documents, and approved knowledge.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link
                href="/register"
                className="rounded-xl bg-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-600/30 hover:bg-blue-700 hover:shadow-blue-600/40 transition-all"
              >
                Register Your Company
              </Link>
              <Link
                href="/dashboard"
                className="rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                View Live Demo
              </Link>
            </div>
          </div>
        </section>

        {/* Feature Highlights */}
        <section className="border-t border-slate-200 bg-white py-20">
          <div className="mx-auto max-w-7xl px-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="rounded-2xl border border-slate-200 p-8 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 font-bold text-2xl mb-6">
                  📚
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">Knowledge Engine</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  Write instructions and upload company policies. Our semantic chunking and Gemini 768d embeddings build a real-time vector search index.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 p-8 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 font-bold text-2xl mb-6">
                  🤖
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">Grounded AI Support</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  Logical AI agent pool handles concurrent chats. Unknown questions are automatically flagged and escalated to human staff.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 p-8 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 font-bold text-2xl mb-6">
                  ⚡
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">Continuous Learning Loop</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  Admin answers unknown customer queries with 1 click. Approved answers are auto-vectorized so the AI immediately knows the answer for all future visitors.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-50 py-8 text-center text-xs text-slate-500">
        © 2026 AI Customer Support SaaS Platform. Built with Google Antigravity & Gemini API.
      </footer>
    </div>
  );
}

