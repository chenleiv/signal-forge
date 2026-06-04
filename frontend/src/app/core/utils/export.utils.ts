export function downloadCsv(headers: string[], rows: string[][], filename: string): void {
  const lines = [headers, ...rows].map(
    row => row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')
  );
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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
