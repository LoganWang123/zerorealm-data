# Scheduled Visual Draft Pipeline Design

## Objective

Run the ZeroRealm content pipeline three times per week and produce a verified website issue plus a complete WeChat draft with one cover and three body images. The automation must never publish, free-publish, or mass-send.

## Data flow

1. Crawl public sources, deduplicate records, run quality checks, and generate the dated MDX report.
2. Use the existing Agnes media service to generate a 900x383 cover and three 1280x720 body images. Validate file presence, PNG format, dimensions, hashes, and asset count.
3. Copy the report and images into `zerorealm-website`, push them, and poll the production report and all four image URLs until they return HTTP 200 and the page contains the expected title and date.
4. Reuse the validated local images, upload the cover as permanent WeChat material, upload body images to the WeChat CDN, render their CDN URLs into the article, and create or update a draft.
5. Read the draft back through `draft/get`. Require the expected title, cover ID, body-image URLs, brand email, website address, and an empty source URL. Any mismatch fails the workflow.

## Safety and recovery

- Scheduled commands use draft mode only and contain neither `--publish` nor `--notify-followers`.
- Missing media, failed production deployment, failed WeChat upload, or failed readback stops the run.
- Generated assets and the publication manifest are restored through GitHub Actions cache so reruns reuse valid files and update the same draft where possible.
- The public footer uses `公开案例征集｜资料纠错｜行业合作`.

## Schedule and configuration

The workflow runs Monday, Wednesday, and Friday at 06:00 Asia/Shanghai (`0 22 * * 0,2,4` UTC). Required GitHub secrets are `DEEPSEEK_API_KEY`, `WEBSITE_REPO_TOKEN`, `AGNES_API_KEY`, `WECHAT_APPID`, and `WECHAT_SECRET`. `AGNES_BASE_URL` and `AGNES_IMAGE_MODEL` are optional overrides with safe defaults.

## Verification

Automated tests assert schedule, step ordering, absence of publish/send flags, draft readback failure behavior, image generation/validation, and WeChat image replacement behavior.
