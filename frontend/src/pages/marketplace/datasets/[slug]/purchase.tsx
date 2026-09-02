import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../../../components/layout/AppLayout';
import PageContent from '../../../../components/ui/PageContent';
import LoadingBlock from '../../../../components/ui/LoadingBlock';
import { datanestApi } from '../../../../lib/api';
import MarketplaceNav from '../../../../components/marketplace/MarketplaceNav';
import { RiLoader4Line, RiLockFill, RiShieldCheckFill, RiBankCardFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

export default function PurchasePage() {
  const router = useRouter();
  const { slug } = router.query;

  const [dataset, setDataset] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    if (!slug) return;

    const token = typeof window !== 'undefined' && document.cookie.includes('rf_token');
    if (!token) {
      toast.error('Please log in to purchase datasets.');
      router.replace('/login');
      return;
    }

    datanestApi.getDataset(slug as string)
      .then((res) => {
        setDataset(res.data);
        if (res.data.price_naira <= 0) {
          toast('Dataset is free. Redirecting to details…');
          router.replace(`/marketplace/datasets/${slug}`);
        }
      })
      .catch(() => {
        toast.error('Dataset not found.');
        router.push('/marketplace');
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const handleCheckout = async () => {
    setProcessing(true);
    try {
      const res = await datanestApi.purchase(slug as string);
      if (res.data.authorization_url) {
        window.location.href = res.data.authorization_url;
      } else {
        toast.error('Failed to initiate payment');
        setProcessing(false);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to initiate checkout');
      setProcessing(false);
    }
  };

  if (loading || !dataset) {
    return (
      <AppLayout title="Checkout">
        <PageContent width="narrow">
          <LoadingBlock label="Preparing checkout…" />
        </PageContent>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title="Checkout"
      breadcrumbs={[
        { label: 'Marketplace', href: '/marketplace' },
        { label: dataset.title, href: `/marketplace/datasets/${dataset.slug}` },
        { label: 'Checkout' },
      ]}
    >
      <PageContent width="narrow">
        <MarketplaceNav />

        <div className="text-center">
          <div className="inline-flex items-center justify-center p-4 rounded-full mb-4" style={{ background: 'rgba(99, 102, 241, 0.12)' }}>
            <RiLockFill size={32} className="text-brand" />
          </div>
          <h1 className="page-title mb-2">Secure checkout</h1>
          <p className="page-description mx-auto">One-time purchase — perpetual access to this dataset.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card p-6 order-2 md:order-1">
            <h3 className="section-title mb-4 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
              Order summary
            </h3>
            <p className="font-medium text-primary line-clamp-2 mb-1">{dataset.title}</p>
            <p className="text-sm text-muted mb-6">{dataset.domain}</p>

            <div className="space-y-3 text-sm mb-4 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="flex justify-between text-secondary">
                <span>Subtotal</span>
                <span>₦{dataset.price_naira.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-secondary">
                <span>Platform fee</span>
                <span>Included</span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="font-bold text-primary">Total</span>
              <span className="page-title" style={{ fontSize: '1.5rem', color: 'var(--brand)' }}>
                ₦{dataset.price_naira.toLocaleString()}
              </span>
            </div>
          </div>

          <div className="card p-6 order-1 md:order-2 flex flex-col justify-center">
            <div className="info-banner mb-6 flex items-start gap-3">
              <RiShieldCheckFill className="text-success shrink-0" size={20} />
              <p className="info-banner-desc m-0">
                Payments are processed securely via Paystack. We do not store card details.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-primary w-full py-3"
              onClick={handleCheckout}
              disabled={processing}
            >
              {processing ? <RiLoader4Line className="animate-spin" /> : <><RiBankCardFill size={18} /> Pay with Paystack</>}
            </button>

            <p className="text-xs text-center text-muted mt-4 m-0">
              By paying, you agree to the Data Use Agreement and marketplace terms.
            </p>
          </div>
        </div>
      </PageContent>
    </AppLayout>
  );
}
