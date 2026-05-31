#!/usr/bin/env node
/**
 * Extract EPISODES object from index.html faithfully into _episodes_seed.json
 * 
 * Reads the HTML file, extracts the 'const EPISODES = {...};' block,
 * evaluates it in isolation, and writes the result as JSON.
 * 
 * All 15 episodes (EP651-EP665) are preserved faithfully, including the
 * full 'deep' HTML content for episodes that have it (EP651-EP661).
 * Episodes pending transcription (EP662-EP665) have empty 'deep' fields.
 * 
 * Usage:
 *   node extract_episodes_seed.js <input_html> <output_json>
 * 
 * Returns exit code 0 on success, 1 on error.
 */

const fs = require('fs');
const path = require('path');

// Parse arguments
const htmlPath = process.argv[2] || path.join(process.cwd(), 'index.html');
const outputPath = process.argv[3] || path.join(process.cwd(), '_episodes_seed.json');

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

// Find the EPISODES block
const startMarker = 'const EPISODES = {';
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
  console.error('ERROR: Could not find closing "};" for EPISODES object');
  process.exit(1);
}

const episodesBlock = htmlContent.substring(startIdx, searchIdx);
console.log(`✓ Extracted EPISODES block (${episodesBlock.length} bytes)`);

// Evaluate the block in a safe wrapper
let EPISODES;
try {
  const evalCode = `
    (function() {
      ${episodesBlock}
      return EPISODES;
    })()
  `;
  EPISODES = eval(evalCode);
} catch (err) {
  console.error('ERROR: Failed to evaluate EPISODES block');
  console.error(`  ${err.message}`);
  process.exit(1);
}

if (!EPISODES || typeof EPISODES !== 'object') {
  console.error('ERROR: EPISODES is not a valid object');
  process.exit(1);
}

// Validate: check all 15 episodes are present
const episodeKeys = Object.keys(EPISODES)
  .map(k => parseInt(k, 10))
  .sort((a, b) => a - b);

console.log(`✓ Found ${episodeKeys.length} episodes: EP${episodeKeys[0]}–EP${episodeKeys[episodeKeys.length - 1]}`);

if (episodeKeys.length !== 15) {
  console.warn(`  WARNING: Expected 15 episodes but found ${episodeKeys.length}`);
}

// Calculate stats: verify deep content
let withDeep = 0;
let totalDeepChars = 0;

for (const key of episodeKeys) {
  const ep = EPISODES[key];
  if (ep && ep.deep && ep.deep.length > 0) {
    withDeep++;
    totalDeepChars += ep.deep.length;
  }
}

console.log(`✓ Deep content: ${withDeep}/${episodeKeys.length} episodes (${totalDeepChars} chars)`);

// Write output file as JSON
const output = {
  episodes: EPISODES,
  schema: 'episodeData-v1',
  entry_count: episodeKeys.length,
  episode_range: `EP${episodeKeys[0]}-EP${episodeKeys[episodeKeys.length - 1]}`,
  deep_content_count: withDeep,
  total_deep_chars: totalDeepChars,
  extracted_at: new Date().toISOString(),
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), 'utf-8');
  console.log(`\n✓ Successfully written to ${outputPath}`);
  console.log(`\nSUMMARY:`);
  console.log(`  Entries: ${episodeKeys.length}`);
  console.log(`  With deep: ${withDeep}`);
  console.log(`  Total deep chars: ${totalDeepChars}`);
  process.exit(0);
} catch (err) {
  console.error(`\nERROR: Cannot write ${outputPath}`);
  console.error(`  ${err.message}`);
  process.exit(1);
}
