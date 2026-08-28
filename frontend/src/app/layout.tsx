import type { Metadata } from 'next';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import QueryProvider from '@/components/providers/QueryProvider';

export const metadata: Metadata = {
  title: 'BookCraft AI',
  description: 'AI-powered book formatting and compilation platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 font-sans antialiased">
        <QueryProvider>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#1f2937',
                color: '#f9fafb',
                borderRadius: '8px',
              },
            }}
          />
        </QueryProvider>
      </body>
    </html>
  );
}
