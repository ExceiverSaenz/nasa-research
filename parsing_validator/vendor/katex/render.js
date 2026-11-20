// JSON-lines MathML renderer around the vendored KaTeX (ADR-006).
// stdin : one JSON object per line  {"id": <any>, "source": "<latex>"}
// stdout: one JSON object per line  {"id": <same>, "mathml": "<math>...</math>" | null, "error": "<message>" | null}
// First line written on start-up: {"ready": true, "renderer": "katex@<version>"}
'use strict';
const path = require('path');
const readline = require('readline');
const katex = require(path.join(__dirname, 'katex.min.js'));

function send(obj) { process.stdout.write(JSON.stringify(obj) + '\n'); }

function render(source) {
  try {
    const html = katex.renderToString(source, { output: 'mathml', throwOnError: true, displayMode: true, strict: 'ignore' });
    const start = html.indexOf('<math');
    const end = html.lastIndexOf('</math>');
    if (start < 0 || end < 0) return { mathml: null, error: 'no_mathml_in_output' };
    return { mathml: html.slice(start, end + '</math>'.length), error: null };
  } catch (e) {
    return { mathml: null, error: String(e && e.message ? e.message : e).replace(/^KaTeX parse error:\s*/, '') };
  }
}

send({ ready: true, renderer: 'katex@' + katex.version });
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', (line) => {
  let req;
  try { req = JSON.parse(line); } catch (e) { send({ id: null, mathml: null, error: 'bad_request' }); return; }
  send(Object.assign({ id: req.id }, typeof req.source === 'string' ? render(req.source) : { mathml: null, error: 'bad_request' }));
});
