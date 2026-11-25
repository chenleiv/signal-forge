// A spreadsheet treats a cell that starts with one of these as a formula
// (CSV injection, CWE-1236), even inside quotes. Checked on the first
// character only: see docs/DECISIONS.md for the cases this leaves out.
const FORMULA_START = /^[=+\-@\t\r]/;

/** One CSV cell: a leading apostrophe before a formula character, then quoted. */
export function csvCell(cell: unknown): string {
  const text = String(cell ?? '');
  const safe = FORMULA_START.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function toCsv(headers: string[], rows: string[][]): string {
  return [headers, ...rows].map(row => row.map(csvCell).join(',')).join('\n');
}

/**
 * One Markdown table cell: line breaks become a space (a newline ends the
 * row), and `\ | ` [ ] <` get a backslash, so a value cannot split the
 * table, open a code span, form a link or start an HTML tag.
 */
export function markdownCell(cell: unknown): string {
  return String(cell ?? '')
    .replace(/\r\n|\r|\n/g, ' ')
    .replace(/[\\|`[\]<]/g, '\\$&');
}

export function toMarkdown(title: string, headers: string[], rows: string[][], generatedAt = new Date()): string {
  const line = (cells: string[]) => `| ${cells.map(markdownCell).join(' | ')} |`;
  return [
    `# ${markdownCell(title)}`,
    '',
    `Generated ${generatedAt.toISOString()}`,
    '',
    line(headers),
    `| ${headers.map(() => '---').join(' | ')} |`,
    ...rows.map(line),
    '',
  ].join('\n');
}

/** The JSON export: typed items for machines (a SIEM), not the display rows. */
export interface JsonExport<T> {
  kind: string;
  generated_at: string;
  count: number;
  items: T[];
}

export function toJson<T>(kind: string, items: T[], generatedAt = new Date()): string {
  const doc: JsonExport<T> = { kind, generated_at: generatedAt.toISOString(), count: items.length, items };
  return JSON.stringify(doc, null, 2);
}

function downloadBlob(content: string, type: string, filename: string): void {
  const blob = new Blob([content], { type });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadCsv(headers: string[], rows: string[][], filename: string): void {
  downloadBlob(toCsv(headers, rows), 'text/csv;charset=utf-8;', filename);
}

export function downloadJson<T>(kind: string, items: T[], filename: string): void {
  downloadBlob(toJson(kind, items), 'application/json;charset=utf-8', filename);
}

export function downloadMarkdown(title: string, headers: string[], rows: string[][], filename: string): void {
  downloadBlob(toMarkdown(title, headers, rows), 'text/markdown;charset=utf-8', filename);
}

export async function downloadPdf(title: string, headers: string[], rows: string[][], filename: string): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const doc = new jsPDF();

  const colW   = 42;
  const rowH   = 7;
  const startX = 14;
  let   y      = 14;

  doc.setFontSize(13);
  doc.setTextColor(40);
  doc.text(title, startX, y);
  y += 7;
  doc.setFontSize(8);
  doc.setTextColor(130);
  doc.text(`Generated ${new Date().toLocaleString()}`, startX, y);
  y += 8;

  // Header row
  doc.setFillColor(30, 37, 53);
  doc.rect(startX, y, colW * headers.length, rowH, 'F');
  doc.setTextColor(229, 231, 235);
  doc.setFont('helvetica', 'bold');
  headers.forEach((h, i) => doc.text(h, startX + colW * i + 2, y + 5));
  y += rowH;

  // Data rows
  doc.setFont('helvetica', 'normal');
  rows.forEach((row, ri) => {
    if (y > 270) { doc.addPage(); y = 14; }
    if (ri % 2 === 0) {
      doc.setFillColor(245, 247, 250);
      doc.rect(startX, y, colW * headers.length, rowH, 'F');
    }
    doc.setTextColor(40);
    row.forEach((cell, i) => doc.text(String(cell).slice(0, 20), startX + colW * i + 2, y + 5));
    y += rowH;
  });

  doc.save(filename);
}
