# DeepSeek text model and image provider setup

## 1. Text model

DeepSeek's official API is OpenAI-compatible for text/vision input, but it does **not publish a
text-to-image generation endpoint**. This project uses the official API for text dialogue and a
separate image service for keyframes.

Official references:

- [DeepSeek API quick start](https://api-docs.deepseek.com/)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)

Configuration:

```dotenv
TEXT_MODEL_BASE_URL=https://api.deepseek.com
TEXT_MODEL_NAME=deepseek-flash
TEXT_MODEL_API_KEY=<server-side secret>
TEXT_MODEL_TIMEOUT_SECONDS=60
TEXT_TEMPERATURE=0.7
TEXT_MAX_OUTPUT_TOKENS=900
# Direct, low-latency replies for the HLSF narrative coach.
TEXT_MODEL_THINKING=disabled
```

Notes:

- The application appends `/chat/completions`; do not include that suffix in
  `TEXT_MODEL_BASE_URL`.
- `deepseek-flash` is the current default model in the official docs. The model name is
  configurable; check the current DeepSeek pricing page before changing it.
- `TEXT_MODEL_THINKING=disabled` uses DeepSeek's non-thinking mode. This is appropriate for the
  1–3-sentence HLSF coaching behavior and reduces latency/cost. Set `enabled` only if a more
  deliberate reasoning mode is desired.
- If you switch to a non-DeepSeek OpenAI-compatible text provider that rejects the `thinking`
  field, remove `TEXT_MODEL_THINKING` from the environment.
- DeepSeek Vision accepts images as input; it does not generate keyframe images. Accepting
  visual input must not be confused with text-to-image generation.

## 2. Image model for keyframes — Volcengine Ark / Doubao Seedream

The official DeepSeek API has no public text-to-image endpoint. The current template targets
the separate Volcengine Ark image API with **Doubao Seedream 5.0 pro**. This is a ByteDance/
Volcengine model service, **not** an official DeepSeek image API.

```dotenv
IMAGE_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGE_MODEL_NAME=doubao-seedream-5-0-pro-260628
IMAGE_MODEL_API_KEY=<server-side Volcengine Ark key>
IMAGE_MODEL_SIZE=2K
IMAGE_MODEL_RESPONSE_FORMAT=url
IMAGE_MODEL_WATERMARK=false
IMAGE_MODEL_TIMEOUT_SECONDS=120
IMAGE_MAX_CONCURRENCY=2
IMAGE_JOB_LIMIT_PER_ROUND=3
```

The app appends `/images/generations`, sends the prompt/model/size plus optional
`response_format` and `watermark`, and supports responses containing `data[0].url` or
`data[0].b64_json`. The 2K URL result is downloaded and stored as a private PNG keyframe.
`IMAGE_MODEL_WATERMARK=false` is deliberate: the experiment's image prompt also asks for no
watermark or readable overlay.

References:

- [Volcengine Ark image generation API](https://console.volcengine.com/ark/region:cn-beijing/docs/image-generation-api)
- [Doubao Seedream 5.0 pro/flash tutorial](https://docs.volcengine.com/docs/ark/seedream-5-0-pro?lang=zh)

If you change to a different image provider, its endpoint must accept this request/response
shape. Otherwise the adapter in `backend/app/services/image_queue.py` must be extended rather
than disguised as a working DeepSeek image API. Do not present a third-party image service as
an official DeepSeek API.

## 3. Local demo with real providers

The default local runtime intentionally uses a labelled fake AI stub. To use the real
providers locally:

```bash
cp .env.example .env
# Fill TEXT_MODEL_API_KEY, IMAGE_MODEL_BASE_URL, IMAGE_MODEL_NAME, IMAGE_MODEL_API_KEY, etc.
# Keep ENVIRONMENT=production only for Docker; the local runtime overrides runtime settings.

# Start the local demo with real providers (requires both text and image config).
HLS_PRESERVE=1 HLS_USE_REAL_AI=1 \
  PYTHONPYCACHEPREFIX=$PWD/.pycache \
  backend/.venv/bin/python scripts/dev_runtime.py
```

`HLS_PRESERVE=1` retains the local study data. If you want a fresh demo database, omit it.
Without `HLS_USE_REAL_AI=1`, the runtime will keep using the test stub even when `.env` is
filled.

Before starting the app, you can run a small direct provider check:

```bash
backend/.venv/bin/python scripts/live_ai_smoke.py --text
# The image check spends real image-generation quota:
backend/.venv/bin/python scripts/live_ai_smoke.py --image
```

The scripts read `.env`/server environment, never print keys, and write any test image under
`.local-runtime/live-ai-smoke/`.

## 4. Production

Docker Compose passes `.env` to the API and Caddy. Only Caddy publishes ports 80/443; keys stay
in the API container environment. After deployment:

1. Run the text/image smoke checks from a trusted host or adapt them into the deployment
   verification procedure.
2. Open `/admin`, confirm the readiness checks show both models configured.
3. Complete the required real-model HLSF scenarios before open data collection.
4. Do not open student email login until the protocol and provider checks are complete.

## 5. What is verified in this repository

- Real DeepSeek text smoke: HTTP 200 with `deepseek-flash`.
- Real Volcengine Ark image smoke: HTTP 200 with `doubao-seedream-5-0-pro-260628`, 2K URL result
  downloaded and validated as a 2,496×1,664 PNG.
- Real app-queue image job: 200 enqueue, worker success, authenticated file retrieval,
  verified as a 2,816×1,584 PNG.
- Seven live HLSF scenarios were driven through the app on demo content. Results and the raw
  transcript are in [HLSF_LIVE_TEST.md](HLSF_LIVE_TEST.md).
- Formal reviewed Evidence Packs are still required before drawing educational conclusions or
  retesting evidence-specific scenario 2.
