// The labels of the Settings board (canvas Settings.dc.html): the providers and the two System prompt kinds. Their
// data comes from the service.

export const PROVIDERS = [
  { id: 'anthropic', name: 'Anthropic', hint: 'Claude models' },
  { id: 'openai', name: 'OpenAI', hint: 'GPT models' },
  { id: 'google', name: 'Google', hint: 'Gemini models' },
  { id: 'server', name: 'Own server', hint: 'A compatible server, local or from your university' },
];

// The two System prompt kinds, with the canvas texts (the prompts themselves are stored by the service, ADR-019).
export const KINDS = {
  ext: { label: 'Extraction', desc: 'Read by the assistant together with the schema of a run: it writes the specific extraction prompt of that run.',
    help: 'Say what every extraction prompt must contain. Do not list fields here: the schema of each run adds them. A change applies to the prompts written from now on; a run keeps the version it used.' },
  norm: { label: 'Normalization', desc: 'Sent to the model with every normalization: it applies the expert’s rule of a feature to a reviewed value.',
    help: 'Say how the model must apply the rules. Do not write rules for a feature here: each feature has its own rule in Normalize. A change applies to the next normalization; a result keeps the version it used.' },
};
