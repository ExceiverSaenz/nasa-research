// Sample data of the Settings board (canvas Settings.dc.html) for the parts with no backend yet (ADR-013):
// API keys (PEND-04), models (PEND-04), System prompts (PEND-05) and the workspace folder (PEND-14).
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

const SYS_BASE = 'You write extraction prompts for a tool that reads scientific papers and returns tables of values.\n\nYou are given a schema: groups of fields, each with a name, an optional unit, type, allowed values and description. Write one prompt for another model that will read a paper and fill that schema.';
const SYS_RULES = ['ask for one row per specimen or test condition;', 'list every field of the schema, with its unit and description;',
  'ask for each value exactly as written in the paper, with its symbols (for example 710 ± 25), without converting units or rounding;',
  'ask for the page where each value was found;', 'say to leave a field empty when the paper does not give it, and never to guess;',
  'treat the schema as a guide: if the paper reports something relevant that the schema does not list, say so in a note and do not drop it.'];
const sysText = (k) => `${SYS_BASE}\n\nThe prompt you write must:\n${SYS_RULES.slice(0, k).map((r) => `- ${r}`).join('\n')}${k >= 6 ? '\n\nWrite in plain language. Do not add anything the expert did not ask for.' : ''}`;
const SYSN_BASE = 'You apply a normalization rule, written by an expert, to values that an expert has already reviewed in tensile test papers.\n\nYou are given the feature (name, type, target unit, allowed values), the expert’s rule for each case, the context and the examples, and one reviewed value.';
const SYSN_RULES = ['follow the rule of the case that fits the value, and never invent a rule;',
  'keep the symbols and the uncertainty as the rule says (for example 710 ± 25 becomes the value 710 and the uncertainty 25);',
  'say when you converted a unit, and how;', 'if no case fits, or the value is ambiguous, do not guess: return it unchanged and flag it for the expert;',
  'never change the reviewed value itself.'];
const sysnText = (k) => `${SYSN_BASE}\n\nYour answer must:\n${SYSN_RULES.slice(0, k).map((r) => `- ${r}`).join('\n')}`;

export const SYSTEM_PROMPTS = {
  ext: [
    { n: 3, text: sysText(6), by: 'Expert reviewer', when: '17 Nov 2026', note: 'Added the rule about things the schema does not list', runs: 0 },
    { n: 2, text: sysText(5), by: 'Expert reviewer', when: '12 Nov 2026', note: '', runs: 1 },
    { n: 1, text: sysText(3), by: 'Expert reviewer', when: '3 Nov 2026', note: '', runs: 0 },
  ],
  norm: [
    { n: 2, text: sysnText(5), by: 'Expert reviewer', when: '17 Nov 2026', note: 'Added: flag instead of guessing', runs: 1 },
    { n: 1, text: sysnText(3), by: 'Expert reviewer', when: '14 Nov 2026', note: '', runs: 0 },
  ],
};

export const KINDS = {
  ext: { label: 'Extraction', desc: 'Read by the assistant together with the schema of a run: it writes the specific extraction prompt of that run.',
    help: 'Say what every extraction prompt must contain. Do not list fields here: the schema of each run adds them. A change applies to the prompts written from now on; a run keeps the version it used.' },
  norm: { label: 'Normalization', desc: 'Sent to the model with every normalization: it applies the expert’s rule of a feature to a reviewed value.',
    help: 'Say how the model must apply the rules. Do not write rules for a feature here: each feature has its own rule in Normalize. A change applies to the next normalization; a result keeps the version it used.' },
};

export const WORKSPACE = 'C:\\TensileWorkspace\\';
