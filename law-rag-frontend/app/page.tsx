'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { 
  Scale, 
  Search, 
  FileText, 
  Shield, 
  ArrowRight, 
  BookOpen,
  MessageSquare,
  Database,
  Sparkles,
  CheckCircle2
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border">
        <nav className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center gap-2">
              <Scale className="h-7 w-7 text-primary" />
              <span className="font-semibold text-lg tracking-tight">Law RAG</span>
            </Link>
            <div className="hidden md:flex items-center gap-8">
              <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Tính năng
              </Link>
              <Link href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Cách hoạt động
              </Link>
              <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Quản trị
              </Link>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
                <Link href="/admin">Quản trị</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href="/chat">
                  Bắt đầu hỏi
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/50 text-accent-foreground text-sm mb-6">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Trợ lý pháp luật AI thế hệ mới</span>
            </div>
            
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance leading-tight">
              Tra cứu pháp luật Việt Nam
              <span className="block text-primary">thông minh và minh bạch</span>
            </h1>
            
            <p className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed">
              Hỏi đáp pháp luật bằng ngôn ngữ tự nhiên. Mỗi câu trả lời đều được trích dẫn rõ ràng 
              từ các văn bản pháp quy chính thức của Việt Nam.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Button size="lg" asChild className="w-full sm:w-auto">
              <Link href="/chat">
                <MessageSquare className="mr-2 h-5 w-5" />
                Đặt câu hỏi pháp luật
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="w-full sm:w-auto">
              <Link href="#how-it-works">
                Tìm hiểu thêm
              </Link>
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Demo Preview */}
      <section className="pb-20 px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="max-w-5xl mx-auto"
        >
          <div className="relative bg-card rounded-xl border border-border shadow-2xl shadow-primary/5 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent/20 via-transparent to-transparent" />
            <div className="relative p-6 sm:p-8">
              {/* Mock Chat Interface */}
              <div className="space-y-6">
                {/* User Message */}
                <div className="flex justify-end">
                  <div className="max-w-md bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-3">
                    <p className="text-sm">Tôi muốn hỏi về thuế thu nhập cá nhân khi bán nhà ở?</p>
                  </div>
                </div>
                
                {/* Assistant Message */}
                <div className="flex justify-start">
                  <div className="max-w-2xl bg-secondary rounded-2xl rounded-bl-md px-5 py-4">
                    <div className="space-y-3">
                      <div className="flex items-start gap-2">
                        <Scale className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium text-sm">Kết luận chính</p>
                          <p className="text-sm text-muted-foreground mt-1">
                            Khi bán nhà, thuế TNCN là 2% trên giá trị chuyển nhượng. Trường hợp nhà ở duy nhất có thể được miễn thuế.
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-start gap-2">
                        <FileText className="h-5 w-5 text-accent mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium text-sm">Căn cứ pháp lý</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-background text-xs font-medium">
                              Luật Thuế TNCN - Điều 3, 4
                            </span>
                            <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-background text-xs font-medium">
                              TT 111/2013/TT-BTC
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Trust Indicators */}
      <section className="py-12 border-y border-border bg-muted/30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-3xl font-semibold text-primary">1,200+</div>
              <div className="mt-1 text-sm text-muted-foreground">Văn bản pháp luật</div>
            </div>
            <div>
              <div className="text-3xl font-semibold text-primary">45,000+</div>
              <div className="mt-1 text-sm text-muted-foreground">Điều khoản được index</div>
            </div>
            <div>
              <div className="text-3xl font-semibold text-primary">100%</div>
              <div className="mt-1 text-sm text-muted-foreground">Trích dẫn nguồn</div>
            </div>
            <div>
              <div className="text-3xl font-semibold text-primary">24/7</div>
              <div className="mt-1 text-sm text-muted-foreground">Sẵn sàng hỗ trợ</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
              Tại sao chọn Law RAG?
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
              Công nghệ RAG (Retrieval-Augmented Generation) đảm bảo mỗi câu trả lời 
              đều có căn cứ từ văn bản pháp luật thực tế.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Search className="h-6 w-6" />}
              title="Tìm kiếm thông minh"
              description="Kết hợp BM25 và vector search để tìm kiếm chính xác điều khoản pháp luật liên quan đến câu hỏi của bạn."
            />
            <FeatureCard
              icon={<FileText className="h-6 w-6" />}
              title="Trích dẫn minh bạch"
              description="Mỗi câu trả lời đều kèm theo trích dẫn cụ thể từ Luật, Nghị định, Thông tư - bạn có thể tra cứu nguồn gốc."
            />
            <FeatureCard
              icon={<MessageSquare className="h-6 w-6" />}
              title="Hội thoại liên tục"
              description="Hệ thống ghi nhớ ngữ cảnh cuộc trò chuyện, cho phép bạn đặt câu hỏi tiếp theo một cách tự nhiên."
            />
            <FeatureCard
              icon={<Shield className="h-6 w-6" />}
              title="Phân biệt rõ ràng"
              description="Câu trả lời phân biệt rõ: căn cứ pháp lý, diễn giải của AI, và thông tin còn thiếu cần bổ sung."
            />
            <FeatureCard
              icon={<Database className="h-6 w-6" />}
              title="Cơ sở dữ liệu cập nhật"
              description="Hệ thống thu thập và cập nhật văn bản pháp luật mới từ các nguồn chính thức của Việt Nam."
            />
            <FeatureCard
              icon={<BookOpen className="h-6 w-6" />}
              title="Hỗ trợ OCR"
              description="Tải lên văn bản scan, hệ thống sẽ nhận dạng và phân tích nội dung pháp lý trong tài liệu của bạn."
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
              Cách hoạt động
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Ba bước đơn giản để có câu trả lời pháp luật đáng tin cậy
            </p>
          </div>

          <div className="space-y-8">
            <StepCard
              number="01"
              title="Đặt câu hỏi bằng ngôn ngữ tự nhiên"
              description="Bạn hỏi bất kỳ câu hỏi pháp luật nào bằng tiếng Việt. Hệ thống sẽ phân tích và viết lại câu hỏi để tìm kiếm hiệu quả hơn."
            />
            <StepCard
              number="02"
              title="Tìm kiếm trong kho văn bản pháp luật"
              description="Hệ thống tìm kiếm trong hơn 1,200 văn bản pháp luật bằng công nghệ hybrid (BM25 + semantic search) để tìm ra các điều khoản liên quan nhất."
            />
            <StepCard
              number="03"
              title="Tổng hợp và trích dẫn nguồn"
              description="AI tổng hợp thông tin từ các nguồn tìm được, đưa ra câu trả lời có cấu trúc với trích dẫn cụ thể để bạn có thể xác minh."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            Sẵn sàng tra cứu pháp luật?
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Bắt đầu ngay - hoàn toàn miễn phí và không cần đăng ký.
          </p>
          <div className="mt-8">
            <Button size="lg" asChild>
              <Link href="/chat">
                <MessageSquare className="mr-2 h-5 w-5" />
                Bắt đầu hỏi ngay
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <Scale className="h-6 w-6 text-primary" />
              <span className="font-semibold">Law RAG</span>
            </div>
            <p className="text-sm text-muted-foreground text-center md:text-left">
              Lưu ý: Thông tin trên hệ thống mang tính chất tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.
            </p>
            <div className="flex items-center gap-6">
              <Link href="/chat" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Hỏi đáp
              </Link>
              <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Quản trị
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="p-6 rounded-xl bg-card border border-border hover:shadow-lg hover:shadow-primary/5 transition-shadow">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-primary/10 text-primary mb-4">
        {icon}
      </div>
      <h3 className="font-semibold text-lg mb-2">{title}</h3>
      <p className="text-muted-foreground text-sm leading-relaxed">{description}</p>
    </div>
  )
}

function StepCard({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div className="flex gap-6 p-6 rounded-xl bg-card border border-border">
      <div className="flex-shrink-0">
        <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-semibold">
          {number}
        </div>
      </div>
      <div>
        <h3 className="font-semibold text-lg mb-2">{title}</h3>
        <p className="text-muted-foreground leading-relaxed">{description}</p>
      </div>
    </div>
  )
}
