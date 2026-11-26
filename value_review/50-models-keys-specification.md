# Specification · API keys and models

**Reference** · Canvas "Extraction Review Tool", board Settings (Models and API keys) and the rule notes Settings 3, 4,
5 and 8; [40-settings-specification.md](40-settings-specification.md). Decisions taken with the user on 2026-11-26
(ADR-020 to ADR-022).

## Objective

An expert adds the API keys of the providers they use, sees that each one works, and chooses which models a run may
use and which is the default, so that Extraction can later call those models with a key that is known to work.

## Scope

- **In scope** · Keys for Anthropic, OpenAI, Google and an own OpenAI-compatible server: add, name, edit, test, make
  default, remove; several keys per provider; a monthly limit per key (stored and shown); the models a key lists and a
  bundled catalog of known models with an estimated cost per paper; ticking models and choosing the default; adding an
  own-server model by name.
- **Out of scope** · Counting spending and blocking a run at its limit, choosing a model and key in a run's Setup, and
  any call that sends a paper to a model (Extraction, PEND-07); prices of OpenAI and Google models (not in the catalog).

## Business rules

- **BR-K01** · A key is stored only after a successful test (the provider listed its models). The service never
  returns a key: it shows the last 4 characters.
- **BR-K02** · A provider may have several named keys; exactly one is its default: the first one added, then the next
  one when the default is removed.
- **BR-K03** · Changing a key's value or the own-server URL tests it again before saving; the old key stays if the
  test fails. The name and the limit are saved without a test.
- **BR-K04** · A model can be ticked only when a key of its provider listed it at its last test (an own-server model
  added by name needs an own-server key). There is one default model among the ticked ones. Removing a key unticks the
  models no remaining key can use, and the default moves to the first ticked model or to none.
- **BR-K05** · The monthly limit is 0 or more dollars, empty for none; spending shows $0.00 until runs record it.
- **BR-K06** · Keys are kept only in `annotations/secrets.json`, written atomically and owner-only where the system
  allows it (0600 on Linux and in Docker), never in exports, `settings.json`, logs or error messages.
- **BR-K07** · The only requests that leave the machine are the key tests, sent to the provider's own address or to
  the own-server URL the user typed (ADR-021).

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-K01 | No keys | GET `/keys`, `/models` | `[]`; the catalog models listed, none usable, with their cost per paper |
| AC-K02 | The provider accepts the key | Save and test | 201 with `last4`, default, models found; the key in no response |
| AC-K03 | The provider answers 401 or 403 | Save and test | 422 `key_rejected` "The provider did not accept this key."; nothing saved |
| AC-K04 | The provider cannot be reached or takes over 15 s | Save and test | 502 `provider_unreachable`; nothing saved |
| AC-K05 | Two keys of a provider | Make the second default; remove it | Exactly one default at every step |
| AC-K06 | No key for a model's provider | Tick it | 400 `model_unavailable` |
| AC-K07 | Models of one provider ticked | Remove its last key | They are unticked; the default moves or is none |
| AC-K08 | An own server | Save with its URL | `<url>/models` called; its models listed; a model can be added by name |
| AC-K09 | Linux or Docker | After a save | `secrets.json` has mode 0600 |
| AC-K10 | Settings page | Add a key, tick models, choose the default | Shown the same in a second browser; the key never comes back to the page |

## Constraints and references

- Python 3.13, the standard library for the requests (no new dependency), a 15 s timeout, no retries.
- Repository context: [51-models-keys-repository-context.md](51-models-keys-repository-context.md). Interface
  contract: [52-models-keys-interface-contract.md](52-models-keys-interface-contract.md).

## Open questions

- OQ-K01 · The cost per paper assumes about 60 000 input and 4 000 output tokens; to be replaced by measured values
  once runs exist.
- OQ-K02 · Which models of a provider's list to show: models that cannot write text (embeddings, speech, images) are
  left out by name; a model wrongly left out can be reported and the list in `service/keys.py` adjusted.
