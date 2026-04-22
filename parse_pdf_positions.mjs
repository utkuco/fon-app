import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';

const pdfPath = resolve(process.argv[2] || './test.pdf');
const outPath = resolve(process.argv[3] || '/tmp/pdf_items.json');
const data = new Uint8Array(readFileSync(pdfPath));
const pdf = await getDocument({
  data,
  standardFontDataUrl: 'file://' + resolve('node_modules/pdfjs-dist/standard_fonts/') + '/'
}).promise;

console.error('Pages:', pdf.numPages);

const allItems = [];
for (let i = 1; i <= pdf.numPages; i++) {
  const page = await pdf.getPage(i);
  const content = await page.getTextContent();
  for (const item of content.items) {
    const cleanStr = item.str.replace(/[\x00-\x1f\x7f]/g, ' ').trim();
    if (cleanStr) {
      allItems.push({
        p: i,
        s: cleanStr,
        x: Math.round(item.transform[4]),
        y: Math.round(item.transform[5]),
        w: Math.round(item.width || 0),
      });
    }
  }
}

writeFileSync(outPath, JSON.stringify({ pages: pdf.numPages, items: allItems }));
console.error(`Written ${allItems.length} items to ${outPath}`);
