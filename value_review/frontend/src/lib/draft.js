// Draft helpers (step 6): the save-status pill and the view stored with a draft.

const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

// saved: {kind: 'original' | 'version' | 'draft', version, at, auto}. Returns {text, tone}.
export function savePill(dirty, saved) {
  if (dirty) return { text: 'Unsaved changes', tone: 'unsure' };
  if (saved.kind === 'draft') return { text: `${saved.auto ? 'Draft saved automatically' : 'Draft saved'} · ${clock(saved.at)}`, tone: 'accepted' };
  if (saved.kind === 'version') return { text: `Matches v${saved.version}`, tone: 'pending' };
  return { text: 'Original model output', tone: 'pending' };
}

// The view saved with a draft (draft.schema.json "ui"): only known keys, no empty values.
export function uiOf(view, selectedId) {
  const ui = { mode: view.mode };
  if (view.mode === 'record' && view.recordId) ui.record_id = view.recordId;
  if (view.mode === 'value' && view.featureId) ui.feature_id = view.featureId;
  if (selectedId) ui.observation_id = selectedId;
  return ui;
}

export function viewFromUi(ui, view) {
  if (!ui) return view;
  return { ...view, mode: ui.mode || view.mode, recordId: ui.record_id || view.recordId, featureId: ui.feature_id || view.featureId };
}
