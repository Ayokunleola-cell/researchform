import React, { useState, useEffect } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import PageContent from '../../components/ui/PageContent';
import PageHeader from '../../components/ui/PageHeader';
import LoadingBlock from '../../components/ui/LoadingBlock';
import { datanestApi } from '../../lib/api';
import { useCurrencyStore } from '../../lib/store';
import MarketplaceNav from '../../components/marketplace/MarketplaceNav';
import EmptyState from '../../components/ui/EmptyState';
import { MARKETPLACE_DOMAINS } from '../../components/marketplace/constants';
import { RiPriceTag3Fill, RiAddFill, RiMoneyDollarCircleFill, RiDownload2Fill, RiUploadCloud2Fill, RiBarChartFill, RiCheckboxCircleFill, RiBox3Fill, RiLoader4Line } from 'react-icons/ri';
import toast from 'react-hot-toast';

const DEFAULT_FORM = {
  title: '',
  description: '',
  domain: 'Education',
  country: '',
  collection_method: 'survey',
  year_collected: new Date().getFullYear(),
  price_naira: 0,
  license: 'CC-BY',
  visibility: 'public',
  tags: '',
};

export default function SellDataPage() {
  const { formatPrice } = useCurrencyStore();
  const [stats, setStats] = useState<any>(null);
  const [listings, setListings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [formData, setFormData] = useState(DEFAULT_FORM);
  const [file, setFile] = useState<File | null>(null);
  
  // Validation Checklist States
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [chkHuman, setChkHuman] = useState(false);
  const [chkHonest, setChkHonest] = useState(false);
  const [chkOwn, setChkOwn] = useState(false);
  const [chkConsent, setChkConsent] = useState(false);
  const [chkProof, setChkProof] = useState(false);

  const allChecked = chkHuman && chkHonest && chkOwn && chkConsent && chkProof;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, listRes] = await Promise.all([
        datanestApi.analytics(),
        datanestApi.myListings(),
      ]);
      setStats(statsRes.data);
      setListings(listRes.data);
    } catch {
      toast.error('Failed to load seller dashboard. Sign in to list datasets.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);

    try {
      let finalFile = file;

      if (!finalFile) {
        setUploading(false);
        return toast.error('Please upload a dataset file.');
      }

      const fd = new FormData();
      Object.entries(formData).forEach(([k, v]) => fd.append(k, String(v)));
      fd.append('file', finalFile);
      if (proofFile) {
        fd.append('proof_file', proofFile);
      }

      await datanestApi.uploadDataset(fd);
      toast.success('Dataset submitted for listing');
      setShowUpload(false);
      setFormData(DEFAULT_FORM);
      setFile(null);
      setProofFile(null);
      setChkHuman(false);
      setChkHonest(false);
      setChkOwn(false);
      setChkConsent(false);
      setChkProof(false);
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to upload dataset');
    } finally {
      setUploading(false);
    }
  };

  return (
    <AppLayout
      title="Sell Data"
      description="List datasets and track sales"
      breadcrumbs={[{ label: 'Marketplace', href: '/marketplace' }, { label: 'Sell Data' }]}
    >
      <PageContent width="wide">
        <MarketplaceNav />

        <PageHeader
          title="Sell data"
          description="List datasets, set pricing, and track downloads and sales from your seller dashboard."
          actions={
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowUpload((s) => !s)}>
              {showUpload ? 'Cancel' : <><RiAddFill size={16} /> New listing</>}
            </button>
          }
        />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 flex items-center gap-4">
          <div className="p-3 bg-brand/10 text-brand rounded-lg"><RiBox3Fill size={22} /></div>
          <div>
            <p className="text-sm text-muted m-0">Listings</p>
            <p className="text-2xl font-bold m-0">{loading ? '—' : stats?.total_listings || 0}</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="p-3 bg-success/10 text-success rounded-lg"><RiMoneyDollarCircleFill size={22} /></div>
          <div>
            <p className="text-sm text-muted m-0">Total sales</p>
            <p className="text-2xl font-bold m-0">{loading ? '—' : formatPrice(stats?.total_earned || 0)}</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}><RiBarChartFill size={22} /></div>
          <div>
            <p className="text-sm text-muted m-0">Wallet</p>
            <p className="text-2xl font-bold m-0">{loading ? '—' : formatPrice(stats?.wallet_balance || 0)}</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="p-3 bg-warning/10 text-warning rounded-lg"><RiDownload2Fill size={22} /></div>
          <div>
            <p className="text-sm text-muted m-0">Downloads</p>
            <p className="text-2xl font-bold m-0">{loading ? '—' : stats?.total_downloads || 0}</p>
          </div>
        </div>
      </div>

      {showUpload && (
        <div className="card p-6 mb-8 animate-fade-in" style={{ borderColor: 'var(--brand)' }}>
          <h3 className="section-title mb-1">Upload new dataset</h3>
          <p className="text-sm text-secondary mb-5">
            Provide metadata and your data file (.csv, .xlsx, or .zip). Set price to 0 for free listings.
          </p>
          <form onSubmit={handleUpload} className="space-y-5">
            <div>
              <p className="label mb-3">Basic information</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label" htmlFor="sell-title">Title</label>
                  <input
                    id="sell-title"
                    required
                    className="input"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="e.g. Nigerian Student Health Survey 2024"
                  />
                </div>
                <div>
                  <label className="label" htmlFor="sell-domain">Domain</label>
                  <select
                    id="sell-domain"
                    className="input"
                    value={formData.domain}
                    onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                  >
                    {MARKETPLACE_DOMAINS.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="label" htmlFor="sell-desc">Description</label>
                  <textarea
                    id="sell-desc"
                    required
                    className="input"
                    rows={3}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What does this dataset contain? How was it collected?"
                  />
                </div>
              </div>
            </div>
            <div>
              <p className="label mb-3">Pricing & file</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="label" htmlFor="sell-price">Price (₦) — 0 for free</label>
                    <input
                      id="sell-price"
                      type="number"
                      required
                      min={0}
                      className="input w-full"
                      value={formData.price_naira}
                      onChange={(e) => setFormData({ ...formData, price_naira: Number(e.target.value) })}
                    />
                    {formData.price_naira > 0 && stats?.platform_fee_percent !== undefined && (
                      <div className="text-xs mt-2 text-muted bg-[var(--surface-2)] p-2 rounded border border-[var(--border)]">
                        <div className="flex justify-between mb-1">
                          <span>Platform Fee ({stats.platform_fee_percent}%):</span>
                          <span className="font-medium text-[var(--text)]">{formatPrice(formData.price_naira * (stats.platform_fee_percent / 100))}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Your Earnings:</span>
                          <span className="font-semibold text-[#22c55e]">{formatPrice(formData.price_naira - (formData.price_naira * (stats.platform_fee_percent / 100)))}</span>
                        </div>
                      </div>
                    )}
                  </div>
                <div>
                  <div className="mb-2">
                    <label className="label m-0">Dataset File</label>
                  </div>
                  <input
                    id="sell-file"
                    type="file"
                    required
                    accept=".csv,.xlsx,.xls,.zip"
                    className="input w-full"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  <p className="text-[11px] text-muted mt-1.5">Accepted formats: .csv, .xlsx, .xls, .zip</p>
                </div>
              </div>
            </div>
            
            <hr className="my-6 border-[var(--border)]" />
            
            <div>
              <p className="label mb-3 text-lg">Data Validation & Ethics</p>
              <p className="text-xs text-secondary mb-4">
                To ensure high quality, every dataset goes through our automated and manual verification queue. 
                Please provide proof of ownership/authorization and agree to the declarations below.
              </p>
              
              <div className="mb-5">
                <label className="label" htmlFor="proof-file">
                  Proof of Authorization <span className="text-muted font-normal">(Optional but recommended)</span>
                </label>
                <p className="text-xs text-muted mb-2">
                  Upload Ethical Clearance, Institutional Letter, IRB Approval, or equivalent authorization document (PDF/Image).
                </p>
                <input
                  id="proof-file"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="input max-w-md"
                  onChange={(e) => setProofFile(e.target.files?.[0] || null)}
                />
              </div>

              <div className="space-y-3 p-4 bg-surface-2 rounded-lg border border-[var(--border)]">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={chkHuman} onChange={e => setChkHuman(e.target.checked)} className="mt-1" />
                  <span className="text-sm text-primary"><b>Authentic Human Collection:</b> I confirm this dataset was collected from real human participants or field observations, not generated by AI or bots.</span>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={chkHonest} onChange={e => setChkHonest(e.target.checked)} className="mt-1" />
                  <span className="text-sm text-primary"><b>No Falsification:</b> I guarantee I have not fabricated, duplicated, or dishonestly filled rows to artificially increase size.</span>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={chkOwn} onChange={e => setChkOwn(e.target.checked)} className="mt-1" />
                  <span className="text-sm text-primary"><b>Clear Ownership:</b> I am the original owner or have explicit authorization to sell/share this data. I did not copy this from a public source.</span>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={chkConsent} onChange={e => setChkConsent(e.target.checked)} className="mt-1" />
                  <span className="text-sm text-primary"><b>Participant Consent & Privacy Compliance:</b> Participants gave informed consent. All Personally Identifiable Information (PII) such as names, phone numbers, and addresses has been removed or anonymized in compliance with applicable privacy laws.</span>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={chkProof} onChange={e => setChkProof(e.target.checked)} className="mt-1" />
                  <span className="text-sm text-primary"><b>Documentary Proof:</b> I can provide my Institutional Approval Letter, Ethical Clearance, or equivalent authorization document if this dataset is flagged for review.</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button 
                type="submit" 
                disabled={uploading || !allChecked} 
                className="btn btn-primary min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed"
                title={!allChecked ? "Please agree to all declarations to upload" : ""}
              >
                {uploading ? <RiLoader4Line className="animate-spin" size={18} /> : <><RiUploadCloud2Fill size={18} /> Upload Dataset</>}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="section-card-header">
        <h2 className="section-title">Your listings</h2>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <LoadingBlock label="Loading listings…" />
        ) : listings.length === 0 ? (
          <EmptyState
            icon={RiPriceTag3Fill}
            title="No listings yet"
            description="Upload your first dataset to start selling or sharing research data for free."
            action={
              <button type="button" className="btn btn-primary" onClick={() => setShowUpload(true)}>
                <RiAddFill size={16} /> Create listing
              </button>
            }
          />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Status</th>
                  <th>Price</th>
                  <th>Sales</th>
                  <th>Listed</th>
                </tr>
              </thead>
              <tbody>
                {listings.map((item) => (
                  <tr key={item.id}>
                    <td className="font-medium text-primary">{item.title}</td>
                    <td>
                      {item.status === 'verified' ? (
                        <span className="badge badge-success flex w-fit items-center gap-1">
                          <RiCheckboxCircleFill size={12} /> Active
                        </span>
                      ) : item.status === 'pending_verification' ? (
                        <span className="badge badge-brand flex w-fit items-center gap-1 opacity-90">
                          In Review
                        </span>
                      ) : item.status === 'rejected' ? (
                        <div className="flex flex-col gap-1">
                          <span className="badge badge-error flex w-fit items-center gap-1 text-error">
                            Rejected
                          </span>
                          {item.rejection_reason && (
                            <span className="text-[10px] text-error max-w-[150px] leading-tight">
                              {item.rejection_reason}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="badge badge-secondary flex w-fit items-center gap-1">
                          {String(item.status).replace('_', ' ')}
                        </span>
                      )}
                    </td>
                    <td>{item.price_naira > 0 ? formatPrice(item.price_naira) : 'Free'}</td>
                    <td>{item.purchase_count || 0}</td>
                    <td className="text-muted">{new Date(item.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </PageContent>
    </AppLayout>
  );
}
