# Design System & Maintenance Guide

The profile at [`README.md`](README.md) is a generated document. This file records the
design tokens it is built from and the rules for changing it safely.

---

## 1. Visual theme & atmosphere

**Tokyo Night** — a deep indigo-black ground with cool blue and violet accents.
The mood is *calm, technical and dense*: information-rich but never loud. Colour is
used to encode meaning (a stage in a pipeline, a category of tool), never as decoration.

Three rules hold the page together:

1. **One accent per meaning.** Blue is identity and structure, violet is intelligence
   and AI, green is outcome and verification, orange is attention and achievement.
2. **Gradients only at boundaries.** The waving header, the footer, and the 2px section
   rules. Never inside a content block.
3. **Every section opens the same way** — a gradient rule, then an emoji-prefixed H2.
   Repetition is what makes a long page feel designed rather than assembled.

---

## 2. Colour palette & roles

| Token | Hex | Role |
| :--- | :--- | :--- |
| **Void Indigo** | `#1A1B27` | Page ground. Every card background matches it so images sit flush against GitHub's dark canvas. |
| **Slate Panel** | `#24283B` | Raised surfaces — badge bodies, diagram nodes, stage cards. |
| **Muted Steel** | `#414868` | Hairlines, borders, inactive rails. |
| **Pale Periwinkle** | `#C0CAF5` | Primary body text on dark ground. |
| **Dim Slate** | `#565F89` | Secondary and caption text. Deliberately low contrast — it should recede. |
| **Signal Blue** | `#7AA2F7` | Primary accent. Identity, headings, links, structural edges. |
| **Electric Violet** | `#BB9AF7` | Secondary accent. Reserved for AI, ML and agentic concepts. |
| **Ice Cyan** | `#7DCFFF` | Tertiary accent. Data ingress, inputs, the leading edge of a gradient. |
| **Circuit Green** | `#9ECE6A` | Success and terminal state. The grounded decision, verified credentials. |
| **Amber Signal** | `#E0AF68` | Attention. Reasoning steps, follower counts, trophies. |
| **Coral Alert** | `#F7768E` | Emphasis and human contact. Email, the streak flame. |

The literal values live in `profile.config.json` under `theme` and are consumed by
`scripts/sync_profile.py`. **Change them there, not in the README** — every generated
badge reads from that object.

---

## 3. Typography

Third-party card services own their own type, so consistency comes from restraint:

* **Headings** — GitHub's own heading stack, prefixed with `&nbsp;` + emoji + `&nbsp;`
  for optical breathing room around the glyph.
* **Monospace** — `ui-monospace, SFMono-Regular, Menlo, monospace` in `assets/pipeline.svg`
  and in the typing banner (Fira Code). Code voice signals generated content.
* **Captions** — wrapped in `<sub>`, coloured Dim Slate. Used for provenance notes
  and the build timestamp.
* **The language bar is a fenced `text` block**, not an image. It renders identically
  everywhere, needs no network round-trip, and stays readable when images are blocked.

---

## 4. Component stylings

**Badges** — `for-the-badge` style throughout, uniformly. Two variants:

* *Stat and credential badges*: two-segment, `labelColor=1A1B27` with a coloured logo.
  Quiet by design; the logo carries the colour.
* *Call-to-action badges*: single-segment with a saturated fill and a `#1A1B27` logo —
  inverted, so the three buttons in the closing section read as the loudest thing on
  the page. That inversion is the only place saturated fills are allowed.

**Repository cards** — `github-readme-stats` pins at `width="49%"`, two per row, with
`bg_color` pinned to Void Indigo and `hide_border=true`. Borders would fight the
section rules.

**Section rules** — `capsule-render` `type=rect`, `height=2`, gradient
`7AA2F7 → BB9AF7 → 7DCFFF`. The same three stops as the header, so the eye reads
them as the same system.

**The pipeline illustration** (`assets/pipeline.svg`) is hand-authored and
self-hosted. Every other visual on the page depends on a third-party service that can
rate-limit or disappear; this one cannot. Its pulses travel *behind* the stage cards so
data visibly enters a stage, is processed, and emerges — the animation carries meaning
rather than just moving.

---

## 5. Layout principles

* **Centred spine.** Header, stats, tech, analytics and footer are centre-aligned.
  Prose sections are left-aligned. The alternation gives rhythm to a long scroll.
* **Progressive disclosure.** The full project index and the deep-dive metrics live
  inside `<details>`. A first-time visitor sees a curated page; a serious one can open
  everything.
* **Narrative order.** Who → what I use → what I write → what I've earned → what I've
  built → proof → how to reach me. Credentials come *before* projects because the
  hybrid MBA/MSc/AI background is the differentiator.
* **97% width** on wide images, not 100% — a sliver of ground on each side stops
  full-bleed images from colliding with GitHub's container edge.

---

## 6. How the automation works

```
profile.config.json  ──┐
                       ├──►  scripts/sync_profile.py  ──►  README.md
GitHub REST API      ──┘         (marker splicing)
```

`README.md` is part hand-written, part generated. Generated regions are delimited:

```
<!-- STATS:START -->   ... generated, do not edit ...   <!-- STATS:END -->
```

| Marker | Source of truth |
| :--- | :--- |
| `FOCUS` | `profile.config.json → focus` |
| `STATS` | Live GitHub API — repos, stars, forks, followers, bytes of source |
| `TECH` | `profile.config.json → stack` |
| `LANGBAR` | Live `/repos/{owner}/{repo}/languages` summed across all public repos |
| `EDUCATION` | `profile.config.json → education` + `certifications` |
| `PROJECTS` | Live repo list, ordered by `featured.pinned`, enriched by `repo_overrides` |
| `ACTIVITY` | Live `/users/{user}/events/public` |
| `UPDATED` | Build timestamp |

**Editing rules**

* Content changes → edit `profile.config.json`.
* Layout, prose, or section order → edit `README.md` *outside* the markers.
* Anything inside a marker is overwritten on the next run. There is no exception.

**Running it locally**

```bash
python3 scripts/sync_profile.py           # rewrite README.md
python3 scripts/sync_profile.py --check   # exit 1 if stale (useful in a pre-commit hook)
```

The script has **no third-party dependencies** — stdlib `urllib` only — so CI needs no
`pip install` step. It authenticates from `GITHUB_TOKEN`, falling back to your local
`gh auth token` so a local run behaves like a CI run.

It is **idempotent**: it compares rendered output against the current file and writes
nothing when they match, so the nightly job produces no empty commits.

---

## 7. Pipelines

| Workflow | Schedule | Writes to | Purpose |
| :--- | :--- | :--- | :--- |
| `profile.yml` | `03:17 UTC` daily | `main` | README sync, 3D calendar, metrics card |
| `snake.yml` | `02:41 UTC` daily | `output` | Contribution snake, light and dark |

Every generator that touches `main` runs in a **single job producing a single commit**.
Splitting them into separate workflows on the same cron makes them race for the branch
tip, and the losers fail with non-fast-forward rejections. The snake is separate only
because it targets the orphan `output` branch, where it cannot collide.

The cron times are deliberately off the hour: `github-readme-stats`, `capsule-render`
and friends are shared free services that rate-limit hardest on the hour.

### Optional: richer metrics

`lowlighter/metrics` renders public data with the default token. To include private
contribution counts, create a fine-grained PAT and add it as a repository secret named
`METRICS_TOKEN`. The workflow picks it up automatically:

```yaml
token: ${{ secrets.METRICS_TOKEN || secrets.GITHUB_TOKEN }}
```

---

## 8. Failure modes to know about

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| A stats card renders as a broken image | The free Vercel service is rate-limited | Transient; it recovers. The `LANGBAR` block is deliberately image-free so the page never looks empty. |
| Snake image is missing | The `output` branch does not exist yet | Run the **Contribution Snake** workflow once from the Actions tab. |
| 3D calendar missing | First pipeline run has not finished | Run **Profile Pipeline** from the Actions tab. |
| A marker block goes empty | Marker comment was edited or deleted | Restore the exact `<!-- KEY:START -->` / `<!-- KEY:END -->` pair; the script logs `marker KEY not found`. |
| Typing banner or streak card blank | Using a retired `*.herokuapp.com` host | Both moved to `*.demolab.com`. This repo already uses the current hosts. |
