# Model routing and catalog

## Aliases
Applications call aliases. The chart maps each alias to a provider model.

| Alias | Provider model (chart default) | Use |
|---|---|---|
| `aurai-fast` | Claude Haiku | Low-latency drafting, classification, extraction |
| `aurai-balanced` | Claude Sonnet | General reasoning, summarization, tool use |
| `aurai-reasoning` | Claude Opus | Complex multi-step analysis |
| `aurai-gemini-fast` | Gemini Flash | Fallback and cost alternative to `aurai-fast` |
| `aurai-gemini-pro` | Gemini Pro | Fallback and long-context alternative |
| `aurai-openai-mini` | OpenAI small model (disabled by default) | Optional third provider, T0 and T1 only |
| `aurai-local` | Ollama (disabled by default) | Keyless local model, T0 only |
| `aurai-embed` | Ollama embedding model (disabled by default) | Embeddings for `aurai-knowledge-rag` |

Provider model names are in `charts/aurai-gateway/values.yaml` (`litellm.models`). Confirm them against each provider's current model list before deploying; they change often.

## The catalog is the control
`config/model-catalog.yaml` lists every approved model with its permitted risk tiers, data-handling terms and fallback. Tests enforce:

1. The chart serves exactly the catalog's aliases.
2. Chart fallbacks equal catalog fallbacks.
3. A fallback permits every tier its primary permits, so a request never lands on a model that is not approved for its tier.
4. Every team uses only models approved for its tier.

## Changing a model
1. Update the catalog (tiers, terms) and the chart values in one pull request.
2. Run the golden-set evaluations for affected use cases (`aurai-eval-governance`).
3. Merge, deploy, then watch error rate, latency and spend per alias.

## Fallback behavior
Retries (default 2) apply first. If the model still fails, the router tries the alias listed in `fallbacks`. A failed provider is cooled down for `cooldownSeconds` (default 30). Fallbacks need credentials for the fallback provider; without a Gemini key, Claude aliases have no working fallback.

## Using the local model
Run Ollama on your machine, then set `apiBase` for `aurai-local` and `aurai-embed` (on Docker Desktop: `http://host.docker.internal:11434`), set `enabled: true`, and redeploy. This is the only path that works without paid keys.
