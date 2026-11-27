// Whether a value fits its schema field (BR-R06). Mirrors value_review/domain/review_schema.py `fit`: a number field only
// asks for a digit (values are never parsed, BR-05); a category with allowed values takes only those, case-insensitive.

const SPLIT = /\s*[;,]\s*/;

export function fit(field, value) {
  const text = (value || '').trim();
  if (!field || !text) return [];
  if (field.type === 'number' && !/\d/.test(text)) return ['not_a_number'];
  if (field.type === 'category' && field.allowed && field.allowed.length) {
    const allowed = new Set(field.allowed.map((a) => a.trim().toLowerCase()));
    const parts = field.multiple ? text.split(SPLIT).filter(Boolean) : [text];
    if (parts.some((p) => !allowed.has(p.toLowerCase()))) return ['not_allowed'];
  }
  return [];
}

export const WARNING_TEXT = {
  not_a_number: 'This field is a number, and the value has no digits.',
  not_allowed: 'Not one of the allowed values for this field.',
};

// Readable reasons for the codes the service adds to "Check this" (BR-R04).
export const CHECK_TEXT = {
  'evidence:quote_not_found': 'The quoted text was not found in the PDF, so this value has no highlight.',
  'field:not_in_schema': 'This field is not in the schema. Move the value to a column, or reject it.',
  'field:not_allowed': 'Not one of the allowed values for this field.',
  'field:not_a_number': 'This field is a number, and the value has no digits.',
};
