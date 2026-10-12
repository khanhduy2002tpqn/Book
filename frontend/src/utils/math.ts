/**
 * Pre-processes markdown string to normalize LaTeX math delimiters for remark-math.
 * Converts LaTeX display math \[ ... \] to $$ ... $$
 * and LaTeX inline math \( ... \) to $ ... $
 */
export function formatMathMarkdown(content: string): string {
  if (!content) return ''

  return content
    // Convert \[ ... \] display math to $$ ... $$
    .replace(/\\\[([\s\S]*?)\\\]/g, '$$\n$1\n$$')
    // Convert \( ... \) inline math to $ ... $
    .replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$')
}
