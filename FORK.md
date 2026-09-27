# Kairos Power Open WebUI fork

This document records the fork's tracked customizations relative to upstream
Open WebUI **v0.11.4**, to support preserving them during upstream updates.

- Upstream repository: `open-webui/open-webui` (local remote: `upstream`).
- Current comparison baseline: `v0.11.4`, commit
  `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`.
- Reviewed tree: branch `kp_prod_update_v0.11.4` with merge conflicts resolved;
  the merge was still uncommitted at this review.
- The resolved tree differs from v0.11.4 in the same 30 files as the original
  inventory, excluding this document. Findings come from the tree diff and
  source inspection, rather than assuming every historical fork commit still
  represents an active change.

Inspect the current working tree against the new baseline (also works while
the merge is uncommitted):

```sh
git diff --stat v0.11.4 -- . ':!FORK.md'
git diff --name-status v0.11.4 -- . ':!FORK.md'
git diff v0.11.4 -- src backend Dockerfile tailwind.config.js .gitignore
```

The original inventory compared fork commit
`771f75e21f53a411ee718f92dba9412114b165da` with upstream `v0.11.3`
(`2a960a59fe1dbbd35282f0556b3666d81102e781`). Reproduce that snapshot with:

```sh
git diff --stat v0.11.3 771f75e21f53a411ee718f92dba9412114b165da
git diff --name-status v0.11.3 771f75e21f53a411ee718f92dba9412114b165da
git diff v0.11.3 771f75e21f53a411ee718f92dba9412114b165da -- src backend Dockerfile tailwind.config.js .gitignore
```

## Login notice and Microsoft SSO preference

Files: [LoginDisclaimer.svelte](src/lib/components/LoginDisclaimer.svelte) and
[auth/+page.svelte](src/routes/auth/+page.svelte).

The authentication page imports and renders `LoginDisclaimer` above the sign-in
controls. Its **ATTENTION** notice says that logging in consents to monitoring,
interception, recording, searching, and disclosure by Kairos Power and authorized
parties, including government entities. It covers work and personal use, states
there is no reasonable expectation of privacy, and requires compliance with
company policies. It also states that logging in certifies the user has read
"The company policy on LLMs (AI)."

The policy link is `https://tinyurl.com/kpcyberpolicy`, opens in a new tab, and is
bold, underlined, and yellow (`#EDE100`). The notice uses a charcoal background
(`#233539`) and white text. The exact notice text lives in the component; there
is no separate acknowledgment checkbox or recorded acceptance added by this patch.

The Microsoft sign-in button receives custom blue styling (`#12588C`, with
mouseover/mouseout handlers using `#2386C8`/`#12588C`) and medium-weight text.
This is a **visual preference for Microsoft SSO**. It still appears only when
the Microsoft OAuth provider is configured and uses the upstream
`/oauth/microsoft/login` flow. The fork diff does not enforce Microsoft-only
authentication, automatically redirect to Microsoft, or remove other sign-in methods.

## Backend restrictions on Open WebUI API keys

The fork prevents requests authenticated with an **Open WebUI API key** from
using the knowledge/file and filter paths described below. This policy is based
on server-side authentication state, not on client-supplied chat metadata.
Browser/session JWT authentication is not classified as API-key authentication,
even when a client calls the same HTTP endpoints directly.

| File | Custom behavior |
| --- | --- |
| [utils/api_policy.py](backend/open_webui/utils/api_policy.py) | Adds `is_api_key_request` and `check_api_key_path`. |
| [utils/auth.py](backend/open_webui/utils/auth.py) | Applies the path restriction during `get_current_user_by_api_key` and sets `request.state.auth_type = 'api_key'` after successful authentication. |
| [main.py](backend/open_webui/main.py) | Rejects explicit attachments at the start of `chat_completion`. |
| [utils/middleware.py](backend/open_webui/utils/middleware.py) | Suppresses knowledge injection, built-in tools, file retrieval, and outlet filters for API-key requests; adds an inlet-pipeline eligibility check. |
| [utils/filter.py](backend/open_webui/utils/filter.py) | Skips filter resolution and execution for API-key requests. |
| [routers/pipelines.py](backend/open_webui/routers/pipelines.py) | Skips pipeline inlet and outlet filters for API-key requests. |

### Restricted routes

API-key authentication returns HTTP 403 for each of these paths and its
subpaths (exact match or prefix followed by `/`):

- `/api/v1/knowledge`
- `/api/v1/retrieval`
- `/api/v1/files`
- `/api/v1/functions`
- `/api/v1/pipelines`

The error detail is `Knowledge, files, and filters are not available with API keys.`
This check is independent of the configurable API-key endpoint allowlist and
has no admin exemption. It runs in authentication, so it also applies when an
API key reaches that authentication path through a supported transport other
than the Authorization header.

### Chat attachments and implicit knowledge

For both `/api/chat/completions` and `/api/v1/chat/completions`, an API-key
request with a truthy `files` or `folder_id` value in any of the following
dictionaries receives HTTP 403:

- The top-level request body.
- `metadata`.
- `user_message`.
- `parent_message`.

The error detail is `Knowledge and file attachments are not available with API keys.`
These explicit attachments are **rejected**, rather than silently stripped.

The middleware separately prevents implicit enrichment for API-key requests:

- Folder/project files are not added to legacy RAG input or native-tool folder
  knowledge metadata.
- Model-attached knowledge is treated as an empty list.
- Internal note-chat files are not added.
- `chat_completion_files_handler` returns the body with an empty sources list
  without running file retrieval.
- `use_builtin_tools` is false, disabling the built-in tool set, including its
  native knowledge access, even if the caller supplies a `session_id`.

These guards control Open WebUI's enrichment paths. They do not redact text
already supplied in `messages`, and they do not add a blanket prohibition on
caller-supplied tools or all other upstream features.

### Filter execution

- `resolve_filter_pipeline` returns empty filter lists for API-key requests,
  covering global, model-attached, and request-selected filters.
- `process_filter_functions` returns the form data and empty flags without
  invoking inlet, stream, or outlet filter functions.
- `process_pipeline_inlet_filter` and `process_pipeline_outlet_filter` return
  the payload unchanged.
- `outlet_filter_handler` returns immediately.
- Independently, `should_process_chat_filters` requires truthy `chat_id`,
  `session_id`, and `message_id` before the pipeline inlet runs in
  `process_chat_payload`. This eligibility rule also affects non-API-key
  requests without all three values. The authentication-based guards still
  block API-key filters when all three values are present.

Preserve all of these enforcement points when upstream moves chat processing
between handlers. Omitting metadata alone is not the policy boundary.

## Permanent Docs sidebar entry

File: [Sidebar.svelte](src/lib/components/layout/Sidebar.svelte).

The sidebar prepends a **Docs** item linking to `/docs`, independently of the
user's saved pinned menu items. It filters duplicate `docs` entries from saved
pins, always considers Docs visible, uses the Notes icon, and includes the entry
in both sidebar layouts. Upstream Notes remains a separate item.

Docs cannot be dragged, and other items cannot be moved ahead of it. Reordering
uses `newDraggableIndex` so saved pin order excludes the fixed Docs entry.
Navigation forces a full page load through `window.location.assign` in the
compact layout and `data-sveltekit-reload` in the expanded layout.

The fork adds the link, but no custom `/docs` page. Upstream FastAPI exposes
`/docs` only when `ENV == 'dev'`; the Dockerfile sets `ENV=prod`. Verify the
deployed destination or proxy routing separately when upgrading.

## Fonts and Kairos assets

[tailwind.config.js](tailwind.config.js) extends the Tailwind font stacks:

- Sans serif starts with `Segoe UI`, then `Arial`, followed by system and emoji
  fallbacks.
- Monospace starts with `Consolas`, then `Lucida Console`, followed by platform
  monospace fallbacks.

Four added image assets are tracked under `static/static/`:

- [KAIROS.png](static/static/KAIROS.png)
- [KAIROS-lite.png](static/static/KAIROS-lite.png)
- [KAIROS_wide.png](static/static/KAIROS_wide.png)
- [KAIROS_wide-lite.png](static/static/KAIROS_wide-lite.png)

No tracked application source references these filenames at this snapshot.
Their presence is a fork customization; any deployment-specific selection or
installation of them is outside this source diff.

## KP Bedrock knowledge-base helpers

The fork adds three modules under `backend/kp/`. They provide a reusable filter
base and helpers for retrieving Bedrock knowledge-base content, sharing results
across filters, and adding downloadable source citations.

| File | Purpose and configuration |
| --- | --- |
| [kb_base_filter.py](backend/kp/kb_base_filter.py) | `KbBaseFilter.inlet` retrieves context for the latest user message and inserts an assistant context message before it, replacing an immediately preceding generated context block when recognized. Its outlet delegates citation output to the last KB filter in the Redis roster. |
| [knowledge_base.py](backend/kp/knowledge_base.py) | Calls `bedrock-agent-runtime.retrieve`, retains KP document metadata, deduplicates text when formatting context, and instructs the model to cite numbered passages. Adds a Sources section for cited hits with presigned S3 downloads. |
| [redis_handler.py](backend/kp/redis_handler.py) | Pools Redis connections, stores a roster and per-KB results under `kalypso:{chat_id}`, merges results in descending score/title order, delegates final output, and clears the chat's retrieval keys after citation processing. |

The base filter's valves default to `TOP_K=9`, `MAX_CONTEXT_CHARS=32000`,
`HYBRID=False`, and `AWS_REGION=us-gov-west-1`. `KB_ID` comes from `MAIN_KB_ID`
with a hard-coded development fallback (`D3Q2K57HXU`). The filter metadata
declares `aiobotocore==3.1.0`; that requirement is not added to the root backend
dependency lists. Redis uses `REDIS_URL`, database 0 by default, and shared
pools with connection/time limits, health checks, and retry configuration.

Source download URLs expire after 300 seconds by default and request
`Cache-Control: no-store, private` plus attachment disposition. `.yml` sources
are offered as `.txt` with a plain-text content type; the default content type
is PDF. The citation helper separately defaults to `us-gov-west-1`; the base
filter does not pass its `AWS_REGION` valve to that helper.

No tracked code outside these modules imports or registers `KbBaseFilter`.
Actual filter wrappers, activation, valves, AWS credentials/permissions, and
deployed knowledge bases therefore need to be checked in deployment/runtime
configuration. When invoked through Open WebUI's filter machinery, these
helpers are subject to the API-key filter bypass described above.

## Build and development changes

- [Dockerfile](Dockerfile) sets
  `NODE_OPTIONS="--max-old-space-size=8192"` in the frontend build stage before
  `npm run build`. Preserve this 8 GiB Node heap allowance for the image build;
  this patch does not set the backend runtime's memory limit.
- [.gitignore](.gitignore) adds `.kiro` to ignore local editor/tool artifacts.

## Historical telemetry artifacts

The remaining 11 added files are reports and tests from earlier OpenTelemetry
user-metrics work:

- [ASYNCPG_EVENT_LOOP_ISSUE.md](backend/ASYNCPG_EVENT_LOOP_ISSUE.md)
- [TASK_3.3_VERIFICATION_RESULTS.md](backend/TASK_3.3_VERIFICATION_RESULTS.md)
- [TASK_4_FINAL_TEST_SUMMARY.md](backend/TASK_4_FINAL_TEST_SUMMARY.md)
- [test_metrics_callbacks.py](backend/open_webui/test/util/test_metrics_callbacks.py)
- [test_metrics_preservation.py](backend/open_webui/test/util/test_metrics_preservation.py)
- [test_bug_exploration.py](backend/test_bug_exploration.py)
- [test_bug_simple.py](backend/test_bug_simple.py)
- [test_fix_simple.py](backend/test_fix_simple.py)
- [test_fix_verification.py](backend/test_fix_verification.py)
- [test_preservation_standalone.py](backend/test_preservation_standalone.py)
- [test_preservation_verification.py](backend/test_preservation_verification.py)

The runtime [telemetry/metrics.py](backend/open_webui/utils/telemetry/metrics.py)
is **identical to upstream v0.11.4**, as it was to v0.11.3 at the original
inventory. It uses synchronous database queries and
callbacks defined inside `setup_metrics(app, resource, db_engine)`. The old
reports describe event-loop bridging or zero-valued callbacks, while tests
reference older callback names, module-level callbacks, or a two-argument
`setup_metrics`. Those assumptions do not describe the current implementation.
Treat the files as historical artifacts to review separately, not evidence that
the current branch passed telemetry tests or a runtime patch to reapply.

Likewise, the historical fork change to suppress the ` (Open WebUI)` name suffix
is absent from the current diff: [env.py](backend/open_webui/env.py) matches
upstream v0.11.4 and retains upstream name handling.

## v0.11.4 merge conflict resolutions

- The Dockerfile retains the fork's 8192 MiB Node heap allowance alongside
  upstream's slim-image source-map cleanup and backend ownership preparation.
  Source maps are deleted only after `npm run build` succeeds, so that cleanup
  does not address a heap OOM during the build. A successful build in the target
  build environment is still needed to verify memory sufficiency.
- The sidebar retains the fixed Docs link to `/docs` and its full-page
  navigation. Menu labels, including Docs, use upstream's `$i18n.t(...)` pattern;
  the other upstream sidebar changes are accepted.

### Verification status

Source comparison confirms that all 30 inventory paths remain in the fork diff.
The added/removed lines of the backend API-key policy patches are unchanged
relative to the new upstream baseline. The only adapted customization is the
translated Docs label. This confirms preservation of the source edits;
compatibility with changed upstream behavior still requires runtime checks.

No unresolved Git conflicts remain. Whitespace checks and shell syntax checks
for the resolved Dockerfile build/ownership commands passed. A full frontend
or Docker build and the UI/API checks below have not been run; frontend
dependencies were not installed locally during this review.

## Preservation checks for the v0.11.4 update

These checks remain to be performed before considering the upgrade validated:

- Confirm the notice text and policy link remain visible on the login page,
  and configured Microsoft SSO retains its styling and working redirect.
- With valid user and admin API keys, confirm restricted route families return
  403 even when the configurable endpoint allowlist would otherwise permit them.
- Exercise both chat completion aliases with `files` and `folder_id` in each
  checked location; confirm 403 for nonempty values.
- Confirm plain API-key completions still work, while model/folder/note
  knowledge, built-in tools, and global/model/selected filters are skipped.
  Include streaming and non-streaming requests, native and legacy function
  calling, and API-key requests supplying all three chat identifiers.
- Confirm normal authenticated UI chats retain authorized knowledge retrieval
  and filter execution, including KP retrieval and citation downloads when
  those filters are configured.
- Verify Docs remains first, unique, and fixed in both sidebar layouts; other
  pins still reorder correctly, and `/docs` resolves in the deployment.
- Check fonts and deployed logo usage, and build the image with the retained
  Node heap allowance.
- Review the obsolete telemetry tests separately before treating their results
  as upgrade validation. Record the final merge commit and build/runtime
  verification results here when the upgrade is complete.
