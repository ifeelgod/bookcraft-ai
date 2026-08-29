'use client';

import React, { useState } from 'react';
import {
  Check,
  CreditCard,
  Lock,
  Sparkles,
  X,
  Zap,
  ShieldCheck,
  ExternalLink,
} from 'lucide-react';
import { createCheckoutSession, verifyPaymentSession } from '@/lib/api';
import { useAuth } from '@/lib/authStore';
import type { VerifyPaymentResult } from '@/types/api';

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTier?: 'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual';
  onSuccess?: (result: VerifyPaymentResult) => void;
}

export function CheckoutModal({
  isOpen,
  onClose,
  initialTier = 'tier_1_pass',
  onSuccess,
}: CheckoutModalProps) {
  const { email: authEmail, name: authName, login } = useAuth();
  const [selectedTier, setSelectedTier] = useState<'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual'>(initialTier);
  const [email, setEmail] = useState(authEmail || '');
  const [name, setName] = useState(authName || '');
  const [loading, setLoading] = useState(false);
  const [paymentProvider, setPaymentProvider] = useState<'stripe' | 'paypal' | 'simulate'>('paypal');
  const [error, setError] = useState<string | null>(null);
  const [completedResult, setCompletedResult] = useState<VerifyPaymentResult | null>(null);

  if (!isOpen) return null;

  const handleCheckout = async (providerOverride?: 'stripe' | 'paypal' | 'simulate') => {
    setError(null);
    setLoading(true);
    const provider = providerOverride || paymentProvider;

    const userEmail = (email || 'author@example.com').trim();
    const userName = (name || 'Pro Author').trim();

    try {
      if (provider === 'simulate') {
        // Direct test verification for local test mode
        const res = await verifyPaymentSession({
          provider: 'paypal',
          session_id: `ORDER-TEST-simulated-${Date.now()}`,
          order_id: `ORDER-TEST-simulated-${Date.now()}`,
          lead_email: userEmail,
          lead_name: userName,
          tier: selectedTier,
        });

        if (res.success && res.access_token) {
          login(res.access_token, res.tier, userEmail, userName, res.expires_at || undefined);
          setCompletedResult(res);
          onSuccess?.(res);
        }
        return;
      }

      // Live / Sandbox Checkout
      const checkoutRes = await createCheckoutSession({
        provider: provider as 'stripe' | 'paypal',
        tier: selectedTier,
        lead_email: userEmail,
        lead_name: userName,
      });

      if (checkoutRes.checkout_url) {
        // If simulation or test redirect
        if (checkoutRes.mode === 'test' || checkoutRes.checkout_url.includes('ORDER-TEST-') || checkoutRes.checkout_url.includes('test')) {
          // Complete verification directly in test mode
          const verifyRes = await verifyPaymentSession({
            provider: provider as 'stripe' | 'paypal',
            session_id: checkoutRes.session_id,
            order_id: checkoutRes.session_id,
            lead_email: userEmail,
            lead_name: userName,
            tier: selectedTier,
          });

          if (verifyRes.success && verifyRes.access_token) {
            login(verifyRes.access_token, verifyRes.tier, userEmail, userName, verifyRes.expires_at || undefined);
            setCompletedResult(verifyRes);
            onSuccess?.(verifyRes);
          }
        } else {
          // Redirect to PayPal
          window.location.href = checkoutRes.checkout_url;
        }
      }
    } catch (err: any) {
      setError(err.message || 'Payment initiation failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-2xl overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl text-slate-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Upgrade to BookCraft Pro</h2>
              <p className="text-xs text-slate-400">Unlock unlimited pages, editable Word & Markdown downloads</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          {completedResult ? (
            <div className="py-8 text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Check className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="text-2xl font-bold text-white">Upgrade Complete!</h3>
                <p className="text-sm text-slate-300">
                  Your <span className="font-semibold text-emerald-400">{completedResult.tier.toUpperCase()}</span> access token is now active.
                </p>
                <p className="text-xs text-slate-400">
                  All 15-page limits have been lifted. You can now compile full manuscripts and download DOCX/MD/EPUB files.
                </p>
              </div>
              <div className="pt-4">
                <button
                  onClick={onClose}
                  className="px-6 py-2.5 font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow-lg shadow-emerald-600/20 transition-all"
                >
                  Continue to Editor
                </button>
              </div>
            </div>
          ) : (
            <>
              {error && (
                <div className="p-3 text-sm text-red-400 bg-red-950/40 border border-red-800/50 rounded-lg">
                  {error}
                </div>
              )}

              {/* Tier Selection Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[300px] overflow-y-auto pr-1">
                {/* Tier 1 Pass Card */}
                <div
                  onClick={() => setSelectedTier('tier_1_pass')}
                  className={`cursor-pointer relative p-4 rounded-xl border transition-all ${
                    selectedTier === 'tier_1_pass'
                      ? 'border-amber-500 bg-amber-500/5 ring-1 ring-amber-500'
                      : 'border-slate-800 bg-slate-800/30 hover:border-slate-700'
                  }`}
                >
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">Single Book Pass</h3>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-extrabold text-white">$9</span>
                      <span className="text-2xs text-slate-400">/ one-time</span>
                    </div>
                    <p className="text-2xs text-slate-400">
                      Perfect for publishing a single manuscript with unlimited pages.
                    </p>
                  </div>
                  <ul className="mt-3 space-y-1 text-2xs text-slate-300">
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-amber-400 flex-shrink-0" />
                      <span>Single book, unlimited pages</span>
                    </li>
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-amber-400 flex-shrink-0" />
                      <span>DOCX, MD, EPUB, PDF Exports</span>
                    </li>
                  </ul>
                </div>

                {/* Tier 2 Monthly Card */}
                <div
                  onClick={() => setSelectedTier('tier_2_monthly')}
                  className={`cursor-pointer relative p-4 rounded-xl border transition-all ${
                    selectedTier === 'tier_2_monthly'
                      ? 'border-amber-500 bg-amber-500/5 ring-1 ring-amber-500'
                      : 'border-slate-800 bg-slate-800/30 hover:border-slate-700'
                  }`}
                >
                  <div className="absolute top-2 right-2 px-1.5 py-0.5 text-[8px] font-semibold text-amber-300 bg-amber-500/20 rounded-full border border-amber-500/30">
                    POPULAR
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">Monthly Pro</h3>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-extrabold text-white">$19</span>
                      <span className="text-2xs text-slate-400">/ month</span>
                    </div>
                    <p className="text-2xs text-slate-400">
                      Ideal for regular authors formatting up to 9 books / month.
                    </p>
                  </div>
                  <ul className="mt-3 space-y-1 text-2xs text-slate-300">
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-amber-400 flex-shrink-0" />
                      <span>Up to 9 books per month</span>
                    </li>
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-amber-400 flex-shrink-0" />
                      <span>All formats & premium compilation</span>
                    </li>
                  </ul>
                </div>

                {/* Tier 3 Monthly Card */}
                <div
                  onClick={() => setSelectedTier('tier_3_monthly')}
                  className={`cursor-pointer relative p-4 rounded-xl border transition-all ${
                    selectedTier === 'tier_3_monthly'
                      ? 'border-indigo-500 bg-indigo-500/5 ring-1 ring-indigo-500'
                      : 'border-slate-800 bg-slate-800/30 hover:border-slate-700'
                  }`}
                >
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">Unlimited Monthly</h3>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-extrabold text-white">$29</span>
                      <span className="text-2xs text-slate-400">/ month</span>
                    </div>
                    <p className="text-2xs text-slate-400">
                      Unlimited books and pages for publishers and prolific writers.
                    </p>
                  </div>
                  <ul className="mt-3 space-y-1 text-2xs text-slate-300">
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                      <span>UNLIMITED books and pages</span>
                    </li>
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                      <span>Priority queue & custom fonts</span>
                    </li>
                  </ul>
                </div>

                {/* Tier 3 Annual Card */}
                <div
                  onClick={() => setSelectedTier('tier_3_annual')}
                  className={`cursor-pointer relative p-4 rounded-xl border transition-all ${
                    selectedTier === 'tier_3_annual'
                      ? 'border-indigo-500 bg-indigo-500/5 ring-1 ring-indigo-500'
                      : 'border-slate-800 bg-slate-800/30 hover:border-slate-700'
                  }`}
                >
                  <div className="absolute top-2 right-2 px-1.5 py-0.5 text-[8px] font-semibold text-emerald-300 bg-emerald-500/20 rounded-full border border-emerald-500/30">
                    SAVE 40%
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">Unlimited Annual</h3>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-extrabold text-white">$199</span>
                      <span className="text-2xs text-slate-400">/ year</span>
                    </div>
                    <p className="text-2xs text-slate-400">
                      Best value. Unlimited formatting billed once per year.
                    </p>
                  </div>
                  <ul className="mt-3 space-y-1 text-2xs text-slate-300">
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                      <span>UNLIMITED books and pages</span>
                    </li>
                    <li className="flex items-center gap-1.5">
                      <Check className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                      <span>Includes all formatting updates</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* Author Details Inputs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Your Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Jane Austen"
                    className="w-full px-3 py-2 text-sm bg-slate-800/60 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="author@example.com"
                    className="w-full px-3 py-2 text-sm bg-slate-800/60 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              {/* Payment Action Buttons */}
              <div className="space-y-2 pt-3 border-t border-slate-800">
                <div className="flex flex-col gap-3">
                  {/* PayPal Button (PayPal Only) */}
                  <button
                    onClick={() => handleCheckout('paypal')}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-bold text-slate-900 bg-[#FFC439] hover:bg-[#F2BA30] shadow-lg shadow-[#FFC439]/20 disabled:opacity-50 transition-all"
                  >
                    <span className="font-bold italic">PayPal</span>
                    <span>Checkout ({selectedTier === 'tier_3_annual' ? '$199' : selectedTier === 'tier_3_monthly' ? '$29' : selectedTier === 'tier_2_monthly' ? '$19' : '$9'})</span>
                  </button>
                </div>

                {/* Instant Simulation Test Mode Button */}
                <button
                  onClick={() => handleCheckout('simulate')}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium text-slate-400 hover:text-white bg-slate-800/40 hover:bg-slate-800 border border-slate-700/60 rounded-lg transition-colors"
                >
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  <span>Instant Test Mode Simulation (Auto-Activate Pro Token)</span>
                </button>
              </div>

              {/* Trust Footer */}
              <div className="flex items-center justify-center gap-4 text-[11px] text-slate-500 pt-1">
                <div className="flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>256-Bit SSL Encryption</span>
                </div>
                <div>•</div>
                <div>Test Mode Supported</div>
                <div>•</div>
                <div>Instant Token Unlock</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
