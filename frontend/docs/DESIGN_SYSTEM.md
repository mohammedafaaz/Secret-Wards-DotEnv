# Design System

## Brand

The exact product spelling is **shield**. The identity uses a lowercase wordmark, a quiet aperture mark and an editorial instrument aesthetic. It should feel private, clinically literate and carefully made—not like a generic hospital portal or hacker console.

## Color tokens

| Token | Value | Use |
|---|---|---|
| Paper | `#F2EFE6` | Warm canvas and quiet structural surfaces |
| Porcelain | `#FFFDF8` | Primary workspace surfaces |
| Forest | `#24594C` | Brand accent, active navigation, safe action and focus |
| Ink | `#1C2722` | Primary text |
| Terracotta | `#BD6349` | Caution and disconnected/unavailable operational state |
| Muted red | Reserved | Only a genuine critical backend failure |

Use alpha-modulated dividers and quieter surface tones rather than enclosing every element in a card. Avoid blanket gradients.

## Typography

Bundle locally licensed SIL Open Font License files: Newsreader for editorial display headings, DM Sans for interface text, IBM Plex Mono for technical labels, and Noto Sans Devanagari when supported Hindi content is supplied. Instrument Sans and Syne remain bundled for compatibility but are no longer the primary pairing. Never load fonts from a runtime CDN. Body text is at least 10–11px for dense technical labels and 13–16px for explanatory copy; landing headlines are fluid via `clamp()`. Technical IDs use IBM Plex Mono. Hindi content should specify Noto Sans Devanagari as a language-appropriate fallback.

## Space and layout

Use an 8px rhythm with 12–16px internal component gaps, 16–24px related-control gaps, 24–32px card separation and 48–72px workspace section spacing. Landing sections use wider 80–150px vertical intervals. The landing page uses an asymmetric editorial split composition. Workspace uses a collapsible 246px navigation rail, a sticky 58px context bar and a spacious content canvas; on mobile the rail becomes a fixed five-item bottom navigation.

## Signature motifs

Layered folios, a guarded membrane, brass-toned apertures and editorial chapter indices recur across the landing page and workspace. The custom 3D privacy-firewall instrument depicts abstract inputs, a membrane and blank output—not records, results, or live processing. Fallback geometry remains visible when WebGL is not.

## Motion and interaction

Use brief transform/opacity transitions, soft route changes, small button press states and one session-only 1.05-second entry treatment. Scroll reveals communicate the concept, not actual run progress. Do not hijack dashboard scroll or use magnetic controls, tracking cursors or noisy perpetual particles. Disable or reduce motion under `prefers-reduced-motion`. Make all tabs, inputs, buttons and navigation keyboard accessible with visible forest focus rings. Unavailable actions remain disabled with explicit explanation.

## Data-state language

“Conceptual” marks the landing workflow. “Engine not connected” means no backend adapter or processing has been connected. “Unavailable” means no result exists, not zero risk or success. Do not use numeric charts until real supported measurements arrive. Keep safe labels and aggregate file metadata; never show raw filenames, record contents, identity evidence or secrets.

## Responsive behavior

Prioritize desktop and laptop, then adapt without horizontal overflow for tablet and mobile. The file selection and workspace cards become one column on narrow screens. The pipeline becomes a vertical stage list. Privacy/integrity panels stack. Artifact rows reflow to preserve readable labels and actions. Use WebGL only when available, at a bounded pixel ratio, and retain a CSS fallback.
