import React from 'react';
import Head from 'next/head';
import Link from 'next/link';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen jenni-bg" style={{ backgroundColor: '#171717', color: '#ffffff', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' }}>
      <Head>
        <title>Privacy Policy — ResearchForm</title>
      </Head>
      
      <div className="max-w-3xl mx-auto py-12 px-6">
        <Link href="/" className="text-brand hover:underline mb-8 inline-block" style={{ color: '#6366f1' }}>
          &larr; Back to Home
        </Link>
        
        <h1 className="text-3xl font-bold mb-6">Privacy Policy</h1>
        <p className="text-sm text-gray-400 mb-8">Last updated: {new Date().toLocaleDateString()}</p>
        
        <div className="space-y-6" style={{ color: '#d4d4d4', lineHeight: '1.6' }}>
          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">1. Introduction</h2>
            <p>
              ResearchForm ("we", "our", or "us") respects your privacy and is committed to protecting it through our compliance with this policy. This policy describes the types of information we may collect from you or that you may provide when you visit the ResearchForm website and use our services.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">2. Information We Collect</h2>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>Account Information:</strong> When you register, we collect your name, email address, and institutional affiliation.</li>
              <li><strong>Survey Data:</strong> Data you collect through your surveys, including respondent answers and uploaded files.</li>
              <li><strong>Usage Data:</strong> Information about how you interact with our platform, such as features used and time spent on pages.</li>
              <li><strong>Cookies:</strong> We use cookies to manage sessions and store your preferences.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">3. How We Use Your Information</h2>
            <p>We use the information we collect to:</p>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li>Provide, maintain, and improve our services.</li>
              <li>Process your analysis requests using AI models.</li>
              <li>Manage your account and communicate with you.</li>
              <li>Ensure the security and integrity of our platform.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">4. Artificial Intelligence Processing</h2>
            <p>
              ResearchForm uses AI models to analyze your survey data. The data you submit for analysis is processed securely. We do not use your survey data or analysis results to train our foundational AI models.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">5. Data Sharing and Disclosure</h2>
            <p>
              We do not sell your personal information or survey data. We may share information with third-party service providers (such as hosting providers and payment processors) strictly for the purpose of operating our service. We may also disclose information if required by law.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">6. Data Security</h2>
            <p>
              We implement appropriate technical and organizational measures to secure your personal information and survey data from accidental loss and from unauthorized access, use, alteration, and disclosure.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">7. Your Rights</h2>
            <p>
              You can review and change your personal information by logging into the website and visiting your account profile page. You may also request deletion of your account and associated data.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold mb-3 text-white">8. Contact Us</h2>
            <p>
              To ask questions or comment about this privacy policy and our privacy practices, contact us at: support@researchform.app.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
