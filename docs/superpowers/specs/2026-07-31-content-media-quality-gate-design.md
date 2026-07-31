# Content and Media Quality Gate Design

## Problem

The current pipeline validates image dimensions, hashes, counts, and file formats, but not editorial uniqueness or visual suitability. This allowed repeated stories, generic retail imagery, repeated frames, and AI-rendered text to reach a WeChat draft.

## Design

1. Daily images must be text-free documentary scenes that directly show smart-cabinet replenishment, stockout inspection, or shelf review.
2. Every image asset carries three review fields: `visual_reviewed`, `text_free`, and `scene_relevant`. Publication is blocked unless all three are true and the reviewed hash still matches the file.
3. Newly generated assets default to unreviewed. A reviewer may approve only after visually opening every file. Replacing a file changes its hash and invalidates reuse.
4. Cover typography is rendered deterministically after image generation. The image model never renders Chinese copy.
5. The generator continues to reject materially similar titles and previously used direct source URLs.

## Acceptance

- A generated image without review flags fails media validation.
- A reviewed, text-free, smart-cabinet image passes.
- Prompts explicitly prohibit all visible text, logos, labels, screens, and synthetic interface effects.
- The July 30 WeChat draft uses one distinct cover plus three distinct smart-cabinet scenes.

