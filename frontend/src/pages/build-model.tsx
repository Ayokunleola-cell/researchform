import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import AppLayout from '../components/layout/AppLayout';
import { 
  RiCpuLine, 
  RiSparklingFill, 
  RiTimerLine, 
  RiCheckLine, 
  RiSendPlaneFill, 
  RiSchoolLine, 
  RiMailLine, 
  RiCompass3Line,
  RiTerminalBoxLine,
  RiUser3Line,
  RiToolsLine,
  RiArrowRightLine,
  RiShieldCheckLine,
  RiRocketLine,
  RiFolder3Line
} from 'react-icons/ri';
import toast from 'react-hot-toast';

interface ProjectRequest {
  id: string;
  fullName: string;
  projectName: string;
  projectType: string;
  email: string;
  schoolName: string;
  framework: string;
  datasetSize: string;
  description: string;
  submittedAt: string;
  status: 'Request Received' | 'Building & Training' | 'Model Deployed';
}

const PROJECT_TYPES = [
  'Natural Language Processing / LLM',
  'Computer Vision & Image Recognition',
  'Predictive Analytics & Tabular ML',
  'Deep Learning & Neural Networks',
  'Time-Series & Financial Forecasting',
  'Reinforcement Learning',
  'Other Academic Thesis / Capstone'
];

const FRAMEWORKS = ['PyTorch', 'TensorFlow', 'HuggingFace', 'Scikit-Learn', 'JAX'];

export default function BuildModelPage() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [requests, setRequests] = useState<ProjectRequest[]>([]);

  // Form state
  const [fullName, setFullName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [projectType, setProjectType] = useState(PROJECT_TYPES[0]);
  const [email, setEmail] = useState('');
  const [schoolName, setSchoolName] = useState('');
  const [framework, setFramework] = useState('PyTorch');
  const [datasetSize, setDatasetSize] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const user = JSON.parse(localStorage.getItem('rf_user') || '{}');
      if (user?.full_name && !fullName) {
        setFullName(user.full_name);
      }
      if (user?.email && !email) {
        setEmail(user.email);
      }
      if (user?.institution && !schoolName) {
        setSchoolName(user.institution);
      }

      const saved = localStorage.getItem('rf_build_model_requests');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setRequests(parsed);
          if (parsed.length > 0) {
            setIsSubmitted(true);
          }
        } catch (e) {}
      }
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      toast.error('Please enter your full name');
      return;
    }
    if (!projectName.trim()) {
      toast.error('Please enter your project or thesis title');
      return;
    }
    if (!email.trim() || !email.includes('@')) {
      toast.error('Please enter a valid email address');
      return;
    }
    if (!schoolName.trim()) {
      toast.error('Please enter your school or university name');
      return;
    }

    setLoading(true);

    setTimeout(() => {
      const newRequest: ProjectRequest = {
        id: `req_${Date.now().toString(36)}`,
        fullName,
        projectName,
        projectType,
        email,
        schoolName,
        framework,
        datasetSize: datasetSize.trim() || 'Not specified',
        description,
        submittedAt: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        status: 'Request Received'
      };

      const updated = [newRequest, ...requests];
      setRequests(updated);
      localStorage.setItem('rf_build_model_requests', JSON.stringify(updated));
      setIsSubmitted(true);
      setLoading(false);
      
      setProjectName('');
      setDatasetSize('');
      setDescription('');

      toast.success("Request submitted! Our AI team will review your project details and get back to you to start building your model.");
    }, 600);
  };

  return (
    <AppLayout title="Build Model">
      <Head>
        <title>Build Model | ResearchForm</title>
        <meta name="description" content="We help students build, train and deploy AI models for school projects, thesis and academic research." />
      </Head>

      <div className="max-w-6xl mx-auto space-y-8 pb-16 animate-in fade-in duration-300">
        
        {/* ── Hero Header Card — same design DNA as Power Analysis ── */}
        <div style={{
          position: 'relative', borderRadius: 24, overflow: 'hidden', marginBottom: 28,
          background: 'linear-gradient(135deg, #090D16 0%, #111827 50%, #0F172A 100%)',
          border: '1px solid #1E293B',
          boxShadow: '0 20px 40px -15px rgba(0,0,0,0.4)',
          padding: '32px 40px',
          color: '#FFFFFF',
        }}>
          {/* Glowing ambient orbs */}
          <div style={{ position: 'absolute', top: -70, right: -70, width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%)', filter: 'blur(35px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -80, left: '18%', width: 360, height: 360, borderRadius: '50%', background: 'radial-gradient(circle, rgba(16,185,129,0.18) 0%, transparent 70%)', filter: 'blur(45px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', top: '30%', left: -60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)', filter: 'blur(30px)', pointerEvents: 'none' }} />

          {/* Subtle dot-grid texture overlay */}
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.04,
            backgroundImage: 'radial-gradient(circle, #ffffff 1px, transparent 1px)',
            backgroundSize: '22px 22px',
          }} />

          {/* Content */}
          <div style={{ position: 'relative', zIndex: 1, maxWidth: 800 }}>
            {/* Main title */}
            <h1 style={{
              margin: '0', fontSize: 34, fontWeight: 800,
              color: '#FFFFFF', fontFamily: 'Syne, sans-serif',
              lineHeight: 1.15, letterSpacing: '-0.02em',
              textShadow: '0 2px 12px rgba(0,0,0,0.4)',
            }}>
              We Help Build, Train & Deploy AI Models for Project & Thesis
            </h1>
            
            {/* Subtitle */}
            <p style={{ margin: '14px 0 0', color: '#94A3B8', fontSize: 15, lineHeight: 1.6, maxWidth: 720 }}>
              From dataset preparation and model architecture to training and final deployment, ResearchForm helps students and academic researchers build custom AI models for school projects, capstones, and thesis research.
            </p>

            {/* Success Notification Pill (When Form Submitted) */}
            {isSubmitted && (
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: '#34D399', fontSize: 14, fontWeight: 600 }}>
                  <span style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(52,211,153,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>✓</span>
                  <span>Project Request Received! Our team is reviewing your project requirements and will reach out to you shortly.</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── 3 FEATURE CARDS GRID (Accurate What We Do) ── */}
        <div className="grid md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-7 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-xl bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-[var(--text)]">
                <RiSparklingFill size={20} />
              </div>
              <h3 className="text-lg font-bold text-[var(--text)] leading-snug">
                Custom Model Architecture & Training
              </h3>
              <p className="text-sm text-[var(--text-2)] leading-relaxed">
                We help you select, design, and train the right AI models for your research goals—whether you need NLP, computer vision, tabular predictive ML, or deep learning.
              </p>
            </div>
          </div>

          {/* Card 2 */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-7 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-xl bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-[var(--text)]">
                <RiCpuLine size={20} />
              </div>
              <h3 className="text-lg font-bold text-[var(--text)] leading-snug">
                Fast GPU Compute & Execution
              </h3>
              <p className="text-sm text-[var(--text-2)] leading-relaxed">
                No need to worry about GPU hardware, CUDA drivers, or local RAM limits. We handle the heavy compute execution so your model trains smoothly and fast.
              </p>
            </div>
          </div>

          {/* Card 3 */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-7 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-xl bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-[var(--text)]">
                <RiRocketLine size={20} />
              </div>
              <h3 className="text-lg font-bold text-[var(--text)] leading-snug">
                Thesis-Ready Output & Deployment
              </h3>
              <p className="text-sm text-[var(--text-2)] leading-relaxed">
                Get clean evaluation metrics, performance charts, and deployable model endpoints ready to present in your project report, submission, or thesis defense.
              </p>
            </div>
          </div>
        </div>

        {/* ── PROJECT REQUEST FORM ── */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-sm overflow-hidden">
          <div className="p-6 md:p-8 border-b border-[var(--border)] bg-[var(--surface-2)]">
            <h2 className="text-xl font-bold text-[var(--text)]">
              Submit Your AI Model Requirements
            </h2>
            <p className="text-sm text-[var(--text-2)] mt-1">
              Provide details about your project or thesis topic below. Our AI team will review your goals and help you build, train, and deploy your model.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-6 md:p-8 space-y-6">
            <div className="grid md:grid-cols-2 gap-6">
              {/* Full Name */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  Full Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <RiUser3Line className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
                  />
                </div>
              </div>

              {/* Email Address */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  Email Address <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <RiMailLine className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
                  />
                </div>
              </div>

              {/* School / Institution */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  School / University Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <RiSchoolLine className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <input
                    type="text"
                    required
                    value={schoolName}
                    onChange={(e) => setSchoolName(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
                  />
                </div>
              </div>

              {/* Project Title */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  Project Title / Thesis Topic <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <RiFolder3Line className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <input
                    type="text"
                    required
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
                  />
                </div>
              </div>

              {/* Project Type Dropdown */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  Project Category <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <RiCompass3Line className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <select
                    value={projectType}
                    onChange={(e) => setProjectType(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all appearance-none cursor-pointer"
                  >
                    {PROJECT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Estimated Dataset Size */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                  Estimated Dataset Size / Dataset Description (Optional)
                </label>
                <div className="relative">
                  <RiCpuLine className="absolute left-3.5 top-3.5 text-[var(--text-3)]" size={18} />
                  <input
                    type="text"
                    value={datasetSize}
                    onChange={(e) => setDatasetSize(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
                  />
                </div>
              </div>
            </div>

            {/* Framework Pills */}
            <div className="space-y-2 pt-2">
              <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                Preferred ML Framework / Tools
              </label>
              <div className="flex flex-wrap gap-3">
                {FRAMEWORKS.map((fw) => (
                  <button
                    type="button"
                    key={fw}
                    onClick={() => setFramework(fw)}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
                      framework === fw
                        ? 'bg-[#0066FF] text-white border-[#0066FF] shadow-sm'
                        : 'bg-[var(--surface-2)] text-[var(--text-2)] border-[var(--border)] hover:text-[var(--text)]'
                    }`}
                  >
                    {fw}
                  </button>
                ))}
              </div>
            </div>

            {/* Detailed Project Goal */}
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block">
                Project Goals & What You Want to Accomplish
              </label>
              <textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-3.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-sm text-[var(--text)] focus:outline-none focus:border-[#0066FF] transition-all"
              />
            </div>

            {/* Form Actions */}
            <div className="pt-4 flex justify-end border-t border-[var(--border)]">
              <button
                type="submit"
                disabled={loading}
                className="w-full md:w-auto px-8 py-3 bg-[#0066FF] hover:bg-[#0052cc] text-white font-bold text-sm rounded-xl transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 disabled:opacity-70 cursor-pointer"
              >
                {loading ? (
                  <span>Submitting request...</span>
                ) : (
                  <>
                    <RiSendPlaneFill size={18} />
                    <span>Submit Project</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* ── SUBMITTED REQUESTS ── */}
        {requests.length > 0 && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-lg font-bold text-[var(--text)] flex items-center gap-2">
              <RiTerminalBoxLine className="text-[var(--text-2)]" size={20} />
              Your Model Build Requests ({requests.length})
            </h3>

            <div className="divide-y divide-[var(--border)] border border-[var(--border)] rounded-xl overflow-hidden">
              {requests.map((req) => (
                <div key={req.id} className="p-4 bg-[var(--surface)] hover:bg-[var(--surface-2)] transition-colors flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-sm text-[var(--text)]">{req.projectName}</h4>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#0066FF]/10 text-[#0066FF] font-semibold">
                        {req.framework}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-2)] mt-0.5">
                      {req.fullName} ({req.email}) • {req.projectType} • {req.schoolName}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    <span className="text-xs text-[var(--text-3)]">{req.submittedAt}</span>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      {req.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </AppLayout>
  );
}
