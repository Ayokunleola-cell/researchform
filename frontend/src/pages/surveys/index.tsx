// src/pages/surveys/index.tsx
import React from 'react';
import AppLayout from '../../components/layout/AppLayout';
import PageHeader from '../../components/ui/PageHeader';
import ResearchWorkflow from '../../components/ui/ResearchWorkflow';
import EmptyState from '../../components/ui/EmptyState';
import Link from 'next/link';
import { surveysApi } from '../../lib/api';
import useSWR from 'swr';
import { RiAddFill, RiGroupFill, RiExternalLinkFill, RiEdit2Fill, RiErrorWarningFill, RiBarChart2Fill, RiFileTextFill, RiDeleteBinFill, RiTimeFill, RiCheckboxCircleFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

const STATUS: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Draft',    cls: 'badge-neutral' },
  active:   { label: 'Active',   cls: 'badge-success' },
  closed:   { label: 'Closed',   cls: 'badge-warning' },
  analysed: { label: 'Analysed', cls: 'badge-brand' },
};

export default function SurveysPage() {
  const { data: surveysData, isLoading, mutate: mutateSurveys } = useSWR('/surveys');
  const surveys: any[] = surveysData || [];
  const loading = isLoading;

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    await surveysApi.delete(id);
    toast.success('Survey deleted');
    mutateSurveys();
  };

  return (
    <AppLayout
      title="Surveys"
      breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Surveys' }]}
    >
      <div className="page-container page-stack">
        <ResearchWorkflow />
        <PageHeader
          title="Your surveys"
          description={`${surveys.length} survey${surveys.length !== 1 ? 's' : ''} — collect responses, then export or analyze in the Analysis tab.`}
          actions={
            <Link href="/surveys/new">
              <button type="button" className="btn btn-primary btn-sm"><RiAddFill size={16} /> New Survey</button>
            </Link>
          }
        />

        {loading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
        ) : surveys.length === 0 ? (
          <EmptyState
            icon={RiFileTextFill}
            title="No surveys yet"
            description="Create your first survey to start collecting research data from respondents."
            action={
              <Link href="/surveys/new">
                <button type="button" className="btn btn-primary"><RiAddFill size={16} /> Create Survey</button>
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {surveys.map((s: any) => {
              const st = STATUS[s.status] || STATUS.draft;
              return (
                <div key={s.id} className="card p-5 flex items-center gap-4 card-hover">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.1)' }}>
                    <RiFileTextFill size={22} style={{ color: 'var(--brand)' }} />
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
                        <button className="btn btn-ghost btn-icon btn-sm" title="Open survey"><RiExternalLinkFill size={15} /></button>
                      </a>
                    )}
                    <Link href={`/surveys/${s.id}/edit`}>
                      <button className="btn btn-ghost btn-icon btn-sm" title="Edit"><RiEdit2Fill size={15} /></button>
                    </Link>
                    <button className="btn btn-ghost btn-icon btn-sm" style={{ color: 'var(--danger)' }}
                      onClick={() => handleDelete(s.id, s.title)} title="Delete">
                      <RiDeleteBinFill size={15} />
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
