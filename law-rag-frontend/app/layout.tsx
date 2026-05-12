import type { Metadata, Viewport } from 'next'
import { Inter, Source_Serif_4, Geist_Mono } from 'next/font/google'
import { Toaster } from 'sonner'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin', 'vietnamese'],
  variable: '--font-inter',
})

const sourceSerif = Source_Serif_4({ 
  subsets: ['latin', 'vietnamese'],
  variable: '--font-source-serif',
})

const geistMono = Geist_Mono({ 
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  title: 'Law RAG - Trợ lý pháp luật AI Việt Nam',
  description: 'Hệ thống hỏi đáp pháp luật thông minh, tra cứu văn bản pháp luật Việt Nam với AI. Câu trả lời được trích dẫn nguồn rõ ràng từ các văn bản pháp quy.',
  keywords: ['pháp luật', 'luật Việt Nam', 'tư vấn pháp luật', 'AI', 'tra cứu văn bản pháp luật'],
  authors: [{ name: 'Law RAG Team' }],
  openGraph: {
    title: 'Law RAG - Trợ lý pháp luật AI Việt Nam',
    description: 'Hệ thống hỏi đáp pháp luật thông minh với trích dẫn nguồn rõ ràng',
    type: 'website',
    locale: 'vi_VN',
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f9f8f6' },
    { media: '(prefers-color-scheme: dark)', color: '#1a1a2e' },
  ],
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="vi" className={`${inter.variable} ${sourceSerif.variable} ${geistMono.variable}`}>
      <body className="font-sans antialiased bg-background">
        {children}
        <Toaster 
          position="top-right" 
          toastOptions={{
            className: 'font-sans',
          }}
        />
      </body>
    </html>
  )
}
