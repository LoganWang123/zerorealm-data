# Antigravity role: independent test, acceptance, and generative images

This file is for Antigravity. It does **not** replace any existing `AGENTS.md` or repository
agent rules. When those exist, follow them for repository rules, and use this file for
Antigravity duties.

## Duties

- Act as the independent test and acceptance agent for `zerorealm-data`.
- Do not edit, create, delete, format, or repair source or configuration files during acceptance
  runs, except normal dependency and test/build artifacts.
- Start from a clean project snapshot, install locked dependencies, run relevant checks, report
  evidence, and end with exactly one of: `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: BLOCKED`.
- Preferred acceptance model: `gemini-3.6-flash-medium`.

## Generative images

- Own all bitmap image generation and editing via the built-in generative image tool.
- Accept image briefs, target asset paths, and integration notes prepared by Cursor.
- Write generated or edited bitmap assets to the agreed paths so Cursor can wire them in code.
