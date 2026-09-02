import React, { useState, useEffect } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { walletApi, creditsApi, authApi } from '../../lib/api';
import { 
  RiCloseCircleFill, 
  RiUpload2Fill, 
  RiErrorWarningFill, 
  RiArrowLeftRightFill, 
  RiWallet3Fill, 
  RiBankFill, 
  RiShieldCheckFill, 
  RiCheckboxCircleFill, 
  RiLoader4Line, 
  RiTimeFill,
  RiArrowRightFill,
  RiInformationFill,
  RiBuilding4Fill,
  RiCoinsFill
} from 'react-icons/ri';
import toast from 'react-hot-toast';
import Link from 'next/link';
import { useCurrencyStore } from '../../lib/store';

export default function PayoutSettingsPage() {
  const { formatPrice } = useCurrencyStore();
  const [profile, setProfile] = useState<any>(null);
  
  const [wallet, setWallet] = useState<any>(null);
  const [kycStatus, setKycStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'kyc' | 'withdraw' | 'convert'>('kyc');
  
  const [kycForm, setKycForm] = useState({
    id_document_type: 'NIN',
    bank_name: '',
    account_number: '',
    account_name: ''
  });
  const [idFile, setIdFile] = useState<File | null>(null);
  const [submittingKyc, setSubmittingKyc] = useState(false);
  
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [payoutMethod, setPayoutMethod] = useState('bank_transfer');
  const [paypalEmail, setPaypalEmail] = useState('');
  const [swiftCode, setSwiftCode] = useState('');
  const [routingNumber, setRoutingNumber] = useState('');
  const [withdrawing, setWithdrawing] = useState(false);
  
  const [packages, setPackages] = useState<any[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState('');
  const [buyingCredits, setBuyingCredits] = useState(false);

  useEffect(() => {
    const user = localStorage.getItem('rf_user');
    if (user && user !== 'undefined') {
      try { setProfile(JSON.parse(user)); } catch (e) {}
    }
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [wRes, kRes, pRes, authRes] = await Promise.allSettled([
        walletApi.getSellerWallet(),
        walletApi.getKycStatus(),
        creditsApi.packages(),
        authApi.me()
      ]);

      if (wRes.status === 'fulfilled') {
        setWallet(wRes.value.data.wallet || wRes.value.data);
      } else {
        console.error('Wallet load failed:', wRes.reason?.response?.data || wRes.reason);
      }

      if (kRes.status === 'fulfilled') {
        const kData = kRes.value.data;
        setKycStatus(kData);
        if (kData?.status === 'approved') {
          setActiveTab('withdraw');
        }
      } else {
        console.error('KYC status load failed:', kRes.reason?.response?.data || kRes.reason);
        setKycStatus(null);
      }

      if (pRes.status === 'fulfilled') {
        setPackages(pRes.value.data.packages || []);
      } else {
        console.error('Credit packages load failed:', pRes.reason?.response?.data || pRes.reason);
      }

      if (authRes.status === 'fulfilled') {
        setProfile(authRes.value.data);
        localStorage.setItem('rf_user', JSON.stringify(authRes.value.data));
      }
    } finally {
      setLoading(false);
    }
  };

  const isProfileComplete = profile && profile.full_name && profile.institution && profile.photo_url;

  const handleKycSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idFile) return toast.error('Please upload an ID document');
    
    setSubmittingKyc(true);
    try {
      const fd = new FormData();
      fd.append('id_document_type', kycForm.id_document_type);
      fd.append('bank_name', kycForm.bank_name);
      fd.append('account_number', kycForm.account_number);
      fd.append('account_name', kycForm.account_name);
      fd.append('id_document', idFile);
      
      await walletApi.submitKyc(fd);
      toast.success('KYC submitted! You will receive an email shortly.');
      await loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to submit KYC');
    } finally {
      setSubmittingKyc(false);
    }
  };

  const handleWithdraw = async (e: React.FormEvent) => {
    e.preventDefault();
    setWithdrawing(true);
    try {
      const payload = {
        amount_naira: Number(withdrawAmount),
        payout_method: payoutMethod,
        paypal_email: paypalEmail || undefined,
        swift_code: swiftCode || undefined,
        routing_number: routingNumber || undefined
      };
      const res = await walletApi.withdraw(payload);
      toast.success(res.data.message || 'Withdrawal submitted');
      setWithdrawAmount('');
      await loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Withdrawal failed');
    } finally {
      setWithdrawing(false);
    }
  };

  const handleBuyCredits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPackageId) return;
    setBuyingCredits(true);
    try {
      const res = await walletApi.buyCredits(selectedPackageId);
      toast.success(res.data.message || 'Converted to credits');
      setSelectedPackageId('');
      await loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Conversion failed');
    } finally {
      setBuyingCredits(false);
    }
  };

  if (loading) return (
    <AppLayout title="Payouts & Wallet">
      <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin" size={32} style={{ color: 'var(--brand)' }} /></div>
    </AppLayout>
  );

  const status = kycStatus?.status || 'unverified';

  const tabs = [
    {
      id: 'kyc',
      label: 'KYC Verification',
      icon: RiShieldCheckFill,
      badge: status === 'approved' ? 'Verified' : status === 'in_process' ? 'In Review' : status === 'denied' ? 'Denied' : 'Action Required',
      badgeBg: status === 'approved' ? 'rgba(16,185,129,0.15)' : status === 'in_process' ? 'rgba(245,158,11,0.15)' : status === 'denied' ? 'rgba(239,68,68,0.15)' : 'rgba(99,102,241,0.12)',
      badgeColor: status === 'approved' ? '#10b981' : status === 'in_process' ? '#f59e0b' : status === 'denied' ? '#ef4444' : 'var(--brand)',
    },
    {
      id: 'withdraw',
      label: 'Withdrawals',
      icon: RiBankFill,
      badge: null,
      badgeBg: null,
      badgeColor: null,
    },
    {
      id: 'convert',
      label: 'Convert to Credits',
      icon: RiCoinsFill,
      badge: null,
      badgeBg: null,
      badgeColor: null,
    },
  ];

  return (
    <AppLayout title="Payouts & Wallet" breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Settings', href: '/settings' }, { label: 'Payouts & KYC' }]}>
      <div className="page-container-narrow page-stack pb-20">
        
        {/* Header Title */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
            Payouts & KYC Verification
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
            Manage your marketplace earnings, verify your identity, and process payouts.
          </p>
        </div>

        {/* Wallet Balance Hero Card */}
        <div 
          className="card p-6 sm:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden shadow-lg"
          style={{
            background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            color: '#FFFFFF',
          }}
        >
          <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full" style={{ background: 'radial-gradient(circle, rgba(129, 140, 248, 0.25) 0%, transparent 70%)', filter: 'blur(30px)', pointerEvents: 'none' }} />
          <div className="relative z-10">
            <p className="text-xs uppercase tracking-wider font-bold mb-1 flex items-center gap-2 text-indigo-200">
              <RiWallet3Fill size={15} /> Available Seller Balance
            </p>
            <h2 className="text-4xl sm:text-5xl font-black font-display tracking-tight text-white my-1">
              {formatPrice(wallet?.balance_naira || 0)}
            </h2>
            <p className="text-xs sm:text-sm mt-2 text-indigo-200/80">
              Total Lifetime Earned: <span className="font-semibold text-white">{formatPrice(wallet?.total_earned_naira || 0)}</span>
            </p>
          </div>

          <div className="relative z-10 flex flex-wrap gap-2.5">
            <button
              onClick={() => setActiveTab('withdraw')}
              className="btn flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm shadow-md"
              style={{ background: '#FFFFFF', color: '#312e81', border: 'none' }}
            >
              <RiBankFill size={16} /> Request Withdrawal
            </button>
            <button
              onClick={() => setActiveTab('convert')}
              className="btn flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm"
              style={{ background: 'rgba(255, 255, 255, 0.15)', color: '#FFFFFF', border: '1px solid rgba(255, 255, 255, 0.2)' }}
            >
              <RiArrowLeftRightFill size={16} /> Convert to Credits
            </button>
          </div>
        </div>

        {/* Theme-Adaptive Tabs */}
        <div 
          className="flex flex-wrap gap-1.5 p-1.5 rounded-2xl w-full sm:w-fit shadow-sm"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
        >
          {tabs.map(tab => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className="flex items-center gap-2.5 px-4 sm:px-5 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer"
                style={{
                  background: isActive ? 'var(--brand)' : 'transparent',
                  color: isActive ? 'var(--brand-text)' : 'var(--text-2)',
                  border: 'none',
                  boxShadow: isActive ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
                }}
              >
                <tab.icon size={16} style={{ color: isActive ? 'var(--brand-text)' : 'var(--text-3)' }} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-bold transition-all"
                    style={{
                      background: isActive ? 'rgba(128, 128, 128, 0.25)' : tab.badgeBg || 'var(--surface-3)',
                      color: isActive ? 'var(--brand-text)' : tab.badgeColor || 'var(--text)',
                      border: isActive ? 'none' : `1px solid ${tab.badgeColor || 'var(--border)'}40`,
                    }}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* TAB 1: KYC Verification */}
        {activeTab === 'kyc' && (
          <div className="card p-6 sm:p-8 animate-slide-up shadow-sm">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: status === 'approved' ? 'rgba(16,185,129,0.12)' : 'rgba(99,102,241,0.12)', color: status === 'approved' ? '#10b981' : 'var(--brand)' }}>
                  <RiShieldCheckFill size={22} />
                </div>
                <div>
                  <h2 className="text-lg font-bold font-display m-0" style={{ color: 'var(--text)' }}>Payout Verification (KYC)</h2>
                  <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>Required by regulatory standards to authorize bank payouts</p>
                </div>
              </div>

              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold"
                style={{
                  background: status === 'approved' ? 'rgba(16,185,129,0.15)' : status === 'in_process' ? 'rgba(245,158,11,0.15)' : status === 'denied' ? 'rgba(239,68,68,0.15)' : 'var(--surface-2)',
                  color: status === 'approved' ? '#10b981' : status === 'in_process' ? '#f59e0b' : status === 'denied' ? '#ef4444' : 'var(--text-2)',
                  border: '1px solid var(--border)'
                }}>
                {status === 'approved' ? '✓ Verified' : status === 'in_process' ? '⟳ In Review' : status === 'denied' ? '✕ Denied' : 'Action Needed'}
              </span>
            </div>
            
            {/* Status alerts */}
            {status === 'approved' && (
              <div className="p-4 rounded-xl flex items-start gap-3.5 mb-6"
                style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)' }}>
                <RiCheckboxCircleFill size={22} style={{ color: '#10b981', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <p className="font-bold text-sm" style={{ color: '#10b981', margin: 0 }}>Identity & Bank Details Verified</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-2)', margin: 0 }}>
                    Your account is fully approved for payouts. You can request withdrawals directly from your wallet balance.
                  </p>
                </div>
              </div>
            )}

            {status === 'in_process' && (
              <div className="p-4 rounded-xl flex items-start gap-3.5 mb-6"
                style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
                <RiLoader4Line size={22} className="animate-spin" style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <p className="font-bold text-sm" style={{ color: '#f59e0b', margin: 0 }}>Verification in Review</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-2)', margin: 0 }}>
                    Our compliance team is currently reviewing your submitted ID document and bank details. Verification usually completes within 1–2 business days.
                  </p>
                </div>
              </div>
            )}

            {status === 'denied' && (
              <div className="p-4 rounded-xl flex items-start gap-3.5 mb-6"
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
                <RiCloseCircleFill size={22} style={{ color: '#ef4444', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <p className="font-bold text-sm" style={{ color: '#ef4444', margin: 0 }}>Verification Denied</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-2)', margin: 0 }}>
                    {kycStatus?.rejection_reason || 'Your document or account details could not be verified. Please review the details and submit again below.'}
                  </p>
                </div>
              </div>
            )}

            {/* KYC Submission Form */}
            {(!status || status === 'unverified' || status === 'denied') && (
              <div>
                {!isProfileComplete ? (
                  <div className="p-6 rounded-2xl text-center" style={{ background: 'rgba(239,68,68,0.05)', border: '2px dashed rgba(239,68,68,0.25)' }}>
                    <RiErrorWarningFill className="mx-auto mb-2" size={36} style={{ color: '#ef4444' }} />
                    <h3 className="font-bold text-base" style={{ color: 'var(--text)', margin: '0 0 4px' }}>Profile Information Required</h3>
                    <p className="text-xs max-w-md mx-auto mb-4" style={{ color: 'var(--text-2)' }}>
                      Before submitting KYC verification, please ensure your profile has your Full Legal Name, Institution, and Profile Picture.
                    </p>
                    <Link href="/settings" className="btn btn-primary inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl">
                      Complete Profile <RiArrowRightFill size={14} />
                    </Link>
                  </div>
                ) : (
                  <form onSubmit={handleKycSubmit} className="space-y-5">
                    <p className="text-xs" style={{ color: 'var(--text-3)' }}>
                      Please provide valid government-issued identification and bank account details for transfers.
                    </p>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="label">ID Document Type</label>
                        <select className="input w-full" value={kycForm.id_document_type} onChange={e => setKycForm({...kycForm, id_document_type: e.target.value})}>
                          <option value="NIN">National Identification Number (NIN)</option>
                          <option value="Driver License">Driver's License</option>
                          <option value="Voters Card">Voter's Card</option>
                          <option value="School ID">School / Faculty ID</option>
                          <option value="Workplace ID">Workplace ID</option>
                          <option value="International Passport">International Passport</option>
                        </select>
                      </div>
                      <div>
                        <label className="label">Upload ID Document (Image or PDF)</label>
                        <input type="file" className="input py-2 w-full" accept="image/*,.pdf" onChange={e => setIdFile(e.target.files?.[0] || null)} required />
                      </div>
                    </div>

                    <div className="p-4 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                      <p className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--text-2)' }}>Bank Transfer Details</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="label">Bank Name</label>
                          <input className="input w-full" required placeholder="e.g. GTBank, Access Bank, Zenith" value={kycForm.bank_name} onChange={e => setKycForm({...kycForm, bank_name: e.target.value})} />
                        </div>
                        <div>
                          <label className="label">Account Number</label>
                          <input className="input w-full font-mono" required placeholder="10-digit NUBAN" value={kycForm.account_number} onChange={e => setKycForm({...kycForm, account_number: e.target.value})} />
                        </div>
                        <div className="md:col-span-2">
                          <label className="label">Account Name (Must match ID exactly)</label>
                          <input className="input w-full" required placeholder="Full Name as registered with Bank" value={kycForm.account_name} onChange={e => setKycForm({...kycForm, account_name: e.target.value})} />
                        </div>
                      </div>
                    </div>

                    <button type="submit" disabled={submittingKyc} className="btn btn-primary w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold shadow-md">
                      {submittingKyc ? <RiLoader4Line className="animate-spin" size={18} /> : <RiUpload2Fill size={18} />} 
                      {submittingKyc ? 'Submitting Verification…' : 'Submit for Verification'}
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Withdrawals */}
        {activeTab === 'withdraw' && (
          <div className="card p-6 sm:p-8 animate-slide-up shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--brand)' }}>
                <RiBankFill size={22} />
              </div>
              <div>
                <h2 className="text-lg font-bold font-display m-0" style={{ color: 'var(--text)' }}>Request Withdrawal</h2>
                <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>Transfer funds from your available balance to your bank</p>
              </div>
            </div>

            {status !== 'approved' ? (
              <div className="p-6 rounded-2xl text-center my-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <RiShieldCheckFill className="mx-auto mb-2" size={36} style={{ color: 'var(--brand)' }} />
                <h3 className="font-bold text-base" style={{ color: 'var(--text)', margin: '0 0 4px' }}>KYC Verification Required</h3>
                <p className="text-xs max-w-md mx-auto mb-4" style={{ color: 'var(--text-2)' }}>
                  You must complete and get approved for KYC verification before you can withdraw earnings.
                </p>
                <button
                  type="button"
                  onClick={() => setActiveTab('kyc')}
                  className="btn btn-primary inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl"
                >
                  Go to KYC Verification <RiArrowRightFill size={14} />
                </button>
              </div>
            ) : (
              <form onSubmit={handleWithdraw} className="space-y-4 max-w-xl">
                <div>
                  <label className="label">Amount (NGN)</label>
                  <input
                    type="number"
                    min="5000"
                    step="100"
                    required
                    className="input w-full text-lg font-bold"
                    placeholder="Min ₦5,000"
                    value={withdrawAmount}
                    onChange={e => setWithdrawAmount(e.target.value)}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>
                    Available: <span className="font-semibold" style={{ color: 'var(--text)' }}>{formatPrice(wallet?.balance_naira || 0)}</span> (Minimum withdrawal: ₦5,000)
                  </p>
                </div>

                <div>
                  <label className="label">Payout Method</label>
                  <select className="input w-full" value={payoutMethod} onChange={e => setPayoutMethod(e.target.value)}>
                    <option value="bank_transfer">Local Bank Transfer (Direct Deposit)</option>
                    <option value="paypal">PayPal</option>
                    <option value="wise">Wise (TransferWise)</option>
                    <option value="swift">International Wire (SWIFT)</option>
                  </select>
                </div>

                {payoutMethod === 'paypal' && (
                  <div>
                    <label className="label">PayPal Email</label>
                    <input type="email" required className="input w-full" placeholder="you@example.com" value={paypalEmail} onChange={e => setPaypalEmail(e.target.value)} />
                  </div>
                )}

                {(payoutMethod === 'wise' || payoutMethod === 'swift') && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="label">SWIFT / BIC Code</label>
                      <input type="text" required className="input w-full" placeholder="8 or 11 characters" value={swiftCode} onChange={e => setSwiftCode(e.target.value)} />
                    </div>
                    <div>
                      <label className="label">Routing / Sort Number</label>
                      <input type="text" className="input w-full" placeholder="Optional" value={routingNumber} onChange={e => setRoutingNumber(e.target.value)} />
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={withdrawing || !withdrawAmount || Number(withdrawAmount) > Number(wallet?.balance_naira || 0) || Number(withdrawAmount) < 5000}
                  className="btn btn-primary w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold shadow-md"
                >
                  {withdrawing ? <RiLoader4Line className="animate-spin" size={18} /> : <RiBankFill size={18} />}
                  {withdrawing ? 'Processing Request…' : 'Submit Withdrawal Request'}
                </button>

                <p className="text-xs text-center flex items-center justify-center gap-1.5" style={{ color: 'var(--text-3)' }}>
                  <RiInformationFill size={14} /> Payouts are reviewed and settled within 1–2 business days.
                </p>
              </form>
            )}
          </div>
        )}

        {/* TAB 3: Convert to Credits */}
        {activeTab === 'convert' && (
          <div className="card p-6 sm:p-8 animate-slide-up shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--brand)' }}>
                <RiCoinsFill size={22} />
              </div>
              <div>
                <h2 className="text-lg font-bold font-display m-0" style={{ color: 'var(--text)' }}>Convert Balance to Credits</h2>
                <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>Instantly exchange your earnings for AI analysis credits without processing fees</p>
              </div>
            </div>

            <form onSubmit={handleBuyCredits} className="space-y-6">
              <div>
                <label className="label">Select Credit Package</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {packages.map(pkg => {
                    const isSelected = selectedPackageId === pkg.id;
                    return (
                      <button 
                        key={pkg.id}
                        type="button" 
                        onClick={() => setSelectedPackageId(pkg.id)}
                        className="p-4 rounded-xl cursor-pointer transition-all text-left w-full relative"
                        style={{
                          background: isSelected ? 'rgba(99,102,241,0.08)' : 'var(--surface-2)',
                          border: `2px solid ${isSelected ? 'var(--brand)' : 'var(--border)'}`,
                          boxShadow: isSelected ? '0 4px 14px rgba(99,102,241,0.15)' : 'none',
                        }}
                      >
                        {isSelected && (
                          <div className="absolute top-3.5 right-3.5" style={{ color: 'var(--brand)' }}>
                            <RiCheckboxCircleFill size={20} />
                          </div>
                        )}
                        <div className="font-bold text-base" style={{ color: isSelected ? 'var(--brand)' : 'var(--text)' }}>
                          {pkg.label}
                        </div>
                        <div className="text-xs mt-1" style={{ color: 'var(--text-2)' }}>
                          <span className="font-bold" style={{ color: 'var(--text)' }}>{pkg.credits} Credits</span> for {formatPrice(pkg.price_naira)}
                        </div>
                        {pkg.description && (
                          <p className="text-xs mt-2" style={{ color: 'var(--text-3)', margin: 0 }}>
                            {pkg.description}
                          </p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              <button
                type="submit"
                disabled={buyingCredits || !selectedPackageId}
                className="btn btn-primary w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold shadow-md"
              >
                {buyingCredits ? <RiLoader4Line className="animate-spin" size={18} /> : <RiArrowLeftRightFill size={18} />}
                {buyingCredits ? 'Converting Balance…' : 'Convert Selected Package Now'}
              </button>
            </form>
          </div>
        )}

      </div>
    </AppLayout>
  );
}
