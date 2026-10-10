---
name: tripo-v2-to-v3-migration
description: >
  Migrate any codebase from the Tripo V2 API (api.tripo3d.ai/v2/openapi or
  api.tripo3d.com/v2/openapi) to the Tripo V3 API (openapi.tripo3d.ai/v3 or
  openapi.tripo3d.com/v3). Use this skill whenever the user asks to migrate,
  upgrade, or fix Tripo API integration code, or when you see V2 endpoints in
  their code. V2 is being shut down; V3 is the replacement.
---

# Tripo API: V2 → V3 Migration Guide

You are migrating code that calls the **Tripo V2 API** (being shut down) to the
**Tripo V3 API**. This document is the authoritative mapping, verified line-by-line
against both server codebases (2026-07). Follow it exactly. Do not invent
endpoints, parameters, or values that are not listed here.

## 0. The big picture

Good news first — the V3 backend was deliberately built to accept V2-shaped
payloads, so this migration is **"change the endpoint, fix a short list of hard
differences"**, not a rewrite:

1. **Your API key keeps working.** The same `tsk_…` keys continue to validate
   on V3; `Authorization: Bearer <key>` is unchanged. (Confirm with the §9
   step-1 balance probe before touching any code.)
2. **Most request fields keep working.** V3 explicitly declares almost every V2
   field name (`model_version`, `file: {type, file_token|url|object}`,
   `original_model_task_id`, `texture`, `pbr`, `prompts`, `animations`, …).
   Unknown extra fields are forwarded, not rejected.
3. **What actually changes:** the URL + endpoint (V2's single `POST /task` with a
   `type` field becomes per-capability V3 endpoints), the response parsing
   (`output.*` keys, `status` enum, timestamps), file upload token names,
   WebSocket watch (gone — poll or use webhooks), image-generation model names,
   and `model_version` becoming **required** for 3D generation.

### Migration procedure (follow in order)

1. **Find V2 usage**: search the codebase for `api.tripo3d.ai`, `api.tripo3d.com`,
   `/v2/openapi`, `tripo3d`. Classify each call site against §2's endpoint table.
2. **Determine region**: `api.tripo3d.ai` → international, base URL becomes
   `https://openapi.tripo3d.ai`; `api.tripo3d.com` → mainland China, becomes
   `https://openapi.tripo3d.com`. Never mix regions; the key only works in its
   own region.
3. **Rewrite each call site** using §2 (endpoints) + §3 (hard differences) +
   §4 (per-type notes).
4. **Rewrite response handling** using §5 (schema changed in specific ways).
5. **Replace WebSocket watch with polling and/or webhooks** using §6.
6. **Run the validation checklist** in §9 before declaring the migration done.

If the code uses something with **no V3 equivalent** (§7), stop and tell the
user instead of guessing.

## 1. Base URL, auth, response envelope

| | V2 (old) | V3 (new) |
|---|---|---|
| Base URL (international) | `https://api.tripo3d.ai/v2/openapi` | `https://openapi.tripo3d.ai/v3` |
| Base URL (China mainland) | `https://api.tripo3d.com/v2/openapi` | `https://openapi.tripo3d.com/v3` |
| Auth header | `Authorization: Bearer <api_key>` | unchanged (same key works) |
| Key management console | platform.tripo3d.ai (deprecated) | `https://developers.tripo3d.ai` (intl) / `https://developers.tripo3d.com` (CN) |
| Success envelope | `{"code": 0, "data": {…}}` | `{"code": 0, "status": "success", "data": {…}}` |
| Error envelope | `{"code": N, "message", "suggestion"}` | `{"code": N, "status": "error", "message", "suggestion", "request_id"}` |
| Request tracing | — | send/read `X-Request-ID` header; response also carries `X-Tripo-Trace-ID` |

`code == 0` still means success — existing success checks keep working.

**Auth-failure detection must change**: V2 returned HTTP 401 with `code: 1002`.
V3 returns HTTP 401 with **`code: 2`** (some deployments may still emit 1002).
→ Detect auth failure by **HTTP status 401**, never by `code == 1002` alone.

## 2. Complete endpoint map

V2 had one creation endpoint (`POST /task`) dispatched by the `type` body field.
V3 has one endpoint per capability and **no `type` field in the body** (remove
it; a leftover `type` field is harmlessly ignored, but remove it anyway).

### Task creation (`POST`, JSON body)

| V2 `type` value | V3 endpoint | Notes |
|---|---|---|
| `text_to_model` | `/v3/generation/text-to-model` | `model_version` now **required** (§3.1) |
| `image_to_model` | `/v3/generation/image-to-model` | `file` object accepted as-is (§3.3) |
| `multiview_to_model` | `/v3/generation/multiview-to-model` | V2 `files` 4-slot array works; **rename `original_task_id` → `original_model_task_id`** (§4) |
| `text_to_image` | `/v3/generation/text-to-image` | new model list + server-side validation (§4) |
| `generate_image` | `/v3/generation/image-to-image` | **model names change** (§3.6) |
| `generate_multiview_image` | `/v3/generation/image-to-multiview` | |
| `edit_multiview_image` | `/v3/generation/edit-multiview` | `original_task_id` + `prompts` unchanged; drop `model_version` |
| `texture_model` | `/v3/models/texture` | default version flipped (§3.2) |
| `refine_model` | `/v3/models/refine` | V3 only accepts `text_to_model` drafts; effectively dead in V2 already |
| `stylize_model` | `/v3/models/stylize` | same 7 styles |
| `convert_model` | `/v3/models/convert` | same formats & options |
| `import_model` | `/v3/models/import` | **input form changes: object → file_token** (§3.4) |
| `animate_prerigcheck` | `/v3/animations/rig-check` | |
| `animate_rig` | `/v3/animations/rig` | version `v2.0-20250506` no longer exists (§3.2) |
| `animate_retarget` | `/v3/animations/retarget` | `animation`/`animations` (≤5) unchanged |
| `mesh_segmentation` | `/v3/mesh/segment` | optional new `v2.0-20260430` version |
| `mesh_completion` | `/v3/mesh/complete` | source must still be a segment task |
| `highpoly_to_lowpoly` | `/v3/mesh/decimate` | version values renamed (§3.2) |
| `classification` | **none — retired** | tell the user (§7) |
| `render_video` | **none — retired** | tell the user (§7) |
| `render_image` | **none — no V3 route** | tell the user (§7) |
| `animate_model` | already dead in V2 (error 2016) | superseded by rig-check → rig → retarget chain |

Creation success response: V2 `{"code":0,"data":{"task_id":"…"}}` →
V3 `{"code":0,"status":"success","data":{"task_id":"…","type":"…","status":"queued"}}`.
Reading only `data.task_id` keeps working.

### Everything else

| V2 | V3 | Notes |
|---|---|---|
| `GET /task/{task_id}` | `GET /v3/tasks/{task_id}` | response schema changes — see §5 |
| `POST /task/batch` `{"task_ids":[…]}` | `POST /v3/tasks/list` `{"task_ids":[…]}` | same request, same `{tasks:{id:detail}, missed:[…]}` response shape, same ≤100 limit |
| `GET /task/watch/:id` (WebSocket) | **gone** | poll `GET /v3/tasks/{id}` + optional webhooks (§6) |
| `GET /task/watch/all[/:since]` (WebSocket) | **gone** | same replacement |
| `POST /upload` (multipart, field `file`) | `POST /v3/files` (multipart, field `file`) | response key renames: `data.image_token` → **`data.file_token`** (§3.5) |
| `POST /upload/sts` (multipart) | `POST /v3/files` | single upload path now |
| `POST /upload/temporary_token` | `POST /v3/files/upload-credentials` | or better: `POST /v3/files/presign` (§3.5) |
| `POST /upload/sts/token` | `POST /v3/files/upload-credentials` | |
| `GET /user/wallet/balance` | `GET /v3/account/balance` | ints → decimals (§3.7) |
| `POST /user/wallet/usage/detail` | `GET /v3/account/usage?limit=&offset=` | CSV-download semantics → paginated JSON rows (§3.7) |

## 3. Hard differences — the things that break if unfixed

### 3.1 `model_version` is now REQUIRED for 3D generation

For `text-to-model`, `image-to-model`, `multiview-to-model`:

- V2: omitted `model_version` fell back to a server default (`v2.5-20250123`).
- V3: omitted `model_version` → HTTP 400, code 1004. **No default.**

The field may be spelled `model_version` (V2 name, still accepted) or `model`
(V3 native name). Allowed values (identical in both regions):

```
v3.1-20260211   v3.0-20250812   v2.5-20250123   P1-20260311
```

Version translation table (apply mechanically):

| V2 code says | Write in V3 | Why |
|---|---|---|
| *(nothing / `"default"`)* | `v2.5-20250123` | preserves V2's default behaviour |
| `v1.3-20240522`, `v1.4-20240625`, `v2.0-20240919`, `Turbo-v1.0-20250506` | `v2.5-20250123` | retired versions (already erroring on V2) |
| `v2.5-20260210` | `v2.5-20250123` | value not in the V3 whitelist |
| `v2.5-20250123`, `v3.0-20250812`, `v3.1-20260211`, `P1-20260311` | unchanged | |

Recommend upgrading to `v3.1-20260211` (best quality) or `P1-20260311`
(low-poly/PBR workflow) to the user, but **default to the behaviour-preserving
value** unless they opt in — outputs and pricing differ between versions.

**P1-20260311 extra rules** (if migrating a P1 call): completely OMIT
`quad`, `smart_low_poly`, `generate_parts`, `geometry_quality` from the payload —
on the international service even an explicit `false` is rejected with 400.
`face_limit`, if present, must be 48–20000 (intl) / 50–20000 (CN).

### 3.2 Version defaults/values that silently changed for processing tasks

| Task | V2 behaviour | V3 behaviour | Migration rule |
|---|---|---|---|
| `texture_model` | default `v2.5-20250123` (options: v2.5, v3.0) | default **`v3.0-20250812`** (same 2 options) | if V2 code omitted the version, add `"model_version": "v2.5-20250123"` to preserve results — or let it upgrade knowingly |
| `animate_rig` | default `v1.0-20240301`; `v2.0-20250506` accepted (intl silently upgraded it to v2.5) | options: `v1.0-20240301` (default), `v2.5-20260210` — **v2.0 rejected** | translate `v2.0-20250506` → `v2.5-20260210` |
| `highpoly_to_lowpoly` → decimate | versions `P-v1.0-20250506` / `P-v2.0-20251225` (both ran as P-v2.0) | versions `v2.0` (default) / `v1.0`; legacy `P-…` values still accepted and normalized | simplest rule: **drop the version field** (default = the engine V2 ran) |
| `mesh_segmentation` | fixed `v1.0-20250506` | `v1.0-20250506` default, `v2.0-20260430` optional | no change needed |

### 3.3 File inputs: what still works, what died

V2's `file` / `files` objects are accepted by V3 **as-is** for these forms:

```jsonc
{"file": {"type": "png", "file_token": "…"}}          // ✔ works (but see token note)
{"file": {"type": "png", "url": "https://…"}}          // ✔ works
{"file": {"object": {"bucket": "…", "key": "…"}}}      // ✔ works
{"file": {"type": "png", "data": "<base64>"}}          // ✖ DEAD — silently treated as empty → 400 "file must specify url, object, or file_token"
```

V3 also offers a simpler native form — a single string field:

```jsonc
{"input": "file_… | https://… | <bare task UUID>"}      // one input
{"inputs": [ … ]}                                        // multiview
```

Rules:

- **base64 (`data`) input must be replaced**: upload the bytes via
  `POST /v3/files` (multipart) first, then pass the returned `file_token`.
  Also, `input: "data:image/png;base64,…"` strings are explicitly rejected (400).
- **Old V2 file tokens do not carry over**: V2 `/upload` returned bare-UUID
  tokens; V3 tokens look like `file_<uuid>`. A bare UUID in the string `input`
  field is interpreted as a *task* reference, not a file; inside a
  `file: {file_token: …}` object it simply fails to resolve. Either way:
  re-upload. In practice V2 tokens were ephemeral (24h) so this only matters if
  tokens are stored. (Encrypted tokens starting with `v2.` — issued by the
  Tripo web app — remain valid on V3.)
- **Task references are bare UUIDs** (e.g. `"0196…"`): same as V2. Never invent
  a `task_` prefix — V3 rejects/misparses it.
- URL inputs required a sibling `type` field in V2; keep it when using the
  `file` object form. The string `input` form does not need it.

### 3.4 `import_model` input form changed completely

- V2 accepted **only** `file: {object: {bucket, key}}` (S3/BOS object refs).
- V3 accepts **only** a `file_token` (from `POST /v3/files`, ≤200 MB multipart —
  or `presign`/`upload-credentials` for bigger files).

Migration: replace the object-ref flow with: upload model file → take
`file_token` → `POST /v3/models/import` with `{"file": {"type": "glb", "file_token": "…"}}`
(or `{"input": "file_…"}`).

### 3.5 Uploads

- `POST /upload` → `POST /v3/files`: still multipart with field name `file`;
  the response key changed `data.image_token` → **`data.file_token`**, and token
  format changed (UUID → `file_<uuid>`). This rename is the #1 silent breakage.
- Image formats: webp/png/jpeg/bmp/tiff (+jpg) — unchanged. Model files now also
  accepted: glb/obj/fbx/stl/3mf/usdz.
- STS flows (`/upload/temporary_token` BOS, `/upload/sts/token` AWS) →
  `POST /v3/files/upload-credentials` (30-min STS creds + `file_token` in one
  response; same region-appropriate storage backend on each side).
  For most code the simpler replacement is **`POST /v3/files/presign`** →
  `{upload_url, file_token, expires_in}` — HTTP PUT the bytes to `upload_url`,
  then use `file_token`. (Treat the URL as valid ~30 min.)
- Upload rate limits are stricter on V3 (~10 uploads/min per client vs 10/s on
  V2). Batch-upload code needs pacing/backoff on 429.

### 3.6 Image-generation model names (`generate_image` → image-to-image, `text_to_image`)

V3 accepts **only friendly aliases**; V2's canonical model names now return 400.
Translation table:

| V2 `model_version` | V3 `model` | Note |
|---|---|---|
| `gpt_4o` | `chat_image_1` | |
| `gpt_image_1.5` | `chat_image_1.5` | |
| `gpt_image_2` | `chat_image_2` | |
| `gemini_2.5_flash_image_preview` | `banana` | |
| `gemini_3_pro_image_preview` | `banana_pro` | |
| `gemini_3.1_flash_image_preview` | `banana2` | |
| `seedream_v4` (CN only in V2) | `seedream_v4` | **text-to-image only** in V3; for image-to-image use `seedream_v5` |
| `seedream_v5` (CN only in V2) | `seedream_v5` | |
| `banana*`, `chat_image_*` (CN V2 aliases) | unchanged | aliases now work in both regions |
| `flux.1_kontext_pro`, `flux.1_dev`, `z_image`, `midjourney` | **no V3 equivalent** | pick a replacement with the user; closest defaults: `seedream_v5` (image-to-image), `seedream_v4` (text-to-image) |
| *(omitted)* | intl V2 defaulted to `flux.1_kontext_pro` (gone), CN V2 to `seedream_v4` | if omitted, V3 defaults to `seedream_v4` (t2i) / `seedream_v5` (i2i) — acceptable; flag the output-style change to the user |

V3 also added strictly-validated optional params: `size` (per-model whitelists,
e.g. `"2K"`/`"1024x1024"`), `aspect_ratio` (**banana-family models only** — 400
on others), `output_format` (`png`/`jpeg`), `watermark` (bool), `template`.
Don't add them during migration unless the V2 code had equivalents in
`parameters`. Prompt limit stays 1800 chars for image generation.

### 3.7 Account endpoints

- Balance: `GET /v3/account/balance` returns `{"balance": 123.45, "frozen": 6.78}` —
  **decimals now, not integers**. Parse as float.
- Usage: V2's `POST /user/wallet/usage/detail` (returned a presigned CSV URL,
  big-customer only) has no direct equivalent. `GET /v3/account/usage?limit=50&offset=0`
  returns JSON rows `{task_id, type, status, created_at, credits_consumed}`
  (limit ≤200). If the code parsed CSVs, it must be rewritten against the JSON.

### 3.8 Misc request-level changes

- `enable_audit` is ignored by V3 (moderation exemption is now an account-level
  entitlement). Remove the field; warn users who relied on disabling moderation.
- `parameters` (generic map) is forwarded to the pipeline on V3 (it was parsed
  but unused on V2). Keep it if present.
- V2's deprecated alias `model` (for model_version) is a non-issue: on V3
  `model` IS the native name. But the deprecated alias `rough_model_task_id`
  does **not** exist on V3 — rename it to `draft_model_task_id` or the refine
  call silently loses its input.
- `X-Tripo-Region` request header (intl V2: selected CDN region for output URLs)
  has no documented V3 effect — remove reliance on it.
- Response header `X-ParallelismLimit-Remain` is V2-only. Do not depend on it.
- Request body limit is 20 MB on both V2 and V3 — and base64 payloads are
  rejected on V3 anyway, so body size stops being a concern after migration.

## 4. Per-type migration notes (only types with non-obvious changes)

**text_to_model / image_to_model / multiview_to_model** — all V2 option fields
keep their names and semantics: `prompt` (≤1024 chars), `negative_prompt`
(≤255), `texture` (default true), `pbr` (default true; true forces texture),
`texture_quality` (`standard`/`detailed`/`extreme`), `geometry_quality`
(`standard`/`detailed`), `face_limit`, `quad`, `smart_low_poly`,
`generate_parts` (requires `texture:false`), `compress` (`"geometry"`),
`return_multiview`, `export_uv`, `image_seed`/`model_seed`/`texture_seed`,
`texture_alignment` (`original_image`/`geometry`), `orientation`
(`default`/`align_image`), `auto_size`, `enable_image_autofix` (V3 also accepts
`image_autofix`), `check_printable` (entitlement-gated), `style_image`.
Multiview: `files` as a 4-slot `[front, left, back, right]` array with `{}`
placeholders still works (front required, ≥2 views). The V2 task-reference mode
(pointing at a `generate_multiview_image`/`edit_multiview_image` task) survives
but **the field name changed**: V2's `original_task_id` is NOT read by this V3
endpoint — rename it to `original_model_task_id` (or send
`{"inputs": [{"task_id": "…"}]}` / `{"input": "<task-uuid>"}`). Also, V2 merged
`files` entries over the referenced task's views; V3 ignores `files` entirely
when a reference is given — if the code relies on "reference + override some
views", that combination has no V3 equivalent: stop and tell the user.

**texture_model** — `original_model_task_id`, `texture_prompt`
(`{text | image | images}` object, images = exactly 4), `texture`/`pbr`,
`texture_quality`, `texture_alignment`, `texture_seed`, `bake`, `part_names`,
`compress`, `return_multiview` all unchanged. Only the default version flipped
(§3.2).

**convert_model** — unchanged: `format` (required; GLTF/USDZ/FBX/OBJ/STL/3MF,
case-insensitive), `texture_format` (BMP/DPX/HDR/JPEG/OPEN_EXR/PNG/TARGA/TIFF/WEBP),
`quad`, `face_limit`, `flatten_bottom(_threshold)`, `texture_size`,
`pivot_to_center_bottom`, `scale_factor`, `force_symmetry`, `bake`, `pack_uv`,
`part_names`, `with_animation`, `assemble_animation`, `animate_in_place`,
`export_vertex_colors` (OBJ/GLTF only), `export_orientation` (+x/-x/+y/-y),
`fbx_preset` (blender/3dsmax/mixamo — **`bake_scale` was removed on V3**; if V2
code sends it, drop the field or pick another preset and tell the user the FBX
export behaviour may change). Non-default options still trigger the "complex
convert" price tier.

**animate_rig** — `original_model_task_id`, `out_format` (glb/fbx), `spec`
(mixamo/tripo), `rig_type` (or legacy `topology`) unchanged. Version: §3.2.

**animate_retarget** — `original_model_task_id` (must be a successful rig task),
`animation` (single) or `animations` (≤5, billed per animation), `out_format`,
`bake_animation`, `export_with_geometry`, `render_video`, `animate_in_place` —
all unchanged.

**stylize_model** — `style` ∈ lego/voxel/voronoi/minecraft/keyring/fridge_magnet/keycap,
`block_size`, `vxc` (entitlement-gated) — unchanged.

**mesh_completion** — `original_model_task_id` (must be a `mesh_segmentation`
task), `part_names` — unchanged.

**highpoly_to_lowpoly → decimate** — `quad`, `face_limit`, `part_names`, `bake`
unchanged (face_limit window 500–20000 tri / 500–10000 quad on the default
engine). Version field: drop it (§3.2).

**text_to_image** — V2 had no model choice (`prompt`, `negative_prompt`,
`style_image`). V3 adds a `model` whitelist (§3.6; default `seedream_v4`) and
optional size/format params. One trap: V2 tolerated a 3D-style `model_version`
(e.g. `v2.5-20250123`) on text_to_image requests — on V3 that value hits the
image-model whitelist and returns 400. **Delete any 3D version value from
text_to_image payloads** (translate it via §3.6 only if it's a real image-model
name). `prompt` remains required. The underlying model differs from V2 — flag
to the user that outputs will look different.

**New V3-only capabilities** (not part of migration, worth mentioning to the
user once done): `POST /v3/generation/image-to-splat` (Gaussian splats),
`POST /v3/mesh/smartsegment` (interactive segmentation), webhooks (§6).

## 5. Response parsing — task detail

`GET /v3/tasks/{task_id}` (and each entry of `POST /v3/tasks/list`). Delta vs V2:

### 5.1 Status enum shrank from 8 to 5

```
V2: queued | running | success | failed | cancelled | banned | expired | unknown
V3: queued | running | success | failed | cancelled
```

- `banned` (moderation rejection) → now `failed` with `error_code: 2008`.
- `expired` (timed out in queue) → now `failed` with `error_code: 2018`.
- Treat any unrecognized status as `failed` (defensive; `unknown` can leak in
  rare edge cases).
- State-machine code that special-cased `banned`/`expired` must move that logic
  to `error_code`.

### 5.2 Output field renames (the most common breakage)

| V2 `output.…` | V3 `output.…` | Note |
|---|---|---|
| `pbr_model` | `model_url` | **all three model keys merge into ONE key**, priority pbr_model > model > base_model |
| `model` | `model_url` | |
| `base_model` | `model_url` | |
| `rendered_image` | `rendered_image_url` | |
| `generated_image` | `generated_image_url` | |
| `rendered_video` | `rendered_video_url` | |
| `rendered_sequence` | `rendered_sequence_url` | |
| `multiview_basecolor` | `multiview_basecolor_url` | |
| `{front,left,back,right}_view_url` (multiview gen) | unchanged | |
| `riggable` (bool) | unchanged | |
| `rig_type` / `topology` | `rig_type` only | `topology` key removed |
| `classification` | *(retired with the task type)* | |

Download URLs are signed and valid ~24 hours in both V2 and V3 — no change.
Download promptly and store; re-query the task to get fresh URLs.

### 5.3 Top-level field changes

| V2 field | V3 field | Note |
|---|---|---|
| `create_time` (unix seconds) | `created_at` (ISO-8601 UTC string) | **type change**; V3 adds `completed_at` |
| `consumed_credit` | `credits_consumed` | renamed |
| `error_code` (failed tasks) | `error_code` | same values; now accompanied by human-readable `error_message` |
| `progress` (0–100) | unchanged | |
| `input` (params echo) | unchanged | |
| `queue_position`, `estimated_running_time`, `running_left_time`, `queuing_num`, `thumbnail`, `previews`, `result`, `prompt` | **all gone** | derive UX from `progress`; thumbnail ≈ `rendered_image_url` |

## 6. Replacing WebSocket watch (V2) with polling + webhooks (V3)

V2's `GET /task/watch/:id`, `/task/watch/all`, `/task/watch/all/:since`
(WebSocket, `{"event":"update|finalized","data":{…}}` frames) have **no V3
equivalent**. Replace with:

**Polling** (always available):

```python
def wait_for_task(task_id, interval=3, timeout=1800):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = get(f"/v3/tasks/{task_id}")["data"]     # cheap; terminal states are cached server-side
        if detail["status"] in ("success", "failed", "cancelled"):
            return detail
        time.sleep(interval)                              # 2–5 s is a good range
    raise TimeoutError(task_id)
```

Poll every 2–5 s (image tasks finish in ~10–60 s, 3D tasks in ~1–10 min).
Polling GETs do not consume creation rate-limit quota.

**Webhooks** (V3-only, replaces `watch/all`): register a URL in the developer
console (developers.tripo3d.ai / .com → Webhooks). Events `task.completed` /
`task.failed` (and `balance.low`) POST an envelope
`{"id": "…", "type": "task.completed", "created_at": "…", "data": {…}}` where
`data` is the task-detail shape (signed output URLs; `error_code`/
`error_message` on failure) — read the task from `payload.data`, not the top
level. Verify the `Tripo-Webhook-Signature` header, format
`t=<unix-seconds>,v1=<hex>` where `v1 = hex(HMAC-SHA256(secret,
"<t>.<raw body>"))` and the secret is the `whsec_…` value shown at
registration (also sent: `Tripo-Webhook-Id`/`-Delivery`/`-Event` headers; see
Appendix C example 3 for verification code). Registration is console-only —
there is no `/v3` API for it.

For V2 `watch/all/:since` catch-up semantics: on reconnect/startup, page
through `GET /v3/account/usage` (has `status` per row) or re-poll known
outstanding task IDs.

## 7. V2 features with NO V3 equivalent — stop and tell the user

| V2 feature | Status | What to tell the user |
|---|---|---|
| `type: classification` | retired | no replacement; remove the feature or keep V2 code until shutdown |
| `type: render_video` | retired | render locally from the model (e.g. three.js/Blender) |
| `type: render_image` | no V3 route | use `rendered_image_url` that 3D generation already returns, or render locally |
| WebSocket watch | removed | §6 |
| Usage CSV export (`usage/detail`) | replaced by JSON | §3.7 |
| `X-Tripo-Region` output-CDN selection | no V3 equivalent | remove |
| Bailian/DashScope provider endpoints (CN, `/provider/bailian/v1/*`) | separate product surface | out of scope for this guide; contact Tripo |
| Task cancel / task list APIs | never existed in V2 either | if code "implements" them it's dead code |

## 8. Error handling

The V3 error-code table is intentionally aligned with V2 — `code` values keep
their meanings (1000/1001 server, 1003 malformed, 1004 bad param, 1007 rate
limit, 2000 concurrency limit, 2001 task not found, 2002–2009 input/audit,
2010 insufficient credit [HTTP 403], 2013 priority, 2015–2017 version errors,
2021/2022 size limits). Differences that matter:

- **Auth failure: match on HTTP 401** (V3 body code is `2`, not 1002 — §1).
- V2 used `code: 2019` for missing object-ref files; V3 reports invalid/expired
  file tokens as `1004`.
- V2 wrapped router errors as `code: 9xxx` (e.g. 9404). V3 uses `4001` for
  unknown routes, and returns `1003` for wrong HTTP method (405) or wrong
  Content-Type (415). Remove any `9xxx` special-casing.
- Rate limits: 1007 = per-minute creation quota (~200 generations/min,
  50 refine/min, 10 uploads/min); 2000 = concurrent-task cap. Both are
  retryable with backoff; 2010 (credit) and 2008 (moderation) are not.
- Failed tasks now carry `error_message` next to `error_code` in task detail —
  surface it to users.

## 9. Validation checklist (run after migrating)

1. `GET {v3_base}/v3/account/balance` with the user's key → expect `code: 0`.
   (Wrong region shows up here as HTTP 401 — try the other base URL, then fix
   the region choice, not the key.)
2. Create one cheap task per migrated type the code uses — e.g. text-to-model
   `{"prompt":"test cube","model_version":"v2.5-20250123","texture":false}` —
   expect `code: 0` + `data.task_id`.
3. Poll it to a terminal state; assert the code reads `output.model_url`
   (not `output.model`/`pbr_model`) and handles `status: failed` +
   `error_code`/`error_message`.
4. Exercise one upload: `POST /v3/files` → assert the code reads
   `data.file_token` (not `image_token`) and passes it through to a creation
   call successfully.
5. Grep the final diff for leftovers: `/v2/openapi`, `api.tripo3d.`,
   `image_token`, `watch/`, `create_time`, `consumed_credit`, `banned`,
   `expired`, `pbr_model`, `base_model`, `rough_model_task_id`. Each hit is
   unfinished work.
6. If the code retries on errors: verify it retries 1007/2000/5xx with backoff
   and does NOT retry 1004/2008/2010.

## 10. Regional differences that survive into V3 (summary)

The V3 API surface is identical in both regions (same endpoints, params, error
codes). What differs: base URL/console URL (§1); output download domains
(CloudFront intl vs Baidu CDN in CN — allowlist accordingly); P1 `face_limit`
lower bound 48 (intl) vs 50 (CN); intl rejects explicit `false` for P1's
forbidden params while CN tolerates it (rule: omit them everywhere, §3.1).
CN-only V2 quirks that are GONE in V3 (nothing to carry over): image-model
friendly-name echo in task detail, `auto_delete_files` behaviour, marketplace
concurrency tiers, `/upload/sts*` being BOS-backed. See Appendix B for the
long version.

---

*Appendices below: A — full per-type parameter tables; B — CN/intl regional
specifics; C — worked Python/JS/curl migration examples. Everything in this
guide was verified against the V2 (Go) and V3 (Java) server sources, 2026-07.
When user code contradicts this document, trust this document; when this
document is silent, test against the live API instead of guessing.*

---

# Appendix A: Per-type parameter reference (V2 → V3)

Full field tables for every migratable task type. Legend for the **V3** column:

- **keep** — same field name, same semantics; send as-is.
- **keep (rename X)** — works, but prefer the canonical V3 name X.
- **translate** — value must be mapped (rule given).
- **drop** — remove from the payload (ignored or harmful on V3).

Fields not listed for a type were ignored by V2 too — drop them.

Common to all creation calls:

| V2 field | V3 | Notes |
|---|---|---|
| `type` | drop | V3 routes by endpoint; body `type` is ignored |
| `model_version` | keep (alias of `model`) | see per-type rules; required for to-model types |
| `model` (deprecated V2 alias) | keep | on V3 this IS the native name |
| `priority` | keep | 1–3; higher tiers gated by account entitlement (error 2013) |
| `parameters` (map) | keep | V2 ignored it; V3 forwards it to the pipeline as extra args |
| `enable_audit` | drop | ignored by V3 (moderation exemption is account-level now) |
| `free_trial`, `free_trial_limit`, `additional_credit`, `user_token`, `price_id` | drop | V2 web-internal billing fields; never valid for API users |

## A.1 text_to_model → POST /v3/generation/text-to-model

| V2 field | V3 | Constraints |
|---|---|---|
| `prompt` | keep | required, 1–1024 chars |
| `negative_prompt` | keep | optional, 1–255 chars |
| `model_version` | **required now** | `v3.1-20260211` / `v3.0-20250812` / `v2.5-20250123` / `P1-20260311`; behaviour-preserving default: `v2.5-20250123` |
| `texture` | keep | default true |
| `pbr` | keep | default true; true forces texture=true |
| `texture_quality` | keep | `standard` / `detailed` / `extreme` |
| `geometry_quality` | keep | `standard` (default) / `detailed`; **omit entirely for P1** |
| `face_limit` | keep | P1: 48–20000 (intl) / 50–20000 (CN) |
| `quad` | keep | **omit for P1**; quad output implies FBX |
| `smart_low_poly` | keep | **omit for P1**; face_limit window 500–20000 tri / 500–10000 quad |
| `generate_parts` | keep | **omit for P1**; requires `texture: false` |
| `compress` | keep | `""` or `"geometry"` |
| `return_multiview`, `export_uv`, `render_sequence`, `render_video` | keep | export_uv default true |
| `image_seed`, `model_seed`, `texture_seed` | keep | |
| `check_printable` | keep | entitlement-gated |
| `style_image` | keep | file object / token / URL |
| `texture_alignment` | drop | V2 ignored user input for this type (server-fixed) |

## A.2 image_to_model → POST /v3/generation/image-to-model

Everything from text_to_model (minus `prompt`/`negative_prompt`/`image_seed`), plus:

| V2 field | V3 | Constraints |
|---|---|---|
| `file` | keep | `{type, file_token}` / `{type, url}` / `{object:{bucket,key}}`; **`{data: base64}` is dead** — upload via /v3/files first |
| `texture_alignment` | keep | `original_image` / `geometry` |
| `orientation` | keep | `default` / `align_image` |
| `auto_size` | keep | |
| `enable_image_autofix` | keep | V3 also accepts `image_autofix` |
| `mode` | keep | pass-through |

Simpler V3-native alternative: `{"input": "<file_token|url|task-uuid>"}`.

## A.3 multiview_to_model → POST /v3/generation/multiview-to-model

Same option fields as image_to_model, plus input modes:

| V2 field | V3 | Constraints |
|---|---|---|
| `files` | keep | exactly 4 slots `[front, left, back, right]`, `{}` placeholders allowed; front required; ≥2 real views |
| `original_task_id` | **translate** | V3's multiview endpoint does NOT read this field name — rename to `original_model_task_id` (or use `{"inputs": [{"task_id": "…"}]}`); still must reference a successful `generate_multiview_image` / `edit_multiview_image` task |
| `original_task_id` + `files` together | **no V3 equivalent** | V2 merged `files` slots over the referenced task's views; V3 ignores `files` when a reference is given — stop and tell the user |
| `orthographic_projection` | keep | |

V3-native alternative: `{"inputs": [{"front": "…"}, {"left": "…"}]}` (view-keyed) or positional array.

## A.4 texture_model → POST /v3/models/texture

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required |
| `model_version` | translate | V2 default was `v2.5-20250123`, V3 default is `v3.0-20250812` → **add explicit `v2.5-20250123` to preserve results** |
| `texture_prompt` | keep | `{text}` or `{image}` or `{images}` (exactly 4, mutually exclusive) |
| `texture` / `pbr` | keep | defaults true/true |
| `texture_quality` | keep | standard/detailed/extreme |
| `texture_alignment` | keep | original_image/geometry |
| `texture_seed`, `compress`, `bake`, `part_names`, `return_multiview`, `asset_map` | keep | |

## A.5 refine_model → POST /v3/models/refine

| V2 field | V3 | Constraints |
|---|---|---|
| `draft_model_task_id` | keep | V3 only accepts `text_to_model` drafts |
| `rough_model_task_id` (deprecated alias) | translate | rename to `draft_model_task_id` |

Note: refine was already effectively unusable on V2 (all eligible source
versions retired). Expect user code that calls it to be dead already; confirm
with the user before porting.

## A.6 stylize_model → POST /v3/models/stylize

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required |
| `style` | keep | lego / voxel / voronoi / minecraft / keyring / fridge_magnet / keycap |
| `block_size` | keep | |
| `vxc` | keep | entitlement-gated |
| `render_image` | keep | preview-render toggle |

## A.7 convert_model → POST /v3/models/convert

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required |
| `format` | keep | required; GLTF/USDZ/FBX/OBJ/STL/3MF (case-insensitive) |
| `texture_format` | keep | BMP/DPX/HDR/JPEG/OPEN_EXR/PNG/TARGA/TIFF/WEBP |
| `quad`, `face_limit`, `flatten_bottom`, `flatten_bottom_threshold`, `texture_size`, `pivot_to_center_bottom`, `scale_factor`, `force_symmetry`, `bake`, `pack_uv`, `part_names`, `with_animation`, `assemble_animation`, `animate_in_place` | keep | any non-default option bills as "complex convert" (same as V2) |
| `export_vertex_colors` | keep | only with format OBJ/GLTF |
| `export_orientation` | keep | `+x` (default) / `-x` / `+y` / `-y` |
| `fbx_preset` | keep, except one value | blender (default) / 3dsmax / mixamo; **`bake_scale` removed on V3** → drop the field or pick another preset and warn the user |

## A.8 import_model → POST /v3/models/import

| V2 field | V3 | Constraints |
|---|---|---|
| `file.object` | **translate** | V3 import accepts only `file_token` — upload via /v3/files (≤200 MB multipart) or presign, then `{"file": {"type": "glb", "file_token": "file_…"}}` |
| `model_version` | drop | V2 force-rewrote it anyway |

## A.9 animate_prerigcheck → POST /v3/animations/rig-check

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required; source task must be success with model output |

Output parsing: `output.riggable` (bool) unchanged; `topology` key → `rig_type`.

## A.10 animate_rig → POST /v3/animations/rig

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required |
| `model_version` | translate | allowed: `v1.0-20240301` (default) / `v2.5-20260210`; **`v2.0-20250506` → `v2.5-20260210`** |
| `out_format` | keep | glb / fbx |
| `spec` | keep | mixamo / tripo |
| `rig_type` (or legacy `topology`) | keep | default biped |

## A.11 animate_retarget → POST /v3/animations/retarget

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | must be a successful `animate_rig` task |
| `animation` / `animations` | keep | at least one; `animations` ≤5, billed per animation |
| `out_format` | keep | glb / fbx |
| `bake_animation`, `export_with_geometry`, `render_video`, `animate_in_place` | keep | |

## A.12 mesh_segmentation → POST /v3/mesh/segment

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | required |
| `model_version` | keep/omit | `v1.0-20250506` (default) / new `v2.0-20260430` |
| — | new optional | `ref_image` (file_token or URL) exists on V3 |

## A.13 mesh_completion → POST /v3/mesh/complete

| V2 field | V3 | Constraints |
|---|---|---|
| `original_model_task_id` | keep | must be a `mesh_segmentation` task |
| `part_names` | keep | |

## A.14 highpoly_to_lowpoly → POST /v3/mesh/decimate

| V2 field | V3 | Constraints |
|---|---|---|
| `model_version` | **translate: drop it** | V3 still accepts the legacy `P-v1.0-20250506`/`P-v2.0-20251225` values (normalized internally), but the clean form is to omit the field — the default `v2.0` is the same engine V2 ran |
| `quad` | keep | |
| `face_limit` | keep | default engine window 500–20000 tri / 500–10000 quad |
| `part_names` | keep | |
| `bake` | keep | V2 defaulted true |

## A.15 text_to_image → POST /v3/generation/text-to-image

| V2 field | V3 | Constraints |
|---|---|---|
| `prompt` | keep | required always (template does NOT waive it on text-to-image); ≤1800 chars on V3 image gen |
| `negative_prompt` | keep | |
| `style_image` | keep | |
| `model_version` | **drop / translate** | V2 tolerated 3D version values here (shared payload builders) — on V3 they fail the image-model whitelist with 400. Delete 3D values; translate real image-model names per §3.6 |
| — | new | `model` (default `seedream_v4`; see §3.6), `size`, `output_format`, `watermark`, `template` |

Output parsing: `output.generated_image` → `output.generated_image_url`.

## A.16 generate_image → POST /v3/generation/image-to-image

| V2 field | V3 | Constraints |
|---|---|---|
| `model_version` | **translate** | alias table in §3.6; canonical gemini_*/gpt_* names now 400 |
| `prompt` | keep | ≤1800 chars; required unless `template` supplies one (same as V2) |
| `file` / `files` | keep | multi-image caps: gpt-family ≤16, banana-family ≤10, seedream ≤4 |
| `template` | keep | V3 validates: `t_pose` / `character_completion` / `3d_enhance` / `variants` / `figure` |
| `t_pose`, `sketch_to_render` | keep | |
| — | new | `size`, `aspect_ratio` (banana-family ONLY), `output_format`, `watermark` |

## A.17 generate_multiview_image → POST /v3/generation/image-to-multiview

| V2 field | V3 | Constraints |
|---|---|---|
| `file` | keep | single image, same forms as image_to_model |

Output parsing unchanged: `output.generate_multiview_image = {front_view_url, left_view_url, back_view_url, right_view_url}`.

## A.18 edit_multiview_image → POST /v3/generation/edit-multiview

| V2 field | V3 | Constraints |
|---|---|---|
| `original_task_id` | keep | must be a successful `generate_multiview_image` task |
| `prompts` | keep | 1–4 items `{view, prompt}`; views unique, ∈ front/left/back/right; prompt ≤1024 chars |
| `model_version` | drop | V2 delegated to generate_image validation; V3 endpoint picks its own model |

---

# Appendix B: Regional notes — China mainland (CN) vs International (intl)

How to tell which region the code targets, what was different on V2, and what
remains different on V3.

## B.1 Region detection

| Signal | Region |
|---|---|
| `api.tripo3d.ai` in code/config | international |
| `api.tripo3d.com` | China mainland |
| Docs/console links to `platform.tripo3d.ai` or `developers.tripo3d.ai` | international |
| `developers.tripo3d.com` | China mainland |
| Payload uses `seedream_v4/v5` or `banana*`/`chat_image_*` model names | was CN V2 (those weren't accepted on intl V2) |
| Code mentions Bailian / DashScope / `/provider/bailian/` | CN-only integration (out of scope — flag to user) |

An API key works in exactly one region. If `GET /v3/account/balance` returns
HTTP 401 on one base URL, try the other before concluding the key is bad.

## B.2 V3 target URLs

| | International | China mainland |
|---|---|---|
| API base | `https://openapi.tripo3d.ai` | `https://openapi.tripo3d.com` |
| Developer console (keys, webhooks, billing) | `https://developers.tripo3d.ai` | `https://developers.tripo3d.com` |
| Output download domain (allowlist in firewalls) | `tripo-data.rg1.data.tripo3d.com` (CloudFront) | `openapi.cdn.tripo3d.com` (Baidu CDN) |

Signed download URLs are valid ~24 h in both regions.

## B.3 V3 behavioural differences (the only ones)

The V3 endpoint set, parameters, response schemas and error codes are identical
in both regions. Verified deltas:

1. **P1 `face_limit` lower bound**: 48 (intl) vs 50 (CN). Use ≥50 for
   region-portable code.
2. **P1 forbidden params**: intl rejects `quad`, `smart_low_poly`,
   `generate_parts`, and `geometry_quality` when *present at all* (even explicit
   `false`/`null`); CN only rejects explicit `true` for the three booleans and
   does not check `geometry_quality` at all. Portable rule: **omit all four keys
   entirely** for P1 requests. SDKs that serialize default values must
   skip-serialize these fields.
3. **Download domains** differ (table above) — relevant for URL rewriting,
   proxies, and CSP/firewall allowlists.
4. Content moderation is active in both regions (same error surface: 2008 on
   input rejection, task `failed` + `error_code: 2008` on output rejection).
   CN has additional compliance pipelines internally; the API contract is the
   same, but rejection rates on borderline content will differ.

## B.4 V2 CN-specific behaviours that are GONE on V3 (do not port them)

| V2 CN quirk | V3 reality |
|---|---|
| `generate_image` accepted friendly aliases (`banana`, `chat_image_1.5`, …) while intl required canonical names | aliases are now the ONLY accepted names, in both regions |
| Task detail echoed the friendly alias back in `input.model_version` (CN) vs canonical (intl) | uniform echo; don't string-match model names across create/query anyway |
| CN default image model `seedream_v4` vs intl `flux.1_kontext_pro` | V3 defaults: `seedream_v4` (text-to-image) / `seedream_v5` (image-to-image), both regions |
| `/upload/sts` + `/upload/sts/token` on CN were silently the BOS (V1) implementations | one upload surface: `/v3/files`, `/v3/files/presign`, `/v3/files/upload-credentials`, region-appropriate storage behind the same contract |
| `s3_host` field in CN STS responses contained a BOS host | `upload-credentials` returns correct fields per region |
| `auto_delete_files` accounts: outputs deleted ~10 min after success | no such mechanism on V3 (if the user relied on auto-cleanup for compliance, tell them it's gone) |
| Marketplace concurrency tier (per-client cap of 3) | standard entitlement-based concurrency |
| URL inputs were trimmed of whitespace on CN only | trim URLs client-side; don't rely on server trimming |
| `priority` upper bound not enforced on CN | keep priority within 1–3 everywhere |
| animate_rig `v2.0-20250506` ran as-requested on CN (intl silently upgraded to v2.5) | v2.0 rejected; use `v2.5-20260210` |
| Bailian/DashScope provider surface (`/provider/bailian/v1/submit\|query`, DashScope envelopes, `X-DashScope-*` headers) | not part of V3 openapi; Bailian users migrate through Alibaba's channel, not this guide |

## B.5 V2 intl-specific behaviours that are GONE on V3

| V2 intl quirk | V3 reality |
|---|---|
| `X-Tripo-Region: rg2` selected Tencent CDN for output URLs | no documented equivalent; remove the header |
| `z_image`, `flux.1_dev`, `flux.1_kontext_pro`, `midjourney` image models | not available; translate per §3.6 |
| Low-balance email alerts (Postmark) configured per account | manage billing alerts in the developer console |
| `thumbnail` fell back to multiview view URLs | `thumbnail` field is gone entirely |

## B.6 Billing notes (both regions)

- Credits are held (`frozen`) at creation, settled on success, refunded on
  failure/cancel/moderation-rejection — same lifecycle as V2.
- Absolute prices differ between versions/models and between regions. Do not
  hardcode credit costs during migration; read `credits_consumed` from task
  detail after completion, and check current pricing on the developer console.
- Insufficient balance: HTTP 403, `code: 2010` — top up in the console
  (Stripe intl / Alipay CN).

---

# Appendix C: Worked migration examples (before / after)

Complete, runnable illustrations of the common patterns. Region: examples use
international URLs — swap `openapi.tripo3d.ai` → `openapi.tripo3d.com` (and
`api.tripo3d.ai` → `api.tripo3d.com` in the "before" halves) for China mainland.

## C.1 curl: text-to-model, create + poll

**Before (V2):**

```bash
curl -s https://api.tripo3d.ai/v2/openapi/task \
  -H "Authorization: Bearer $TRIPO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "text_to_model", "prompt": "a red vintage camera"}'
# → {"code":0,"data":{"task_id":"..."}}

curl -s https://api.tripo3d.ai/v2/openapi/task/$TASK_ID \
  -H "Authorization: Bearer $TRIPO_API_KEY"
# model URL was at .data.output.pbr_model (or .model / .base_model)
```

**After (V3):**

```bash
curl -s https://openapi.tripo3d.ai/v3/generation/text-to-model \
  -H "Authorization: Bearer $TRIPO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a red vintage camera", "model_version": "v2.5-20250123"}'
#      no "type" field; model_version is REQUIRED now
# → {"code":0,"status":"success","data":{"task_id":"...","type":"text_to_model","status":"queued"}}

curl -s https://openapi.tripo3d.ai/v3/tasks/$TASK_ID \
  -H "Authorization: Bearer $TRIPO_API_KEY"
# model URL is at .data.output.model_url (single merged key)
```

## C.2 Python: image-to-model with upload + polling

**Before (V2):**

```python
import requests, time

BASE = "https://api.tripo3d.ai/v2/openapi"
H = {"Authorization": f"Bearer {KEY}"}

# upload
with open("chair.png", "rb") as f:
    r = requests.post(f"{BASE}/upload", headers=H, files={"file": f}).json()
token = r["data"]["image_token"]                      # <- image_token

# create
r = requests.post(f"{BASE}/task", headers=H, json={
    "type": "image_to_model",                          # <- type field
    "file": {"type": "png", "file_token": token},
}).json()
task_id = r["data"]["task_id"]

# poll
while True:
    d = requests.get(f"{BASE}/task/{task_id}", headers=H).json()["data"]
    if d["status"] in ("success", "failed", "banned", "expired", "cancelled"):
        break
    time.sleep(3)
if d["status"] == "success":
    url = d["output"].get("pbr_model") or d["output"].get("model")
elif d["status"] == "banned":
    raise RuntimeError("moderation rejected")
```

**After (V3):**

```python
import requests, time

BASE = "https://openapi.tripo3d.ai/v3"
H = {"Authorization": f"Bearer {KEY}"}

# upload — endpoint and response key change
with open("chair.png", "rb") as f:
    r = requests.post(f"{BASE}/files", headers=H, files={"file": f}).json()
token = r["data"]["file_token"]                       # <- file_token (format: file_<uuid>)

# create — per-capability endpoint, no type field, model_version required
r = requests.post(f"{BASE}/generation/image-to-model", headers=H, json={
    "file": {"type": "png", "file_token": token},      # V2 file object still accepted
    "model_version": "v2.5-20250123",                  # REQUIRED (or upgrade to v3.1-20260211)
}).json()
task_id = r["data"]["task_id"]

# poll — 5-state enum; banned/expired are now failed + error_code
while True:
    d = requests.get(f"{BASE}/tasks/{task_id}", headers=H).json()["data"]
    if d["status"] in ("success", "failed", "can
<truncated 5588 bytes>

NOTE: The output was truncated because it was too long. Use a more targeted query or a smaller range to get the information you need.