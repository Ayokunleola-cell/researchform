// src/pages/surveys/index.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import Link from 'next/link';
import { surveysApi } from '../../lib/api';
import { Plus, FileText, Users, CheckCircle, Clock, AlertCircle, BarChart3, Trash2, Edit, ExternalLink } from 'lucide-react';
import toast from 'react-hot-toast';

const STATUS: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Draft',    cls: 'badge-neutral' },
  active:   { label: 'Active',   cls: 'badge-success' },
  closed:   { label: 'Closed',   cls: 'badge-warning' },
  analysed: { label: 'Analysed', cls: 'badge-brand' },
};

export default function SurveysPage() {
  const [surveys, setSurveys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => surveysApi.list().then(r => setSurveys(r.data || [])).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    await surveysApi.delete(id);
    toast.success('Survey deleted');
    load();
  };

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--text)' }}>Surveys</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>{surveys.length} survey{surveys.length !== 1 ? 's' : ''}</p>
          </div>
          <Link href="/surveys/new"><button className="btn btn-primary"><Plus size={16} /> New Survey</button></Link>
        </div>

        {loading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
        ) : surveys.length === 0 ? (
          <div className="card p-16 text-center">
            <FileText size={48} className="mx-auto mb-4" style={{ color: 'var(--text-3)' }} />
            <p className="font-display font-bold text-lg mb-2" style={{ color: 'var(--text)' }}>No surveys yet</p>
            <p className="text-sm mb-6" style={{ color: 'var(--text-2)' }}>Create your first survey to start collecting research data</p>
            <Link href="/surveys/new"><button className="btn btn-primary"><Plus size={16} /> Create Survey</button></Link>
          </div>
        ) : (
          <div className="space-y-3">
            {surveys.map((s: any) => {
              const st = STATUS[s.status] || STATUS.draft;
              return (
                <div key={s.id} className="card p-5 flex items-center gap-4 card-hover">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.1)' }}>
                    <FileText size={22} style={{ color: 'var(--brand)' }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Link href={`/surveys/${s.id}`}>
                        <span className="font-semibold hover:underline cursor-pointer" style={{ color: 'var(--text)' }}>{s.title}</span>
                      </Link>
                      <span className={`badge ${st.cls} text-xs`}>{st.label}</span>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-3)' }}>
                      {s.response_count} response{s.response_count !== 1 ? 's' : ''} ·
                      {s.question_count} question{s.question_count !== 1 ? 's' : ''} ·
                      Created {new Date(s.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {s.status === 'active' && s.slug && (
                      <a href={`/s/${s.slug}`} target="_blank" rel="noreferrer">
                        <button className="btn btn-ghost btn-icon btn-sm" title="Open survey"><ExternalLink size={15} /></button>
                      </a>
                    )}
                    <Link href={`/surveys/${s.id}/edit`}>
                      <button className="btn btn-ghost btn-icon btn-sm" title="Edit"><Edit size={15} /></button>
                    </Link>
                    <button className="btn btn-ghost btn-icon btn-sm" style={{ color: 'var(--danger)' }}
                      onClick={() => handleDelete(s.id, s.title)} title="Delete">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
