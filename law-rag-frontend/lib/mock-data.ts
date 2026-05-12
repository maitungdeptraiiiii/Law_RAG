// Law RAG Mock Data
// Realistic sample data for development and demonstration

import type {
  Session,
  Conversation,
  Message,
  LegalDocument,
  RetrievedSource,
  CorpusStatus,
  PipelineJob,
} from './types'

// ==================== Sessions ====================

export const mockSessions: Session[] = [
  {
    id: 'session-1',
    title: 'Quy định về thuế thu nhập cá nhân',
    createdAt: new Date('2024-01-15T10:30:00'),
    updatedAt: new Date('2024-01-15T11:45:00'),
    messageCount: 6,
    preview: 'Tôi muốn hỏi về thuế thu nhập cá nhân khi bán nhà...',
  },
  {
    id: 'session-2',
    title: 'Thủ tục đăng ký kinh doanh',
    createdAt: new Date('2024-01-14T14:20:00'),
    updatedAt: new Date('2024-01-14T15:30:00'),
    messageCount: 4,
    preview: 'Quy trình đăng ký doanh nghiệp tư nhân cần những giấy tờ gì?',
  },
  {
    id: 'session-3',
    title: 'Quyền thừa kế theo pháp luật',
    createdAt: new Date('2024-01-13T09:00:00'),
    updatedAt: new Date('2024-01-13T10:15:00'),
    messageCount: 8,
    preview: 'Thừa kế không có di chúc được quy định như thế nào?',
  },
  {
    id: 'session-4',
    title: 'Hợp đồng lao động và bảo hiểm',
    createdAt: new Date('2024-01-12T16:45:00'),
    updatedAt: new Date('2024-01-12T17:30:00'),
    messageCount: 5,
    preview: 'Quyền lợi bảo hiểm xã hội khi nghỉ việc...',
    archived: true,
  },
]

// ==================== Conversations ====================

export const mockConversations: Record<string, Conversation> = {
  'session-1': {
    sessionId: 'session-1',
    messages: [
      {
        id: 'msg-1',
        role: 'user',
        content: 'Tôi muốn hỏi về thuế thu nhập cá nhân khi bán nhà. Tôi đã sở hữu căn nhà này được 5 năm và muốn bán với giá 3 tỷ đồng.',
        timestamp: new Date('2024-01-15T10:30:00'),
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: `## Kết luận chính

Khi bán nhà, bạn có thể chịu thuế thu nhập cá nhân (TNCN) với mức 2% trên giá trị chuyển nhượng hoặc 25% trên thu nhập chịu thuế, tùy vào việc bạn có xác định được giá vốn hay không.

## Căn cứ pháp lý

**Luật Thuế thu nhập cá nhân** (Luật số 04/2007/QH12, sửa đổi bổ sung 2012) quy định tại Điều 3 và Điều 14:
- Thu nhập từ chuyển nhượng bất động sản là thu nhập chịu thuế
- Thuế suất 2% trên giá chuyển nhượng nếu không xác định được giá vốn
- Thuế suất 25% trên thu nhập chịu thuế nếu xác định được giá vốn

**Thông tư 111/2013/TT-BTC** hướng dẫn chi tiết về cách tính thuế.

## Trường hợp được miễn thuế

Bạn có thể được miễn thuế nếu:
- Chuyển nhượng nhà ở duy nhất
- Thu nhập từ chuyển nhượng giữa vợ chồng, cha mẹ con cái
- Thu nhập từ thừa kế, quà tặng bất động sản giữa người thân

## Thông tin cần bổ sung

⚠️ Để tư vấn chính xác, bạn vui lòng cho biết:
- Đây có phải nhà ở duy nhất không?
- Giá mua ban đầu là bao nhiêu?
- Bạn có các hóa đơn, chứng từ mua nhà không?`,
        timestamp: new Date('2024-01-15T10:31:00'),
        sources: [
          {
            id: 'src-1',
            documentId: 'doc-1',
            documentTitle: 'Luật Thuế thu nhập cá nhân 2007 (sửa đổi 2012)',
            articleNumber: 'Điều 3, Điều 14',
            chunkText: 'Thu nhập chịu thuế từ chuyển nhượng bất động sản bao gồm thu nhập từ chuyển nhượng quyền sử dụng đất và tài sản gắn liền với đất...',
            relevanceScore: 0.95,
            retrievalOrigin: 'hybrid',
            documentType: 'law',
          },
          {
            id: 'src-2',
            documentId: 'doc-2',
            documentTitle: 'Thông tư 111/2013/TT-BTC',
            articleNumber: 'Điều 12',
            chunkText: 'Thuế thu nhập cá nhân đối với thu nhập từ chuyển nhượng bất động sản được xác định như sau: Thuế TNCN = Giá chuyển nhượng × 2%...',
            relevanceScore: 0.89,
            retrievalOrigin: 'vector',
            documentType: 'circular',
          },
        ],
        metadata: {
          retrievalMode: 'hybrid',
          modelUsed: 'gpt-4',
          processingTimeMs: 1456,
        },
      },
      {
        id: 'msg-3',
        role: 'user',
        content: 'Đây là nhà ở duy nhất của tôi. Vậy tôi có được miễn thuế không?',
        timestamp: new Date('2024-01-15T10:35:00'),
      },
      {
        id: 'msg-4',
        role: 'assistant',
        content: `## Kết luận

**Có**, nếu đây là nhà ở duy nhất và bạn đáp ứng đủ điều kiện, bạn sẽ được **miễn thuế thu nhập cá nhân** khi chuyển nhượng.

## Điều kiện miễn thuế

Theo **Điều 4 Luật Thuế TNCN** và **Điều 4 Thông tư 111/2013/TT-BTC**, bạn được miễn thuế khi:

1. ✅ Đây là nhà ở, đất ở **duy nhất** của bạn
2. ✅ Bạn có quyền sở hữu nhà và quyền sử dụng đất ở
3. ✅ Bạn đã đăng ký thường trú tại địa chỉ này

## Hồ sơ cần chuẩn bị

Để được miễn thuế, bạn cần:
- Đơn đề nghị miễn thuế TNCN
- Giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà
- Sổ hộ khẩu thường trú
- Giấy xác nhận của UBND xã/phường về việc chỉ có một nhà ở duy nhất

## Lưu ý quan trọng

⚠️ Điều kiện "duy nhất" nghĩa là tại thời điểm chuyển nhượng, bạn chỉ có 01 nhà ở/đất ở duy nhất. Nếu bạn đồng sở hữu với người khác hoặc có nhà ở khác (kể cả đứng tên chung), bạn có thể không đủ điều kiện miễn thuế.`,
        timestamp: new Date('2024-01-15T10:36:00'),
        sources: [
          {
            id: 'src-3',
            documentId: 'doc-1',
            documentTitle: 'Luật Thuế thu nhập cá nhân 2007 (sửa đổi 2012)',
            articleNumber: 'Điều 4',
            chunkText: 'Thu nhập được miễn thuế: Thu nhập từ chuyển nhượng nhà ở, quyền sử dụng đất ở và tài sản gắn liền với đất ở của cá nhân trong trường hợp cá nhân chỉ có một nhà ở, đất ở duy nhất...',
            relevanceScore: 0.98,
            retrievalOrigin: 'hybrid',
            documentType: 'law',
          },
        ],
        metadata: {
          retrievalMode: 'hybrid',
          modelUsed: 'gpt-4',
          processingTimeMs: 1234,
        },
      },
    ],
  },
}

// ==================== Legal Documents ====================

export const mockDocuments: LegalDocument[] = [
  {
    id: 'doc-1',
    title: 'Luật Thuế thu nhập cá nhân',
    documentNumber: '04/2007/QH12',
    documentType: 'law',
    issuedDate: '2007-11-21',
    effectiveDate: '2009-01-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-thue-thu-nhap-ca-nhan-2007-04-2007-QH12-58574.aspx',
    status: 'indexed',
    chunkCount: 156,
    crawledAt: new Date('2024-01-01'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Luật này quy định về đối tượng nộp thuế, thu nhập chịu thuế, thu nhập được miễn thuế, giảm thuế và căn cứ tính thuế thu nhập cá nhân...',
  },
  {
    id: 'doc-2',
    title: 'Thông tư hướng dẫn Luật Thuế TNCN',
    documentNumber: '111/2013/TT-BTC',
    documentType: 'circular',
    issuedDate: '2013-08-15',
    effectiveDate: '2013-10-01',
    issuingAuthority: 'Bộ Tài chính',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Thong-tu-111-2013-TT-BTC-huong-dan-Luat-thue-thu-nhap-ca-nhan-201091.aspx',
    status: 'indexed',
    chunkCount: 234,
    crawledAt: new Date('2024-01-01'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Thông tư này hướng dẫn thực hiện một số điều của Luật Thuế thu nhập cá nhân, Luật sửa đổi, bổ sung một số điều của Luật Thuế thu nhập cá nhân...',
  },
  {
    id: 'doc-3',
    title: 'Bộ luật Dân sự 2015',
    documentNumber: '91/2015/QH13',
    documentType: 'law',
    issuedDate: '2015-11-24',
    effectiveDate: '2017-01-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx',
    status: 'indexed',
    chunkCount: 892,
    crawledAt: new Date('2024-01-02'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Bộ luật này quy định địa vị pháp lý, chuẩn mực pháp lý về cách ứng xử của cá nhân, pháp nhân; quyền, nghĩa vụ về nhân thân và tài sản...',
  },
  {
    id: 'doc-4',
    title: 'Luật Doanh nghiệp 2020',
    documentNumber: '59/2020/QH14',
    documentType: 'law',
    issuedDate: '2020-06-17',
    effectiveDate: '2021-01-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Doanh-nghiep-2020-so-59-2020-QH14-427301.aspx',
    status: 'indexed',
    chunkCount: 345,
    crawledAt: new Date('2024-01-02'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Luật này quy định về việc thành lập, tổ chức quản lý, tổ chức lại, giải thể và hoạt động có liên quan của doanh nghiệp...',
  },
  {
    id: 'doc-5',
    title: 'Bộ luật Lao động 2019',
    documentNumber: '45/2019/QH14',
    documentType: 'law',
    issuedDate: '2019-11-20',
    effectiveDate: '2021-01-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/Bo-Luat-lao-dong-2019-45-2019-QH14-430580.aspx',
    status: 'indexed',
    chunkCount: 567,
    crawledAt: new Date('2024-01-03'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Bộ luật này quy định tiêu chuẩn lao động; quyền, nghĩa vụ, trách nhiệm của người lao động, người sử dụng lao động...',
  },
  {
    id: 'doc-6',
    title: 'Luật Đất đai 2024',
    documentNumber: '31/2024/QH15',
    documentType: 'law',
    issuedDate: '2024-01-18',
    effectiveDate: '2024-08-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-31-2024-QH15-590839.aspx',
    status: 'chunked',
    chunkCount: 0,
    crawledAt: new Date('2024-01-20'),
    lastUpdated: new Date('2024-01-20'),
    previewText: 'Luật này quy định về chế độ sở hữu đất đai, quyền hạn và trách nhiệm của Nhà nước đại diện chủ sở hữu toàn dân về đất đai...',
  },
  {
    id: 'doc-7',
    title: 'Nghị định hướng dẫn Luật Doanh nghiệp',
    documentNumber: '01/2021/NĐ-CP',
    documentType: 'decree',
    issuedDate: '2021-01-04',
    effectiveDate: '2021-01-04',
    issuingAuthority: 'Chính phủ',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Nghi-dinh-01-2021-ND-CP-dang-ky-doanh-nghiep-463092.aspx',
    status: 'indexed',
    chunkCount: 189,
    crawledAt: new Date('2024-01-03'),
    lastUpdated: new Date('2024-01-10'),
    previewText: 'Nghị định này quy định chi tiết về đăng ký doanh nghiệp, đăng ký hộ kinh doanh...',
  },
  {
    id: 'doc-8',
    title: 'Luật Hôn nhân và Gia đình 2014',
    documentNumber: '52/2014/QH13',
    documentType: 'law',
    issuedDate: '2014-06-19',
    effectiveDate: '2015-01-01',
    issuingAuthority: 'Quốc hội',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Luat-Hon-nhan-va-gia-dinh-2014-238640.aspx',
    status: 'crawled',
    chunkCount: 0,
    crawledAt: new Date('2024-01-15'),
    lastUpdated: new Date('2024-01-15'),
    previewText: 'Luật này quy định chế độ hôn nhân và gia đình; chuẩn mực pháp lý cho cách ứng xử của các thành viên gia đình...',
  },
]

// ==================== Retrieved Sources ====================

export const mockSources: RetrievedSource[] = [
  {
    id: 'src-1',
    documentId: 'doc-1',
    documentTitle: 'Luật Thuế thu nhập cá nhân 2007 (sửa đổi 2012)',
    articleNumber: 'Điều 3',
    clauseNumber: 'Khoản 5',
    chunkText: 'Thu nhập chịu thuế từ chuyển nhượng bất động sản, bao gồm:\na) Thu nhập từ chuyển nhượng quyền sử dụng đất và tài sản gắn liền với đất;\nb) Thu nhập từ chuyển nhượng quyền sở hữu hoặc sử dụng nhà ở;\nc) Thu nhập từ chuyển nhượng quyền thuê đất, quyền thuê mặt nước;\nd) Các khoản thu nhập khác nhận được từ chuyển nhượng bất động sản dưới mọi hình thức.',
    relevanceScore: 0.95,
    retrievalOrigin: 'hybrid',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-thue-thu-nhap-ca-nhan-2007-04-2007-QH12-58574.aspx',
    issuedDate: '2007-11-21',
    documentType: 'law',
  },
  {
    id: 'src-2',
    documentId: 'doc-2',
    documentTitle: 'Thông tư 111/2013/TT-BTC',
    articleNumber: 'Điều 12',
    clauseNumber: 'Khoản 1',
    chunkText: 'Thuế thu nhập cá nhân đối với thu nhập từ chuyển nhượng bất động sản được xác định như sau:\n1. Trường hợp chuyển nhượng bất động sản không xác định được giá vốn:\nThuế TNCN phải nộp = Giá chuyển nhượng × 2%\n2. Trường hợp chuyển nhượng bất động sản xác định được giá vốn và các chi phí liên quan:\nThuế TNCN phải nộp = (Giá chuyển nhượng - Giá vốn - Chi phí) × 25%',
    relevanceScore: 0.91,
    retrievalOrigin: 'vector',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Thong-tu-111-2013-TT-BTC-huong-dan-Luat-thue-thu-nhap-ca-nhan-201091.aspx',
    issuedDate: '2013-08-15',
    documentType: 'circular',
  },
  {
    id: 'src-3',
    documentId: 'doc-1',
    documentTitle: 'Luật Thuế thu nhập cá nhân 2007 (sửa đổi 2012)',
    articleNumber: 'Điều 4',
    clauseNumber: 'Khoản 1, điểm b',
    chunkText: 'Thu nhập được miễn thuế:\nb) Thu nhập từ chuyển nhượng nhà ở, quyền sử dụng đất ở và tài sản gắn liền với đất ở của cá nhân trong trường hợp cá nhân chỉ có một nhà ở, đất ở duy nhất;',
    relevanceScore: 0.88,
    retrievalOrigin: 'bm25',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-thue-thu-nhap-ca-nhan-2007-04-2007-QH12-58574.aspx',
    issuedDate: '2007-11-21',
    documentType: 'law',
  },
  {
    id: 'src-4',
    documentId: 'doc-3',
    documentTitle: 'Bộ luật Dân sự 2015',
    articleNumber: 'Điều 117',
    chunkText: 'Điều kiện có hiệu lực của giao dịch dân sự:\n1. Giao dịch dân sự có hiệu lực khi có đủ các điều kiện sau đây:\na) Chủ thể có năng lực pháp luật dân sự, năng lực hành vi dân sự phù hợp với giao dịch dân sự được xác lập;\nb) Chủ thể tham gia giao dịch dân sự hoàn toàn tự nguyện;\nc) Mục đích và nội dung của giao dịch dân sự không vi phạm điều cấm của luật, không trái đạo đức xã hội.',
    relevanceScore: 0.75,
    retrievalOrigin: 'vector',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx',
    issuedDate: '2015-11-24',
    documentType: 'law',
  },
  {
    id: 'src-5',
    documentId: 'doc-7',
    documentTitle: 'Nghị định 01/2021/NĐ-CP',
    articleNumber: 'Điều 22',
    chunkText: 'Hồ sơ đăng ký doanh nghiệp đối với công ty TNHH hai thành viên trở lên, công ty cổ phần bao gồm:\na) Giấy đề nghị đăng ký doanh nghiệp;\nb) Điều lệ công ty;\nc) Danh sách thành viên đối với công ty TNHH hai thành viên trở lên, danh sách cổ đông sáng lập và cổ đông là nhà đầu tư nước ngoài đối với công ty cổ phần;\nd) Bản sao giấy tờ pháp lý của cá nhân đối với người đại diện theo pháp luật.',
    relevanceScore: 0.72,
    retrievalOrigin: 'bm25',
    sourceUrl: 'https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Nghi-dinh-01-2021-ND-CP-dang-ky-doanh-nghiep-463092.aspx',
    issuedDate: '2021-01-04',
    documentType: 'decree',
  },
]

// ==================== Corpus Status ====================

export const mockCorpusStatus: CorpusStatus = {
  totalDocuments: 1247,
  crawledDocuments: 1198,
  chunkedDocuments: 1156,
  totalChunks: 45678,
  bm25IndexStatus: {
    built: true,
    documentCount: 1156,
    lastUpdated: new Date('2024-01-15T08:30:00'),
    sizeBytes: 156000000,
  },
  vectorIndexStatus: {
    built: true,
    documentCount: 1156,
    lastUpdated: new Date('2024-01-15T09:45:00'),
    sizeBytes: 890000000,
  },
  lastCrawlAt: new Date('2024-01-15T06:00:00'),
  lastIndexAt: new Date('2024-01-15T09:45:00'),
}

// ==================== Pipeline Jobs ====================

export const mockJobs: PipelineJob[] = [
  {
    id: 'job-1',
    type: 'index_vector',
    status: 'completed',
    progress: 100,
    startedAt: new Date('2024-01-15T09:00:00'),
    completedAt: new Date('2024-01-15T09:45:00'),
  },
  {
    id: 'job-2',
    type: 'index_bm25',
    status: 'completed',
    progress: 100,
    startedAt: new Date('2024-01-15T08:00:00'),
    completedAt: new Date('2024-01-15T08:30:00'),
  },
  {
    id: 'job-3',
    type: 'chunk',
    status: 'completed',
    progress: 100,
    startedAt: new Date('2024-01-15T07:00:00'),
    completedAt: new Date('2024-01-15T07:45:00'),
  },
  {
    id: 'job-4',
    type: 'crawl',
    status: 'completed',
    progress: 100,
    startedAt: new Date('2024-01-15T06:00:00'),
    completedAt: new Date('2024-01-15T06:30:00'),
  },
  {
    id: 'job-5',
    type: 'crawl',
    status: 'running',
    progress: 67,
    startedAt: new Date('2024-01-16T10:00:00'),
  },
]
