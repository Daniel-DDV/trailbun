# Trailbun

**Keep your agent on the trail.**

Trailbun helps a coding agent preserve the actual task, notice artifact drift,
and recover with a compact checkpoint and current verification. The voice is
practical, direct and mildly exasperated by unnecessary complexity. The rabbit
knows the way back; it does not pretend the hole cannot exist.

## Character and visual language

The original mascot is a scruffy rabbit guide with one folded ear, half-lidded
eyes, a chartreuse neckerchief and a small task card. Its open paw points toward
the simple trail. A cutaway rabbit hole contains an absurd stack of architectural
diagrams. The joke belongs to the situation, not to the developer using the tool.

Use plum ink, warm cream and chartreuse. The drawing combines expressive ink
lines with restrained paper grain. Retain its irregular edges and asymmetrical
ears. Avoid glossy 3D treatment, neon gradients, shields, locks and robot heads.

| Color | Value | Role |
| --- | --- | --- |
| Plum | `#35263E` | Type and ink |
| Cream | `#F4F0E7` | Light canvas |
| Chartreuse | `#D2ED73` | Direction and small accents |
| Deep plum | `#211A29` | Dark canvas |

These are the intended design colors; generated textures contain nearby shades.

## Delivered assets

| File | Verified dimensions | Intended use |
| --- | --- | --- |
| [hero-light.png](../assets/hero-light.png) | 1774 × 887 | Light README hero |
| [hero-dark.png](../assets/hero-dark.png) | 1774 × 887 | Dark README hero |
| [mascot.png](../assets/mascot.png) | 1254 × 1254, RGBA | Transparent character |
| [social-preview.png](../assets/social-preview.png) | 1774 × 887 | Social card, 2:1 aspect ratio |
| [social-preview.svg](../assets/social-preview.svg) | 1280 × 640 viewport | Layout wrapper referencing the PNG |
| [demo.gif](../assets/demo.gif) | 1000 × 520, 25 seconds | Recorded deterministic terminal demo |

PNG sizes were read from the image files. The mascot has an alpha channel and a
fully transparent top-left pixel. All four generated images were visually
inspected for identity, composition and spelling. The social PNG is **not**
1280 × 640: the generator retained its 1774 × 887 output despite a targeted
resize request. The SVG supplies the requested viewport without changing the
raster pixels. Keep it beside `social-preview.png` when using that wrapper.

The README uses a responsive `picture` element to select the light or dark hero.
Keep the tagline as real Markdown text as well, for accessibility and search.

The terminal GIF is rendered from the exported demo JSON with FFmpeg and the
repository's rendering script. It is separate from the generated illustrations
and labels itself as a deterministic demonstration with no live model.

## Generation provenance

Generated on 2026-09-08 with the built-in `image_gen.imagegen` tool. The model
identifier was not exposed in its response. No external mascot artwork was
provided as a reference. The light hero was generated first; the dark hero,
transparent cutout and social card were edits of that original. No Python or
other raster-editing tool was used to modify the output.

Exact prompts, edit ancestry, output filenames and observed dimensions are
retained in [assets/prompts.json](../assets/prompts.json). The local generated
originals were copied into the repository; repository consumers do not depend
on the generating machine's paths. Existing generated provenance metadata was
preserved by copying the PNGs unchanged.

Ponytail inspired the use of a distinctive character and an immediately legible
problem. Matt Pocock's skills inspired navigation from an engineering failure
to a concrete action. Trailbun uses its own character, visual treatment, writing
and functionality. See [research](RESEARCH.md#presentation).

## Voice and claim discipline

- Lead with the task: checkpoints, scope checks, diagnosis and receipts.
- Let humor expose a familiar detour: a small bug turning into a framework.
- Say what the tested mechanism does and name uncovered paths nearby.
- Publish measurements with the task, environment, sample size and receipt.
- Never turn a passing fixture into a universal prevention or security claim.

The public name is **Trailbun** and the tagline is **Keep your agent on the
trail.** The previous repository identity is migration history, not a second
product name or competing headline.
