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
  source: Pick<RetrievedSource, 'documentTitle' | 'articleNumber' | 'clauseNumber' | 'targetArticle'>,
): string {
  const reference = formatLegalReference(source.articleNumber, source.clauseNumber, source.targetArticle)
  if (!reference) return source.documentTitle
  return `${reference}, ${source.documentTitle}`
}