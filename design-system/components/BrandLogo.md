# BrandLogo

The owner-supplied package is the source for the mark and wordmark. Original SVG,
wordmark, horizontal lockup, application icon and favicon files live in
`ui/src/design/assets/brand/originals`; provenance.json records package and file
hashes. No new font, remote asset or third-party dependency is introduced.

The shared component retains the exact supplied vector geometry and wordmark
silhouette. Its transparent ground, brand-ink and brand-signal follow the active
application theme. The wordmark uses the original PNG alpha as a CSS mask; Vite
emits a self-origin hashed asset. The dark ink matches the design system's light
text and the dark orange matches its existing estimated-result palette. The
semantic roles remain separate: a logo is not a scientific outcome.

Expanded navigation and sign-in use the horizontal mark/wordmark composition.
Collapsed navigation shows only the mark. The component exposes one accessible
HYPRN name, with decorative inner shapes; no duplicate rendered text name, fixed
white plate, screen override or invented alternative lettering. Original fixed
artwork is preserved for contexts that need it. This owner-approved adaptation
supersedes the previous unchanged-stacked-PNG requirement.
