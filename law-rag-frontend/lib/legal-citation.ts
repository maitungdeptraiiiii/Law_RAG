import type { RetrievedSource } from './types'

function normalizePart(value?: string): string | null {
  if (!value) return null
  const normalized = value.trim().replace(/\s+/g, ' ')
  return normalized || null
}

function ensurePrefix(value: string, prefix: string, pattern: RegExp): string {
  return pattern.test(value) ? value : `${prefix} ${value}`
}

export function formatLegalReference(
  articleNumber?: string,
  clauseNumber?: string,
  targetArticle?: string,
): string | null {
  const article = normalizePart(articleNumber)
  const clause = normalizePart(clauseNumber)
  const target = normalizePart(targetArticle)
  const segments: string[] = []

  if (clause) {
    segments.push(ensurePrefix(clause, 'Khoản', /^khoản\b/i))
  }

  if (article) {
    segments.push(ensurePrefix(article, 'Điều', /^điều\b/i))
  }

  if (target) {
    segments.push(`(sửa đổi ${ensurePrefix(target, 'Điều', /^điều\b/i)})`)
  }

  return segments.length > 0 ? segments.join(' ') : null
}

export function formatSourceCitation(
  source: Pick<
    RetrievedSource,
    'documentId' | 'documentTitle' | 'documentNumber' | 'articleNumber' | 'clauseNumber' | 'targetArticle' | 'documentType'
  >,
): string {
  const reference = formatLegalReference(source.articleNumber, source.clauseNumber, source.targetArticle)
  const label = sourceDocumentLabel(source)
  if (!reference) return label
  return `${reference}, ${label}`
}

export function sourceShortReference(
  source: Pick<RetrievedSource, 'documentId' | 'documentTitle' | 'documentNumber' | 'articleNumber' | 'clauseNumber' | 'targetArticle'>,
): string | null {
  const reference = formatLegalReference(source.articleNumber, source.clauseNumber, source.targetArticle)
  const number = cleanedDocumentNumber(source)

  if (reference && number) return `${reference} - ${number}`
  return reference || number
}

function isTechnicalId(value?: string): boolean {
  if (!value) return true
  return /^\d+$/.test(value.trim())
}

function looksLikeSlugTitle(value?: string): boolean {
  if (!value) return true
  const text = value.trim()
  if (!text) return true
  if (/^kh[oô]ng r[oõ] v[aă]n b[aả]n$/i.test(text)) return true

  const words = text.split(/\s+/)
  const shortConsonantWords = words.filter((word) => /^[bcdfghjklmnpqrstvwxyz]{1,3}$/i.test(word))
  const hasBrokenVietnameseMarkers = /\b(?:N Cp|Ngh Nh|Th Ng T|Quy Nh|I U|Ch Nh|Giao Th Ng|Ng B)\b/i.test(text)
  const hasVeryManySingleLetters = words.filter((word) => /^[A-Z]$/i.test(word)).length >= 4
  const hasFileSlugShape = /[_/\\]/.test(text) || /\b(?:N_|N-|-CP|_CP|Ngh_nh|Th_ng|Quy_nh)\b/i.test(text)

  return hasFileSlugShape || hasBrokenVietnameseMarkers || hasVeryManySingleLetters || shortConsonantWords.length >= 5
}

function documentTypePrefix(type?: string): string {
  const labels: Record<string, string> = {
    law: 'Luật',
    decree: 'Nghị định',
    circular: 'Thông tư',
    resolution: 'Nghị quyết',
    decision: 'Quyết định',
    guideline: 'Hướng dẫn',
  }
  return labels[type || ''] || 'Văn bản'
}

function extractNumberFromSlug(value?: string): string | null {
  if (!value) return null
  const slug = value.replace(/\.[a-z0-9]+$/i, '').replace(/[\\/]+/g, '_')

  const yearMatch = slug.match(/(?:^|_)(\d{1,4})[_-](\d{4})[_-]([A-Za-zĐÐ]+)[_-]*([A-Za-zĐÐ]+)?(?:_|-|$)/i)
  if (yearMatch) {
    const [, number, year, rawCode, rawSuffix] = yearMatch
    const code = rawCode.toUpperCase()
    const suffix = (rawSuffix || '').toUpperCase()
    if (code === 'N' && suffix === 'CP') return `${number}/${year}/NĐ-CP`
    if (suffix) return `${number}/${year}/${code}-${suffix}`
    return `${number}/${year}/${code}`
  }

  const oldStyleMatch = slug.match(/(?:^|_)(\d{1,4})[-_ ]([A-Za-z]{1,8})[-_\/ ]([A-Za-z]{2,10})(?:_|-|$)/i)
  if (oldStyleMatch) {
    const [, number, code, suffix] = oldStyleMatch
    return `${number}-${code.toUpperCase()}/${suffix.toUpperCase()}`
  }

  return null
}

function cleanedDocumentNumber(source: Pick<RetrievedSource, 'documentId' | 'documentTitle' | 'documentNumber'>): string | null {
  const number = normalizePart(source.documentNumber)
  if (number && !isTechnicalId(number) && !looksLikeSlugTitle(number)) return number

  return (
    extractNumberFromSlug(source.documentTitle)
    || extractNumberFromSlug(source.documentNumber)
    || extractNumberFromSlug(source.documentId)
  )
}

export function sourceDocumentLabel(
  source: Pick<RetrievedSource, 'documentId' | 'documentTitle' | 'documentNumber' | 'documentType'>,
): string {
  const title = normalizePart(source.documentTitle)
  const number = cleanedDocumentNumber(source)

  if (title && !isTechnicalId(title) && !looksLikeSlugTitle(title)) return title
  if (number && !isTechnicalId(number)) return `${documentTypePrefix(source.documentType)} ${number}`

  const id = normalizePart(source.documentId)
  if (id && !looksLikeSlugTitle(id)) return `${documentTypePrefix(source.documentType)} ${id}`

  return documentTypePrefix(source.documentType)
}
