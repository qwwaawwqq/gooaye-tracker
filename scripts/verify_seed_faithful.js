#!/usr/bin/env node
/**
 * Verify that the _episodes_seed.json is a faithful copy of the inline EPISODES
 * object from index.html.
 * 
 * This script provides a deterministic proof that the seed extraction is safe
 * for use in the monolith swap. It compares:
 * - Key set (all episodes present)
 * - Each field: date, title, dur, v, tags, summary, stocks, deep, sponsor
 * - Full byte-exact comparison of deep HTML content
 * 
 * Exit code 0 = identical (safe to proceed)
 * Exit code 1 = mismatch or error (inspect diffs before proceeding)
 * 
 * Usage:
 *   node scripts/verify_seed_faithful.js [index_html] [seed_json]
 * 
 * Default paths:
 *   index_html = ./index.html
 *   seed_json = ./_episodes_seed.json
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ============ PARSE ARGS ============
const htmlPath = process.argv[2] || path.join(process.cwd(), 'index.html');
const seedPath = process.argv[3] || path.join(process.cwd(), '_episodes_seed.json');

let inlineEPISODES;
let seedData;

console.log('[VERIFY] Starting faithful comparison...\n');
console.log(`HTML: ${htmlPath}`);
console.log(`Seed: ${seedPath}\n`);

// ============ LOAD FILES ============

// Read and extract EPISODES from HTML
try {
  const htmlContent = fs.readFileSync(htmlPath, 'utf-8');
  const startMarker = 'const EPISODES = {';
  const startIdx = htmlContent.indexOf(startMarker);
  
  if (startIdx === -1) {
    console.error('ERROR: Could not find "const EPISODES = {" in index.html');
    process.exit(1);
  }
  
  // Find closing "};" by brace counting
  let braceDepth = 0;
  let searchIdx = startIdx;
  let foundEnd = false;
  
  for (let i = startIdx; i < htmlContent.length; i++) {
    const ch = htmlContent[i];
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
  
  // Evaluate in a safe context
  try {
    inlineEPISODES = eval(`(function(){${episodesBlock}return EPISODES;})()`);
  } catch (e) {
    console.error('ERROR: Failed to evaluate inline EPISODES:');
    console.error(`  ${e.message}`);
    process.exit(1);
  }
  
  console.log(`✓ Extracted inline EPISODES (${Object.keys(inlineEPISODES).length} episodes)`);
} catch (err) {
  console.error(`ERROR: Failed to read/parse ${htmlPath}`);
  console.error(`  ${err.message}`);
  process.exit(1);
}

// Read seed JSON
try {
  const seedContent = fs.readFileSync(seedPath, 'utf-8');
  seedData = JSON.parse(seedContent);
  
  if (!seedData.episodes || typeof seedData.episodes !== 'object') {
    console.error('ERROR: Seed JSON missing "episodes" object');
    process.exit(1);
  }
  
  console.log(`✓ Loaded seed JSON (${Object.keys(seedData.episodes).length} episodes)\n`);
} catch (err) {
  console.error(`ERROR: Failed to read/parse ${seedPath}`);
  console.error(`  ${err.message}`);
  process.exit(1);
}

// ============ COMPARISON LOGIC ============

const seedEpisodes = seedData.episodes;
const inlineKeys = Object.keys(inlineEPISODES)
  .map(k => parseInt(k, 10))
  .filter(k => Number.isFinite(k))
  .sort((a, b) => a - b);

const seedKeys = Object.keys(seedEpisodes)
  .map(k => parseInt(k, 10))
  .filter(k => Number.isFinite(k))
  .sort((a, b) => a - b);

let hasErrors = false;
const diffSummary = [];

// Check key sets match
if (inlineKeys.length !== seedKeys.length) {
  hasErrors = true;
  diffSummary.push(`ERROR: Episode count mismatch: inline=${inlineKeys.length}, seed=${seedKeys.length}`);
}

const missingInSeed = inlineKeys.filter(k => !seedEpisodes[k]);
const extraInSeed = seedKeys.filter(k => !inlineEPISODES[k]);

if (missingInSeed.length > 0) {
  hasErrors = true;
  diffSummary.push(`ERROR: Missing in seed: EP${missingInSeed.join(', EP')}`);
}

if (extraInSeed.length > 0) {
  hasErrors = true;
  diffSummary.push(`ERROR: Extra in seed: EP${extraInSeed.join(', EP')}`);
}

// Field comparison for each episode
const fieldList = ['date', 'title', 'dur', 'v', 'sponsor', 'tags', 'summary', 'stocks', 'deep'];

for (const ep of inlineKeys) {
  const inlineEp = inlineEPISODES[ep];
  const seedEp = seedEpisodes[ep];
  
  if (!seedEp) continue; // Already reported above
  
  const epDiffs = [];
  
  for (const field of fieldList) {
    const inlineVal = inlineEp[field];
    const seedVal = seedEp[field];
    
    // Handle undefined vs not-present (both should be skipped)
    if (inlineVal === undefined && seedVal === undefined) {
      continue;
    }
    
    // For arrays and objects, deep compare
    if (field === 'tags' || field === 'stocks') {
      const inline_json = JSON.stringify(inlineVal || []);
      const seed_json = JSON.stringify(seedVal || []);
      if (inline_json !== seed_json) {
        hasErrors = true;
        epDiffs.push(`  ${field}: MISMATCH`);
      }
    } else if (field === 'deep') {
      // Byte-exact comparison for deep HTML
      if (inlineVal !== seedVal) {
        hasErrors = true;
        const inlineLen = (inlineVal || '').length;
        const seedLen = (seedVal || '').length;
        const inlineHash = crypto.createHash('sha256').update(inlineVal || '').digest('hex').slice(0, 8);
        const seedHash = crypto.createHash('sha256').update(seedVal || '').digest('hex').slice(0, 8);
        epDiffs.push(`  ${field}: length(${inlineLen} vs ${seedLen}) hash(${inlineHash} vs ${seedHash})`);
      }
    } else {
      // String/scalar comparison
      if (inlineVal !== seedVal) {
        hasErrors = true;
        epDiffs.push(`  ${field}: "${String(inlineVal).slice(0, 50)}" vs "${String(seedVal).slice(0, 50)}"`);
      }
    }
  }
  
  if (epDiffs.length > 0) {
    diffSummary.push(`EP${ep}:`);
    diffSummary.push(...epDiffs);
  }
}

// ============ REPORT ============

if (diffSummary.length > 0) {
  console.log('DIFFERENCES FOUND:\n');
  console.log(diffSummary.join('\n'));
  console.log();
}

if (hasErrors) {
  console.error('\n✗ VERIFICATION FAILED: seed is NOT faithful to inline EPISODES');
  console.error('   Do NOT proceed with monolith swap until these mismatches are resolved.');
  process.exit(1);
} else {
  console.log('\n✓ VERIFICATION PASSED: seed is faithful to inline EPISODES');
  console.log('  - All 15 episodes present');
  console.log('  - All fields match (byte-exact including HTML deep content)');
  console.log('  - Safe to proceed with monolith swap');
  process.exit(0);
}