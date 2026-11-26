// Sample data of the Settings board (canvas Settings.dc.html) for the parts with no backend yet (ADR-013):
// API keys (PEND-04), models (PEND-04) and the workspace folder (PEND-14).
// Kept in memory: a reload starts again from here.

export const PROVIDERS = [
  { id: 'anthropic', name: 'Anthropic', hint: 'Claude models' },
  { id: 'openai', name: 'OpenAI', hint: 'GPT models' },
  { id: 'google', name: 'Google', hint: 'Gemini models' },
  { id: 'server', name: 'Own server', hint: 'A compatible server, local or from your university' },
];

export const MODELS = [
  { id: 'sonnet', name: 'Claude Sonnet 5.5', note: 'Balanced', provider: 'anthropic', usd: 0.18 },
  { id: 'opus', name: 'Claude Opus 5.5', note: 'Most accurate', provider: 'anthropic', usd: 0.55 },
  { id: 'haiku', name: 'Claude Haiku 5.5', note: 'Fastest and cheapest', provider: 'anthropic', usd: 0.05 },
];

export const KEYS = [
  { id: 'k1', provider: 'anthropic', name: 'Lab account', last: '3F9a', tested: 'Tested 18 Nov 2026', cap: 50, used: 12.4, isDefault: true },
  { id: 'k2', provider: 'anthropic', name: 'Personal', last: '7Kq2', tested: 'Tested 18 Nov 2026', cap: 5, used: 5, isDefault: false },
];

// The two System prompt kinds, with the canvas texts (the prompts themselves are stored by the service, ADR-019).
export const KINDS = {
  ext: { label: 'Extraction', desc: 'Read by the assistant together with the schema of a run: it writes the specific extraction prompt of that run.',
    help: 'Say what every extraction prompt must contain. Do not list fields here: the schema of each run adds them. A change applies to the prompts written from now on; a run keeps the version it used.' },
  norm: { label: 'Normalization', desc: 'Sent to the model with every normalization: it applies the expert’s rule of a feature to a reviewed value.',
    help: 'Say how the model must apply the rules. Do not write rules for a feature here: each feature has its own rule in Normalize. A change applies to the next normalization; a result keeps the version it used.' },
};

export const WORKSPACE = 'C:\\TensileWorkspace\\';
