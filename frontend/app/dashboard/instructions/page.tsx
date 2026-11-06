'use client';

import { useState } from 'react';

export default function InstructionsPage() {
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const [instruction, setInstruction] = useState({
    title: 'Return and Refund Policy',
    content: `Standard delivery takes 3 to 5 business days across all regions.\n\nReturns and exchanges are accepted within 30 days of delivery with the original purchase receipt and un-opened packaging.\n\nRefunds are processed to the original payment method within 48 hours of inspection.`,
  });

  const [publishedId, setPublishedId] = useState<string | null>(null);

  const handleSaveAndPublish = async () => {
    setLoading(true);
    setStatusMsg(null);

    const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';

    try {
      // 1. Create Draft
      const draftRes = await fetch(`/api/v1/knowledge/instructions?tenant_id=${tenantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(instruction),
      });

      const draftData = await draftRes.json();
      if (!draftRes.ok) throw new Error(draftData.detail || 'Failed to save instruction');

      // 2. Publish (Generate semantic chunks & Gemini 768d vector embeddings)
      const pubRes = await fetch(`/api/v1/knowledge/instructions/${draftData.id}/publish?tenant_id=${tenantId}`, {
        method: 'POST',
      });

      const pubData = await pubRes.json();
      if (!pubRes.ok) throw new Error(pubData.detail || 'Failed to publish to vector index');

      setPublishedId(pubData.id);
      setStatusMsg('✅ Instructions successfully chunked, vectorized, and published to AI pgvector memory!');
    } catch (err: any) {
      setStatusMsg(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Knowledge & Business Instructions</h2>
        <p className="text-sm text-slate-500 mt-1">
          Your AI Customer Support Agent uses these verified instructions to answer customer inquiries. The AI will never answer with information outside this knowledge base.
        </p>
      </div>

      {statusMsg && (
        <div className={`p-4 rounded-xl text-sm font-semibold border ${
          statusMsg.includes('✅')
            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
            : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {statusMsg}
        </div>
      )}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
            Instruction Document Title
          </label>
          <input
            type="text"
            value={instruction.title}
            onChange={(e) => setInstruction({ ...instruction, title: e.target.value })}
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
            Verified Content & Guidelines (Markdown supported)
          </label>
          <textarea
            rows={10}
            value={instruction.content}
            onChange={(e) => setInstruction({ ...instruction, content: e.target.value })}
            className="w-full rounded-lg border border-slate-300 p-3.5 text-sm font-mono text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 leading-relaxed"
          />
          <p className="mt-2 text-xs text-slate-400">
            Separate sections with double line breaks for optimal semantic chunking.
          </p>
        </div>

        <div className="pt-3 flex items-center justify-between border-t border-slate-100">
          <div className="text-xs text-slate-500">
            Status: <span className="font-semibold text-emerald-600">{publishedId ? 'Published to Vector DB' : 'Ready to Publish'}</span>
          </div>
          <button
            onClick={handleSaveAndPublish}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Chunking & Vectorizing...' : 'Save & Publish to AI Memory'}
          </button>
        </div>
      </div>
    </div>
  );
}
