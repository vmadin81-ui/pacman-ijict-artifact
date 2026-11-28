// Read-only audit: do not reformat or modify historical releases.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { ESLint } from 'eslint';
import * as prettier from 'prettier';

const source = 'versions/pacman_v0.12.2.html';
const html = await readFile(source, 'utf8');
const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
if (!scripts.length) throw new Error('No inline scripts found');
const eslint = new ESLint();
const lint = [];
for (const [index, match] of scripts.entries()) {
    const results = await eslint.lintText(match[1], { filePath: 'game-inline.js' });
    for (const result of results) {
        lint.push({ script: index + 1, errors: result.errorCount, warnings: result.warningCount, messages: result.messages });
    }
}
const options = await prettier.resolveConfig(source);
const formatted = await prettier.check(html, { ...options, parser: 'html' });
const report = { source, lint, prettierCompliant: formatted, formattingPolicy: 'advisory for frozen baseline' };
await mkdir('metrics', { recursive: true });
await writeFile('metrics/quality.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
if (lint.some(item => item.errors > 0)) process.exitCode = 1;
