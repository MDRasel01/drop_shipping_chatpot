'use client';

import { useEffect, useState } from 'react';

interface QuestionItem {
  id: string;
  question_text: string;
  status: string;
  frequency: number;
  approved_answer: string | null;
}

export default function QuestionsQueuePage() {
  const [questions, setQuestions] = useState<QuestionItem[]>([
    {
      id: 'demo_q_1',
      question_text: 'Do you provide refrigerated storage for frozen seafood?',
      status: 'UNANSWERED',
      frequency: 3,
      approved_answer: null,
    },
  ]);

  const [activeQuestionId, setActiveQuestionId] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId) {
      fetch(`/api/v1/knowledge/questions?tenant_id=${tenantId}`)
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => {
          if (data && data.length > 0) setQuestions(data);
        })
        .catch(() => {});
    }
  }, []);

  const handleApprove = async (questionId: string) => {
    if (!answerText.trim()) return;
    setLoading(true);
    setMsg(null);

    const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';

    try {
      const res = await fetch(`/api/v1/knowledge/questions/${questionId}/answer?tenant_id=${tenantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer_text: answerText, approved_by: 'Company Admin' }),
      });

      if (!res.ok) throw new Error('Failed to approve answer');

      setQuestions((prev) =>
        prev.map((q) =>
          q.id === questionId
            ? { ...q, status: 'ANSWERED', approved_answer: answerText }
            : q
        )
      );

      setMsg('✅ Answer approved! Vector embeddings generated. The AI now knows the answer for future customers.');
      setActiveQuestionId(null);
      setAnswerText('');
    } catch (err: any) {
      setMsg(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Unknown Questions & Human Handoff Queue</h2>
        <p className="text-sm text-slate-500 mt-1">
          When customer questions score below the 65% confidence threshold, the AI gracefully escalates them here. Approving an answer automatically vectorizes it into knowledge memory.
        </p>
      </div>

      {msg && (
        <div className={`p-4 rounded-xl text-sm font-semibold border ${
          msg.includes('✅')
            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
            : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {msg}
        </div>
      )}

      <div className="space-y-4">
        {questions.map((q) => (
          <div
            key={q.id}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                    q.status === 'ANSWERED'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {q.status}
                  </span>
                  <span className="text-xs text-slate-400">Asked {q.frequency} time(s)</span>
                </div>
                <h3 className="mt-2 text-base font-bold text-slate-900">"{q.question_text}"</h3>
              </div>
            </div>

            {q.approved_answer ? (
              <div className="rounded-xl bg-emerald-50 p-4 border border-emerald-100 text-sm">
                <span className="font-bold text-emerald-900 block mb-1">Approved Knowledge Answer:</span>
                <p className="text-emerald-800">{q.approved_answer}</p>
              </div>
            ) : (
              <div>
                {activeQuestionId === q.id ? (
                  <div className="space-y-3 pt-2">
                    <textarea
                      rows={3}
                      value={answerText}
                      onChange={(e) => setAnswerText(e.target.value)}
                      placeholder="Type the approved answer here..."
                      className="w-full rounded-lg border border-slate-300 p-3 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setActiveQuestionId(null)}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleApprove(q.id)}
                        disabled={loading}
                        className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {loading ? 'Vectorizing...' : 'Approve & Vectorize'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setActiveQuestionId(q.id);
                      setAnswerText('Yes, we operate temperature-controlled refrigerated facilities for frozen seafood at -18°C.');
                    }}
                    className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Provide Approved Answer
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
