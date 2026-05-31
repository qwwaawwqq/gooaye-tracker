#!/usr/bin/env node
/**
 * Extract STOCKS object from index.html faithfully into _stocks.json
 * 
 * Reads the HTML file, extracts the 'const STOCKS = {...};' block,
 * evaluates it in isolation, and writes the result as JSON.
 * 
 * All 33 stocks are preserved faithfully, including all fields:
 * code, name, mkt, mentions, stance, perf, perfDelta, v, note, eps.
 * 
 * Usage:
 *   node extract_stocks_json.js <input_html> <output_json>
 * 
 * Returns exit code 0 on success, 1 on error.
 */

const fs = require('fs');
const path = require('path');

// Parse arguments
const htmlPath = process.argv[2] || path.join(process.cwd(), 'index.html');
const outputPath = process.argv[3] || path.join(process.cwd(), '_stocks.json');

// Helper: read file
function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    console.error(`ERROR: Cannot read ${filePath}`);
    console.error(`  ${err.message}`);
    process.exit(1);
  }
}

// Read index.html
console.log(`Reading ${htmlPath}...`);
const htmlContent = readFile(htmlPath);

// Find the STOCKS block
const startMarker = 'const STOCKS = {';
const startIdx = htmlContent.indexOf(startMarker);
if (startIdx === -1) {
  console.error(`ERROR: Could not find '${startMarker}' in ${htmlPath}`);
  process.exit(1);
}

// Find the closing "};" by counting braces
let searchIdx = startIdx;
let foundEnd = false;
let braceDepth = 0;

for (let i = startIdx; i < htmlContent.length; i++) {
  const ch = htmlContent[i];
  
  // Count braces to find matching close
  if (ch === '{') braceDepth++;
  else if (ch === '}') {
    braceDepth--;
    if (braceDepth === 0 && i + 1 < htmlContent.length && htmlContent[i + 1] === ';') {
      searchIdx = i + 2;
      foundEnd = true;
      break;
    }
  }
}

if (!foundEnd) {
  console.error('ERROR: Could not find closing "};" for STOCKS object');
  process.exit(1);
}

const stocksBlock = htmlContent.substring(startIdx, searchIdx);
console.log(`✓ Extracted STOCKS block (${stocksBlock.length} bytes)`);

// Evaluate the block in a safe wrapper
let STOCKS;
try {
  const evalCode = `
    (function() {
      ${stocksBlock}
      return STOCKS;
    })()
  `;
  STOCKS = eval(evalCode);
} catch (err) {
  console.error('ERROR: Failed to evaluate STOCKS block');
  console.error(`  ${err.message}`);
  process.exit(1);
}

if (!STOCKS || typeof STOCKS !== 'object') {
  console.error('ERROR: STOCKS is not a valid object');
  process.exit(1);
}

// Validate: check all entries are present
const stockKeys = Object.keys(STOCKS).sort();

console.log(`✓ Found ${stockKeys.length} stocks: ${stockKeys.slice(0, 3).join(', ')}, ..., ${stockKeys.slice(-2).join(', ')}`);

if (stockKeys.length !== 33) {
  console.warn(`  WARNING: Expected 33 stocks but found ${stockKeys.length}`);
}

// Validate structure: check all have required fields
let structureErrors = 0;
for (const code of stockKeys) {
  const stock = STOCKS[code];
  if (!stock.name || !stock.mkt || !Array.isArray(stock.eps)) {
    console.warn(`  WARNING: Stock ${code} missing required fields`);
    structureErrors++;
  }
}

if (structureErrors > 0) {
  console.warn(`  Found ${structureErrors} stocks with missing fields`);
}

// Write output file as JSON
const output = {
  stocks: STOCKS,
  schema: 'stockData-v1',
  entry_count: stockKeys.length,
  codes: stockKeys,
  extracted_at: new Date().toISOString(),
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), 'utf-8');
  console.log(`\n✓ Successfully written to ${outputPath}`);
  console.log(`\nSUMMARY:`);
  console.log(`  Entries: ${stockKeys.length}`);
  console.log(`  Markets: ${new Set(Object.values(STOCKS).map(s => s.mkt)).size}`);
  console.log(`  Total eps references: ${Object.values(STOCKS).reduce((sum, s) => sum + (s.eps ? s.eps.length : 0), 0)}`);
  process.exit(0);
} catch (err) {
  console.error(`\nERROR: Cannot write ${outputPath}`);
  console.error(`  ${err.message}`);
  process.exit(1);
}
