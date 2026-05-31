import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

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

export function downloadPdf(title: string, headers: string[], rows: string[][], filename: string): void {
  const doc = new jsPDF();
  doc.setFontSize(13);
  doc.setTextColor(40);
  doc.text(title, 14, 15);
  doc.setFontSize(8);
  doc.setTextColor(130);
  doc.text(`Generated ${new Date().toLocaleString()}`, 14, 22);
  autoTable(doc, {
    head:       [headers],
    body:       rows,
    startY:     28,
    styles:     { fontSize: 8, cellPadding: 3 },
    headStyles: { fillColor: [30, 37, 53], textColor: [229, 231, 235], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [245, 247, 250] },
  });
  doc.save(filename);
}
