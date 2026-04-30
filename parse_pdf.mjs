import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const pdfPath = resolve(process.argv[2] || './glg_portfolio.pdf');
const data = new Uint8Array(readFileSync(pdfPath));
const pdf = await getDocument({
  data,
  standardFontDataUrl: 'file://' + resolve('node_modules/pdfjs-dist/standard_fonts/') + '/'
}).promise;
console.log('Pages:', pdf.numPages);

for (let i = 1; i <= pdf.numPages; i++) {
  const page = await pdf.getPage(i);
  const content = await page.getTextContent();
  const lines = content.items.map(item => item.str).join('');
  console.log(`\n=== PAGE ${i} ===`);
  console.log(lines);
}
