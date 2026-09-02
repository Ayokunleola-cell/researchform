import React from 'react';
import Head from 'next/head';
import Link from 'next/link';

export default function TermsPage() {
  return (
    <div className="min-h-screen jenni-bg" style={{ backgroundColor: '#171717', color: '#ffffff', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' }}>
      <Head>
        <title>Terms of Service — ResearchForm</title>
      </Head>
      
      <div className="max-w-3xl mx-auto py-12 px-6">
        <Link href="/" className="text-brand hover:underline mb-8 inline-block" style={{ color: '#6366f1' }}>
          &larr; Back to Home
        </Link>
        
        <h1 className="text-3xl font-bold mb-6">Terms of Service</h1>
        <p className="text-sm text-gray-400 mb-8">Last updated: {new Date().toLocaleDateString()}</p>
        
        <div className="space-y-6" style={{ color: '#d4d4d4', lineHeight: '1.6' }}>
          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">1. Acceptance of Terms</h2>
            <p>
              By accessing or using ResearchForm, you agree to be bound by these Terms of Service. If you disagree with any part of the terms, you may not access the service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">2. Description of Service</h2>
            <p>
              ResearchForm provides tools for creating surveys, collecting responses, and analyzing data using artificial intelligence. We reserve the right to modify, suspend, or discontinue the service at any time.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">3. User Accounts</h2>
            <p>
              You are responsible for maintaining the confidentiality of your account and password. You agree to accept responsibility for all activities that occur under your account.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">4. Data and Privacy</h2>
            <p>
              Your use of ResearchForm is also governed by our Privacy Policy. You retain all rights to the data you upload or collect through our surveys. ResearchForm will only use your data as necessary to provide the service and as outlined in our Privacy Policy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">5. Acceptable Use</h2>
            <p>
              You agree not to use ResearchForm to collect sensitive personal information without proper authorization, to distribute spam, or to engage in any unlawful activities.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">6. Intellectual Property</h2>
            <p>
              The ResearchForm platform, including its original content, features, and functionality, is owned by ResearchForm and is protected by international copyright, trademark, and other intellectual property laws.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">7. Limitation of Liability</h2>
            <p>
              In no event shall ResearchForm be liable for any indirect, incidental, special, consequential, or punitive damages arising out of your use of the service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">8. Changes to Terms</h2>
            <p>
              We reserve the right to modify these terms at any time. We will notify users of any significant changes. Your continued use of the service after such modifications constitutes your acceptance of the new terms.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">9. Contact Us</h2>
            <p>
              If you have any questions about these Terms, please contact us at support@researchform.app.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
