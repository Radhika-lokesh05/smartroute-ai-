#!/usr/bin/env node
/**
 * scripts/check_bundle_secrets.mjs
 * Post-build security scan of frontend distribution bundle.
 * Detects hardcoded secrets, database credentials, API tokens, and JWTs in client assets.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Resolve frontend/dist directory from repository root or current directory
let distDir = path.resolve(__dirname, "../frontend/dist");
if (!fs.existsSync(distDir)) {
  distDir = path.resolve(__dirname, "./dist");
}
if (!fs.existsSync(distDir)) {
  distDir = path.resolve(process.cwd(), "frontend/dist");
}
if (!fs.existsSync(distDir)) {
  distDir = path.resolve(process.cwd(), "dist");
}

if (!fs.existsSync(distDir)) {
  console.error(`[check_bundle_secrets] ERROR: Built distribution folder not found at: ${distDir}`);
  console.error("Please run 'npm run build' before executing this security check.");
  process.exit(1);
}

const FORBIDDEN_PATTERNS = [
  { name: "Hardcoded JWT Token", regex: /eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}/g },
  { name: "Neon Database Password Prefix (npg_)", regex: /npg_[A-Za-z0-9_]{8,}/gi },
  { name: "PostgreSQL Connection String", regex: /postgres(?:ql)?(?:\+[a-z0-9_]+)?:\/\/[^\s"'<>]+/gi },
  { name: "ORS API Key Variable Name", regex: /\bORS_API_KEY\b/g },
  { name: "RSA / EC Private Key Block", regex: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g },
];

function getFilesRecursively(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...getFilesRecursively(fullPath));
    } else if (entry.isFile() && /\.(js|mjs|cjs|html|css|map)$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}

const files = getFilesRecursively(distDir);
let violations = 0;

console.log(`[check_bundle_secrets] Scanning ${files.length} built client assets in: ${distDir}`);

for (const filePath of files) {
  const content = fs.readFileSync(filePath, "utf-8");
  const relPath = path.relative(process.cwd(), filePath);

  for (const pattern of FORBIDDEN_PATTERNS) {
    const matches = content.match(pattern.regex);
    if (matches && matches.length > 0) {
      console.error(`[check_bundle_secrets] VIOLATION in ${relPath}: Found pattern '${pattern.name}' (${matches.length} occurrences)`);
      violations += matches.length;
    }
  }
}

if (violations > 0) {
  console.error(`\n[check_bundle_secrets] FAILED: Detected ${violations} sensitive secret pattern(s) in built bundle!`);
  process.exit(1);
}

console.log(`[check_bundle_secrets] SUCCESS: All ${files.length} client assets clean. Zero sensitive secrets detected.`);
process.exit(0);
