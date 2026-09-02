import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Image from 'next/image';
import { FiArrowRight, FiCpu, FiLayers, FiSearch, FiShoppingCart, FiActivity } from 'react-icons/fi';

export default function LandingPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');

  const handleMarketplaceSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/marketplace/browse?q=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      router.push('/marketplace/browse');
    }
  };
  return (
    <div className="min-h-screen bg-[#09090b] text-white font-sans antialiased selection:bg-emerald-500 selection:text-black">
      
      {/* ── 1. Top Navigation Bar (Sleek Dark Obsidian) ──────────────────── */}
      <header className="sticky top-0 z-50 bg-[#09090b]/85 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          
          {/* Brand Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-slate-950 shadow-md group-hover:scale-105 transition-transform">
              <span className="font-extrabold text-lg tracking-wider">RF</span>
            </div>
            <span className="font-bold text-2xl tracking-tight text-white">
              ResearchForm
            </span>
          </Link>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <Link href="#analysis" className="hover:text-white transition-colors">
              Analysis
            </Link>
            <Link href="#survey" className="hover:text-white transition-colors">
              Survey
            </Link>
            <Link href="#report" className="hover:text-white transition-colors">
              Report
            </Link>
            <Link href="#gpu" className="hover:text-white transition-colors">
              GPU
            </Link>
          </nav>

          {/* Action CTAs */}
          <div className="flex items-center gap-4">
            <Link 
              href="/login" 
              className="text-sm font-semibold text-slate-300 hover:text-white px-4 py-2.5 transition-colors"
            >
              Log in
            </Link>
            <Link 
              href="/login"
              className="inline-flex items-center gap-2 text-sm font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-5 py-2.5 rounded-full shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-all duration-200"
            >
              <span>Get Started</span>
              <div className="w-6 h-6 rounded-full bg-slate-950 text-white flex items-center justify-center">
                <FiArrowRight className="w-3.5 h-3.5" />
              </div>
            </Link>
          </div>
        </div>
      </header>

      {/* ── 2. Hero Section (Glowing Vector Lines & Notion Bold Headline) ── */}
      <section className="relative overflow-hidden pt-16 pb-20 md:pt-24 md:pb-28">
        
        {/* Glowing Background Flow Lines (Pop Against Black) */}
        <div className="absolute inset-0 pointer-events-none opacity-45">
          <svg className="w-full h-full" viewBox="0 0 1440 800" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M-100 200 C 300 100, 700 600, 1540 200" stroke="#34d399" strokeWidth="2" strokeOpacity="0.5" fill="none"/>
            <path d="M-100 250 C 400 150, 800 700, 1540 300" stroke="#10b981" strokeWidth="1.5" strokeOpacity="0.4" fill="none"/>
            <path d="M-100 350 C 500 200, 900 750, 1540 400" stroke="#6ee7b7" strokeWidth="1.5" strokeOpacity="0.3" fill="none"/>
          </svg>
        </div>

        {/* Ambient Top Glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-emerald-500/10 blur-[130px] rounded-full pointer-events-none" />

        <div className="relative max-w-5xl mx-auto px-6 text-center">
          
          {/* Main Headline */}
          <h1 
            style={{ fontFamily: "'Archivo Black', sans-serif" }}
            className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tight text-white leading-[1.08] mb-8"
          >
            From survey to <br className="hidden sm:inline" />
            <span className="relative inline-block text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-200">
              analysis report
            </span>
          </h1>

          {/* Subheading (User's Exact Words) */}
          <p className="text-xl sm:text-2xl md:text-3xl text-slate-300 font-normal max-w-3xl mx-auto leading-relaxed mb-10">
            Analysis your project or dissertation at your comfort within maximum of 10min and get report.
          </p>

          {/* Primary CTA Button (Notch Pill Style with Glow) */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Link 
              href="/login"
              className="inline-flex items-center gap-3 text-base font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-8 py-4 rounded-full shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all duration-200 hover:-translate-y-0.5"
            >
              <span>Get Started</span>
              <div className="w-8 h-8 rounded-full bg-slate-950 text-white flex items-center justify-center">
                <FiArrowRight className="w-4 h-4" />
              </div>
            </Link>
          </div>

          {/* Trust Logo Bar (Clean Grayscale against Black) */}
          <div className="pt-8 border-t border-white/10 flex flex-wrap items-center justify-center gap-10 md:gap-16 opacity-60">
            <span className="font-extrabold tracking-wider text-sm text-slate-300 uppercase">SPSS .SAV</span>
            <span className="font-extrabold tracking-wider text-sm text-slate-300 uppercase">EXCEL .XLSX</span>
            <span className="font-extrabold tracking-wider text-sm text-slate-300 uppercase">APA 7TH EDITION</span>
            <span className="font-extrabold tracking-wider text-sm text-slate-300 uppercase">SURVEY</span>
          </div>

          {/* Marketplace Search Bar Section */}
          <div className="mt-20 md:mt-24 pt-4 max-w-4xl mx-auto text-center">
            {/* Captivating Headline */}
            <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight text-white mb-8 leading-[1.15]">
              Find the exact{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-teal-200 to-cyan-300">
                survey dataset
              </span>{' '}
              you need for your study.
            </h2>

            {/* Capsule Search Bar Form */}
            <form onSubmit={handleMarketplaceSearch} className="relative flex items-center group max-w-2xl mx-auto">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search survey datasets, research templates, scales..."
                className="w-full bg-[#18181b]/95 hover:bg-[#202024] focus:bg-[#18181b] text-white placeholder-slate-400 text-sm sm:text-base rounded-full pl-6 pr-14 py-4 border border-white/15 hover:border-white/30 focus:border-emerald-400 focus:outline-none shadow-2xl transition-all"
              />
              <button
                type="submit"
                aria-label="Search Marketplace"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 active:scale-95 transition-all"
              >
                <FiSearch className="w-5 h-5 text-slate-300 group-hover:text-emerald-400 transition-colors" />
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* ── 3. Feature Bento Grid (Sleek Dark Cards with User Pictures) ───── */}
      <section id="survey" className="py-16 md:py-24 bg-[#09090b] border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6">
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-stretch">
            
            {/* Bento Card 1: Easy Survey Builder with Student Picture */}
            <div className="rounded-3xl bg-[#121215] border border-white/10 p-8 sm:p-12 flex flex-col justify-between overflow-hidden relative group hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/5 transition-all">
              <div className="mb-8">
                <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center text-white shadow-sm mb-6">
                  <FiLayers className="w-6 h-6 text-emerald-400" />
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4 leading-snug">
                  Easy survey builder to capture all type of data capturing.
                </h2>
              </div>

              {/* Picture 1: Student in Green Sweater with Notebook */}
              <div className="relative w-full h-80 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-white/10 bg-slate-900">
                <Image
                  src="/images/student_green.jpg"
                  alt="Student with survey notebook"
                  fill
                  className="object-cover object-center group-hover:scale-105 transition-transform duration-500"
                  priority
                />
              </div>
            </div>

            {/* Bento Card 2: Statistical Tests with Professional Picture */}
            <div className="rounded-3xl bg-[#121215] border border-white/10 p-8 sm:p-12 flex flex-col justify-between overflow-hidden relative group hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/5 transition-all">
              <div className="mb-8">
                <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center text-white shadow-sm mb-6">
                  <FiCpu className="w-6 h-6 text-emerald-400" />
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4 leading-snug">
                  Highly standard statistical tests for deep analysis.
                </h2>
              </div>

              {/* Picture 3: Professional with Clipboard and Glasses */}
              <div className="relative w-full h-80 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-white/10 bg-slate-900">
                <Image
                  src="/images/professional_clipboard.jpg"
                  alt="Professional with data analytics clipboard"
                  fill
                  className="object-cover object-center group-hover:scale-105 transition-transform duration-500"
                  priority
                />
              </div>
            </div>

            {/* Bento Card 3: Buy and sell survey data in the data marketplace */}
            <div className="rounded-3xl bg-[#121215] border border-white/10 p-8 sm:p-12 flex flex-col justify-between overflow-hidden relative group hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/5 transition-all">
              <div className="mb-8">
                <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center text-white shadow-sm mb-6">
                  <FiShoppingCart className="w-6 h-6 text-emerald-400" />
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4 leading-snug">
                  Buy and sell survey data in the data marketplace.
                </h2>
              </div>

              {/* Picture 3: Tablet with analytics chart */}
              <div className="relative w-full h-80 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-white/10 bg-slate-900">
                <Image
                  src="/images/marketplace_charts.jpg"
                  alt="Buy and sell survey data in the data marketplace"
                  fill
                  className="object-cover object-center group-hover:scale-105 transition-transform duration-500"
                  priority
                />
              </div>
            </div>

            {/* Bento Card 4: Sample size needed through power analysis */}
            <div className="rounded-3xl bg-[#121215] border border-white/10 p-8 sm:p-12 flex flex-col justify-between overflow-hidden relative group hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/5 transition-all">
              <div className="mb-8">
                <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center text-white shadow-sm mb-6">
                  <FiActivity className="w-6 h-6 text-emerald-400" />
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4 leading-snug">
                  Know the sample needed for analysis through power analysis.
                </h2>
              </div>

              {/* Picture 4: Math table with magnifying glass */}
              <div className="relative w-full h-80 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-white/10 bg-slate-900">
                <Image
                  src="/images/power_analysis_math.jpg"
                  alt="Statistical power and sample size calculation"
                  fill
                  className="object-cover object-center group-hover:scale-105 transition-transform duration-500"
                  priority
                />
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 3.5. Analysis Pipeline Capability Matrix (Template Layout) ──── */}
      <section id="analysis" className="py-16 md:py-24 bg-[#09090b] border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
            
            {/* Left Card: AI-Powered Box (Matching Template) */}
            <div className="lg:col-span-5 rounded-3xl bg-[#121215] border border-white/10 p-8 sm:p-10 flex flex-col justify-between min-h-[440px] shadow-2xl relative overflow-hidden group hover:border-emerald-500/30 transition-all">
              {/* Subtle background glow */}
              <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-[90px] rounded-full pointer-events-none" />
              
              <div>
                {/* Top Status Pill with Glowing Green Dot */}
                <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-semibold text-slate-200 mb-8 shadow-sm">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#34d399] shadow-sm shadow-emerald-400 animate-pulse" />
                  <span>Analysis Pipeline</span>
                </div>

                {/* Main Headline */}
                <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white leading-tight">
                  AI-powered data analysis workflow for all your project types.
                </h2>
              </div>

              {/* Bottom CTA Button */}
              <div className="pt-8">
                <Link
                  href="/analysis"
                  className="inline-flex items-center gap-3 text-sm sm:text-base font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-6 py-3.5 rounded-full shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/35 transition-all hover:-translate-y-0.5"
                >
                  <span>Start Analysis</span>
                  <div className="w-7 h-7 rounded-full bg-slate-950 text-white flex items-center justify-center">
                    <FiArrowRight className="w-3.5 h-3.5" />
                  </div>
                </Link>
              </div>
            </div>

            {/* Right Rows: Structured Workflow Stages */}
            <div className="lg:col-span-7 flex flex-col divide-y divide-white/10">
              
              {/* Row 1: Ingest */}
              <div className="py-7 first:pt-0 grid grid-cols-1 sm:grid-cols-12 gap-6 items-start">
                <div className="sm:col-span-3">
                  <span className="inline-flex items-center justify-center px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 tracking-wide">
                    Ingest
                  </span>
                </div>
                <div className="sm:col-span-9 grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-6 text-sm text-slate-300">
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">SPSS (.SAV) Dataset Import</p>
                    <p className="font-medium hover:text-white transition-colors">Excel (.XLSX) & CSV Files</p>
                    <p className="font-medium hover:text-white transition-colors">Multi-Source Data Cleaning</p>
                  </div>
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Direct Survey Form Sync</p>
                    <p className="font-medium hover:text-white transition-colors">Automated Column Mapping</p>
                    <p className="font-medium hover:text-white transition-colors">Smart Type Inference</p>
                  </div>
                </div>
              </div>

              {/* Row 2: Decode */}
              <div className="py-7 grid grid-cols-1 sm:grid-cols-12 gap-6 items-start">
                <div className="sm:col-span-3">
                  <span className="inline-flex items-center justify-center px-4 py-1.5 rounded-full bg-teal-500/10 border border-teal-500/20 text-xs font-bold text-teal-300 tracking-wide">
                    Decode
                  </span>
                </div>
                <div className="sm:col-span-9 grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-6 text-sm text-slate-300">
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Variable Scale Type Detection</p>
                    <p className="font-medium hover:text-white transition-colors">Latent Construct Grouping</p>
                    <p className="font-medium hover:text-white transition-colors">Psychometric Scale Screening</p>
                  </div>
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Missing Data (Little&apos;s MCAR)</p>
                    <p className="font-medium hover:text-white transition-colors">Normality (Shapiro-Wilk / KS)</p>
                    <p className="font-medium hover:text-white transition-colors">Multicollinearity & VIF Check</p>
                  </div>
                </div>
              </div>

              {/* Row 3: Analyze */}
              <div className="py-7 grid grid-cols-1 sm:grid-cols-12 gap-6 items-start">
                <div className="sm:col-span-3">
                  <span className="inline-flex items-center justify-center px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 tracking-wide">
                    Analyze
                  </span>
                </div>
                <div className="sm:col-span-9 grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-6 text-sm text-slate-300">
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Parametric & Non-Parametric Tests</p>
                    <p className="font-medium hover:text-white transition-colors">Multiple Regression & Path Models</p>
                    <p className="font-medium hover:text-white transition-colors">ANOVA, MANOVA & GLM</p>
                  </div>
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Mediation & Moderation Models</p>
                    <p className="font-medium hover:text-white transition-colors">Cronbach&apos;s α & McDonald&apos;s ω</p>
                    <p className="font-medium hover:text-white transition-colors">195+ Statistical Techniques</p>
                  </div>
                </div>
              </div>

              {/* Row 4: Report */}
              <div className="py-7 last:pb-0 grid grid-cols-1 sm:grid-cols-12 gap-6 items-start">
                <div className="sm:col-span-3">
                  <span className="inline-flex items-center justify-center px-4 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs font-bold text-cyan-300 tracking-wide">
                    Report
                  </span>
                </div>
                <div className="sm:col-span-9 grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-6 text-sm text-slate-300">
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Complete APA 7th Edition Output</p>
                    <p className="font-medium hover:text-white transition-colors">Themed APA Statistical Tables</p>
                    <p className="font-medium hover:text-white transition-colors">Hypothesis Verification & Decisions</p>
                  </div>
                  <div className="space-y-2.5">
                    <p className="font-medium hover:text-white transition-colors">Publication-Ready Visualizations</p>
                    <p className="font-medium hover:text-white transition-colors">Chapter 4 Findings & Results Draft</p>
                    <p className="font-medium hover:text-white transition-colors">Instant Word & PDF Export</p>
                  </div>
                </div>
              </div>

            </div>

          </div>
        </div>
      </section>

      {/* ── 4. Fast Chapter 4 Delivery Banner (Wide Template Card) ──────── */}
      <section id="report" className="py-16 md:py-24 bg-[#09090b] border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="relative overflow-hidden rounded-3xl md:rounded-[36px] border border-white/15 min-h-[380px] sm:min-h-[440px] flex items-center p-8 sm:p-14 lg:p-16 shadow-2xl group">
            
            {/* Sharp Study Flatlay Background Photograph */}
            <Image
              src="/images/chapter4_bg.jpg"
              alt="Research notebooks, textbook, and study desk"
              fill
              quality={100}
              unoptimized
              className="object-cover object-center group-hover:scale-105 transition-transform duration-700"
              priority
            />

            {/* Dark Cinematic Gradient Overlay for Maximum Sharpness & Text Readability */}
            <div className="absolute inset-0 bg-gradient-to-r from-black/95 via-black/75 to-black/20 pointer-events-none" />

            {/* Left Content */}
            <div className="relative z-10 max-w-xl sm:max-w-2xl space-y-8">
              <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white tracking-tight leading-[1.15]">
                Get your chapter 4 within 10 mins after your analysis. No delay again.
              </h2>

              <div>
                <Link
                  href="/analysis"
                  className="inline-flex items-center gap-3 text-base font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-7 py-3.5 rounded-full shadow-xl shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all hover:-translate-y-0.5"
                >
                  <span>Start Analysis</span>
                  <div className="w-7 h-7 rounded-full bg-slate-950 text-white flex items-center justify-center">
                    <FiArrowRight className="w-3.5 h-3.5" />
                  </div>
                </Link>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 5. Spotlight Card (Dark Notch & Andela Inspired) ──────────────── */}
      <section id="gpu" className="py-16 md:py-24 bg-[#09090b] border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6">
          
          <div className="rounded-3xl bg-[#141418] border border-white/10 p-6 sm:p-10 lg:p-14 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            
            {/* Picture 2: Smiling Student with Books */}
            <div className="lg:col-span-5 relative w-full h-96 sm:h-[450px] rounded-2xl overflow-hidden shadow-md border border-white/10 bg-slate-900">
              <Image
                src="/images/student_pink.jpg"
                alt="Student with research books"
                fill
                className="object-cover object-center"
              />
            </div>

            {/* Right Content */}
            <div className="lg:col-span-7 flex flex-col justify-center">
              <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-white leading-tight mb-8">
                Run your AI and Machine Learning project on a dedicated GPU system
              </h2>

              <div>
                <Link
                  href="/build-model"
                  className="inline-flex items-center gap-3 text-base font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-7 py-3.5 rounded-full shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-all"
                >
                  <span>Let&apos;s help</span>
                  <div className="w-7 h-7 rounded-full bg-slate-950 text-white flex items-center justify-center">
                    <FiArrowRight className="w-3.5 h-3.5" />
                  </div>
                </Link>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 5. Bottom Call to Action ───────────────────────────────────────── */}
      <section className="py-20 md:py-28 bg-[#09090b] border-t border-white/10 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-emerald-500/5 blur-[120px] pointer-events-none" />
        <div className="relative max-w-4xl mx-auto px-6">
          <h2 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-6">
            Run your analysis with ease
          </h2>
          <p className="text-xl sm:text-2xl text-slate-300 mb-10 max-w-2xl mx-auto">
            Easily designed for Bsc, Masters and PhD project or dissertation. Let make your analysis count.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-3 text-base font-semibold text-slate-950 bg-[#34d399] hover:bg-[#10b981] px-8 py-4 rounded-full shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all hover:-translate-y-0.5"
          >
            <span>Get Started</span>
            <div className="w-8 h-8 rounded-full bg-slate-950 text-white flex items-center justify-center">
              <FiArrowRight className="w-4 h-4" />
            </div>
          </Link>
        </div>
      </section>

      {/* ── 6. Comprehensive Dark Footer ───────────────────────────────────── */}
      <footer className="pt-16 pb-12 bg-[#09090b] border-t border-white/10 text-slate-400 text-sm">
        <div className="max-w-7xl mx-auto px-6">
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 pb-12 border-b border-white/10">
            
            {/* Column 1 & 2: Brand Info & Description */}
            <div className="lg:col-span-2 space-y-4">
              <Link href="/" className="flex items-center gap-3 group w-fit">
                <div className="w-9 h-9 rounded-xl bg-white flex items-center justify-center text-slate-950 shadow-md group-hover:scale-105 transition-transform">
                  <span className="font-extrabold text-base tracking-wider">RF</span>
                </div>
                <span className="font-bold text-xl tracking-tight text-white">
                  ResearchForm
                </span>
              </Link>
              <p className="text-slate-400 text-sm leading-relaxed max-w-sm">
                The intelligent research and statistical analysis platform designed for BSc, Masters, PhD dissertations, and advanced AI machine learning workflows.
              </p>
            </div>

            {/* Column 3: Platform & Features */}
            <div className="space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-200">Platform</p>
              <ul className="space-y-2.5 text-sm">
                <li>
                  <Link href="/analysis" className="hover:text-white transition-colors">
                    Analysis Pipeline
                  </Link>
                </li>
                <li>
                  <Link href="/#survey" className="hover:text-white transition-colors">
                    Survey Builder
                  </Link>
                </li>
                <li>
                  <Link href="/#report" className="hover:text-white transition-colors">
                    Chapter 4 Report
                  </Link>
                </li>
                <li>
                  <Link href="/build-model" className="hover:text-white transition-colors">
                    GPU & AI Models
                  </Link>
                </li>
                <li>
                  <Link href="/analysis/power" className="hover:text-white transition-colors">
                    Sample Power Check
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 4: Resources */}
            <div className="space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-200">Resources</p>
              <ul className="space-y-2.5 text-sm">
                <li>
                  <Link href="/marketplace" className="hover:text-white transition-colors">
                    Marketplace
                  </Link>
                </li>
                <li>
                  <Link href="/reports" className="hover:text-white transition-colors">
                    Research Reports
                  </Link>
                </li>
                <li>
                  <Link href="/referral" className="hover:text-white transition-colors">
                    Referral Program
                  </Link>
                </li>
                <li>
                  <Link href="/surveys" className="hover:text-white transition-colors">
                    Survey Templates
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 5: Legal & Support */}
            <div className="space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-200">Legal & Support</p>
              <ul className="space-y-2.5 text-sm">
                <li>
                  <Link href="/terms" className="hover:text-white transition-colors font-medium text-slate-300">
                    Terms of Condition
                  </Link>
                </li>
                <li>
                  <Link href="/privacy" className="hover:text-white transition-colors font-medium text-slate-300">
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link href="/login" className="hover:text-white transition-colors">
                    Log in
                  </Link>
                </li>
                <li>
                  <Link href="/login" className="hover:text-white transition-colors">
                    Get Started
                  </Link>
                </li>
              </ul>
            </div>

          </div>

          {/* Bottom Copyright and Legal Links Bar */}
          <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <p>© {new Date().getFullYear()} ResearchForm. All rights reserved.</p>
            
            <div className="flex items-center gap-6">
              <Link href="/terms" className="hover:text-slate-300 transition-colors">
                Terms of Service
              </Link>
              <Link href="/privacy" className="hover:text-slate-300 transition-colors">
                Privacy Policy
              </Link>
              <Link href="/login" className="hover:text-slate-300 transition-colors">
                Account
              </Link>
            </div>
          </div>

        </div>
      </footer>

    </div>
  );
}
