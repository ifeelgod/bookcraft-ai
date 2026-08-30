'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import {
  ArrowLeft,
  Check,
  CreditCard,
  Crown,
  FileCheck,
  FileDown,
  HelpCircle,
  ShieldCheck,
  Sparkles,
  Zap,
  Loader2,
  X,
} from 'lucide-react';
import { CheckoutModal } from '@/components/CheckoutModal';
import { useAuth } from '@/lib/authStore';
import { verifyPaymentSession } from '@/lib/api';

function CheckoutContent() {
  const { isPro, tier, email, logout } = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [targetTier, setTargetTier] = useState<'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual'>('tier_1_pass');

  const searchParams = useSearchParams();
  const success = searchParams.get('success');
  const provider = searchParams.get('provider');
  const token = searchParams.get('token');
  const sessionId = searchParams.get('session_id');
  const queryTier = searchParams.get('tier');
  const queryEmail = searchParams.get('email');
  const queryName = searchParams.get('name');

  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const { login } = useAuth();

  useEffect(() => {
    if (success === 'true' && provider) {
      const orderId = token || sessionId;
      if (!orderId) return;

      const runVerification = async () => {
        setVerifying(true);
        setVerifyStatus('loading');
        try {
          const res = await verifyPaymentSession({
            provider: provider as 'stripe' | 'paypal',
            order_id: provider === 'paypal' ? orderId : undefined,
            session_id: provider === 'stripe' ? orderId : undefined,
            lead_email: queryEmail || undefined,
            lead_name: queryName || undefined,
            tier: queryTier || 'tier_1_pass',
          });

          if (res.success && res.access_token) {
            login(res.access_token, res.tier, res.email || queryEmail || '', queryName || '', res.expires_at || undefined);
            setVerifyStatus('success');
            toast.success('Payment verified! Your Pro access is now active.');
          } else {
            setVerifyStatus('error');
            setVerifyError('Verification response was unsuccessful.');
          }
        } catch (err: any) {
          console.error(err);
          setVerifyStatus('error');
          setVerifyError(err.message || 'Failed to verify transaction.');
        } finally {
          setVerifying(false);
        }
      };

      runVerification();
    }
  }, [success, provider, token, sessionId, queryTier, queryEmail, queryName]);

  const openCheckout = (tierName: 'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual') => {
    setTargetTier(tierName);
    setModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-amber-500/30">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            href="/editor"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Editor</span>
          </Link>

          <div className="flex items-center gap-3">
            {isPro ? (
              <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-full text-emerald-400 text-xs font-semibold">
                <Crown className="w-3.5 h-3.5" />
                <span>Active Tier: {tier?.toUpperCase()}</span>
                <button
                  onClick={logout}
                  className="ml-2 text-slate-400 hover:text-red-400 underline text-[11px]"
                >
                  Reset
                </button>
              </div>
            ) : (
              <div className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-full text-slate-400 text-xs">
                Free Demo (15-Page Cap)
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Transparent, Author-First Pricing</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
          Typeset and Export Your Book with Zero Limits
        </h1>
        <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto">
          Choose between our high-value single manuscript pass or recurring author unlimited plan. Full PDF, DOCX, Markdown, and EPUB3 outputs.
        </p>
      </section>

      {/* Pricing Cards Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 items-stretch justify-center">
          {/* Card 1: Free Demo */}
          <div className="flex flex-col justify-between p-8 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all">
            <div className="space-y-6">
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white">Free Demo</h3>
                <p className="text-xs text-slate-400">Test the AI formatting engine on your manuscript.</p>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">$0</span>
                <span className="text-xs text-slate-400">/ forever</span>
              </div>
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Up to 15 pages preview output</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Standard Typst PDF Preview</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Interactive Chapter Editor</span>
                </li>
                <li className="flex items-center gap-2.5 text-slate-500">
                  <span className="line-through">Editable DOCX & Markdown</span>
                </li>
              </ul>
            </div>
            <div className="pt-8">
              <Link
                href="/upload"
                className="w-full block text-center py-3 px-4 rounded-xl font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                Try Free Demo
              </Link>
            </div>
          </div>

          {/* Card 2: Single Book Pass (Tier 1) */}
          <div className="flex flex-col justify-between p-8 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all">
            <div className="space-y-6">
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white">Single Book Pass</h3>
                <p className="text-xs text-slate-400">Everything needed to publish a single complete book.</p>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">$9</span>
                <span className="text-xs text-slate-400">/ one-time</span>
              </div>
              <ul className="space-y-3 text-sm text-slate-200">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span className="font-semibold text-white">Single Book (No page limit)</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Print-Ready High-Res PDF</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Word (.docx) & Markdown Export</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>EPUB3 Ebook Export</span>
                </li>
              </ul>
            </div>
            <div className="pt-8">
              <button
                onClick={() => openCheckout('tier_1_pass')}
                className="w-full py-3 px-4 rounded-xl font-semibold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700/80 transition-colors flex items-center justify-center gap-2"
              >
                <span>Get Book Pass ($9)</span>
              </button>
            </div>
          </div>

          {/* Card 3: Monthly Pro (Tier 2) */}
          <div className="relative flex flex-col justify-between p-8 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border-2 border-amber-500/80 shadow-2xl shadow-amber-500/10">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-amber-500 text-slate-950 text-xs font-extrabold uppercase tracking-wide">
              Most Popular
            </div>
            <div className="space-y-6">
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white">Monthly Pro</h3>
                <p className="text-xs text-slate-400">Perfect for authors formatting up to 9 books / month.</p>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-5xl font-black text-white">$19</span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <ul className="space-y-3 text-sm text-slate-200">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span className="font-semibold text-white">Up to 9 Books / Month</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Unlimited Pages for All Books</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>PDF, DOCX, MD, EPUB exports</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Priority Queue Support</span>
                </li>
              </ul>
            </div>
            <div className="pt-8">
              <button
                onClick={() => openCheckout('tier_2_monthly')}
                className="w-full py-3.5 px-4 rounded-xl font-bold text-white bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 shadow-lg shadow-amber-500/25 transition-all flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Get Monthly Pro ($19)</span>
              </button>
            </div>
          </div>

          {/* Card 4: Unlimited Monthly (Tier 3) */}
          <div className="flex flex-col justify-between p-8 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all">
            <div className="space-y-6">
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white">Unlimited Monthly</h3>
                <p className="text-xs text-slate-400">Unlimited books and pages for professional publishers.</p>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">$29</span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span className="font-semibold text-white">UNLIMITED Books & Titles</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>All Formats (PDF/DOCX/MD/EPUB)</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Priority Compilation Engine</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Custom Fonts & Margins</span>
                </li>
              </ul>
            </div>
            <div className="pt-8">
              <button
                onClick={() => openCheckout('tier_3_monthly')}
                className="w-full py-3 px-4 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-600/20 transition-all flex items-center justify-center gap-2"
              >
                <Crown className="w-4 h-4" />
                <span>Subscribe ($29/mo)</span>
              </button>
            </div>
          </div>

          {/* Card 5: Unlimited Annual (Tier 3) */}
          <div className="flex flex-col justify-between p-8 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all">
            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h3 className="text-xl font-bold text-white">Unlimited Annual</h3>
                  <span className="px-2 py-0.5 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded">SAVE 40%</span>
                </div>
                <p className="text-xs text-slate-400">Best value for publishing. Unlimited books and pages.</p>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">$199</span>
                <span className="text-xs text-slate-400">/ year</span>
              </div>
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span className="font-semibold text-white">UNLIMITED Books & Titles</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>All Formats (PDF/DOCX/MD/EPUB)</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Priority Compilation Engine</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>Continuous Cloud Updates & Backups</span>
                </li>
              </ul>
            </div>
            <div className="pt-8">
              <button
                onClick={() => openCheckout('tier_3_annual')}
                className="w-full py-3 px-4 rounded-xl font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/20 transition-all flex items-center justify-center gap-2"
              >
                <Zap className="w-4 h-4 text-amber-300" />
                <span>Go Annual ($199/yr)</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 border-t border-slate-800">
        <h2 className="text-2xl font-bold text-center text-white mb-8">Detailed Feature Comparison</h2>
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-xs font-semibold text-slate-400">
              <tr>
                <th className="py-3 px-4">Feature</th>
                <th className="py-3 px-4 text-center">Free Demo ($0)</th>
                <th className="py-3 px-4 text-center text-amber-400">Book Pass ($9)</th>
                <th className="py-3 px-4 text-center text-amber-400">Monthly Pro ($19/mo)</th>
                <th className="py-3 px-4 text-center text-indigo-400">Unlimited ($29/mo or $199/yr)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              <tr>
                <td className="py-3 px-4 font-medium">Page Limit per Manuscript</td>
                <td className="py-3 px-4 text-center text-slate-400">15 Pages</td>
                <td className="py-3 px-4 text-center font-bold text-emerald-400">Unlimited</td>
                <td className="py-3 px-4 text-center font-bold text-emerald-400">Unlimited</td>
                <td className="py-3 px-4 text-center font-bold text-emerald-400">Unlimited</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium">Print-Ready Typst PDF</td>
                <td className="py-3 px-4 text-center">First 15p + Upsell</td>
                <td className="py-3 px-4 text-center">Full Document</td>
                <td className="py-3 px-4 text-center">Full Document</td>
                <td className="py-3 px-4 text-center">Full Document</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium">Editable Word (.docx) Export</td>
                <td className="py-3 px-4 text-center text-slate-500">❌ Locked</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium">Markdown (.md) Export</td>
                <td className="py-3 px-4 text-center text-slate-500">❌ Locked</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium">EPUB3 Ebook Output</td>
                <td className="py-3 px-4 text-center text-slate-500">❌ Locked</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
                <td className="py-3 px-4 text-center text-emerald-400">✅ Included</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium">Number of Books Included</td>
                <td className="py-3 px-4 text-center">1 Preview</td>
                <td className="py-3 px-4 text-center">1 Complete Book</td>
                <td className="py-3 px-4 text-center text-amber-300">Up to 9 Books / mo</td>
                <td className="py-3 px-4 text-center font-bold text-indigo-400">Unlimited Books</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Checkout Modal */}
      <CheckoutModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        initialTier={targetTier}
      />

      {/* Verification Overlays */}
      {verifyStatus === 'loading' && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-md text-white">
          <Loader2 className="w-12 h-12 text-amber-500 animate-spin mb-4" />
          <h2 className="text-2xl font-bold">Finalizing your payment...</h2>
          <p className="text-slate-400 mt-2">Communicating with the payment provider to secure your access.</p>
        </div>
      )}

      {verifyStatus === 'success' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm">
          <div className="relative w-full max-w-md overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 text-center text-slate-100 animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20 mb-6 mx-auto">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <h2 className="text-3xl font-extrabold text-white mb-2">Upgrade Complete!</h2>
            <p className="text-slate-300 mb-6">
              Thank you! Your transaction has been successfully verified. Your account has been upgraded to the{' '}
              <span className="text-amber-400 font-bold uppercase">{tier?.toUpperCase()}</span> tier.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center w-full">
              <Link
                href="/editor"
                className="flex-1 py-3 px-6 rounded-xl font-bold bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 hover:from-amber-400 hover:to-amber-500 transition-all flex items-center justify-center gap-2"
              >
                <span>Go to Editor</span>
              </Link>
            </div>
          </div>
        </div>
      )}

      {verifyStatus === 'error' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm">
          <div className="relative w-full max-w-md overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 text-center text-slate-100 animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center border border-red-500/20 mb-6 mx-auto">
              <X className="w-8 h-8" />
            </div>
            <h2 className="text-3xl font-extrabold text-white mb-2">Verification Failed</h2>
            <p className="text-red-400 text-sm mb-4">{verifyError || 'An error occurred during verification.'}</p>
            <p className="text-slate-400 text-xs mb-6">
              If payment was captured on PayPal, please check your email or contact support with the transaction ID.
            </p>
            <div className="flex gap-4 w-full">
              <button
                onClick={() => {
                  setVerifyStatus('idle');
                  window.history.replaceState(null, '', window.location.pathname);
                }}
                className="flex-1 py-3 px-6 rounded-xl font-bold bg-slate-800 hover:bg-slate-700 text-white transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100"><Loader2 className="h-8 w-8 animate-spin" /></div>}>
      <CheckoutContent />
    </Suspense>
  );
}
