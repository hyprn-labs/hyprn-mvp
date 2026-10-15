# BrandLogo

The shared product mark in the app bar and sign-in shell. The component owns the
accessible name `HYPRN`, approved size and fixed light `brand-ground` in both themes.
Screens compose `BrandLogo` from `ui/src/design`; they supply no URL, colour or text
wordmark. The original PNG bytes are the canonical source at
`ui/src/design/assets/brand/hyprn-stacked-color-on-light.png`.

The logo is an imported asset, so Vite resolves the `/ui/` base and emits a hashed
file. Its explicit `?no-inline` import keeps it an ordinary self-origin image in all
builds; production also disables asset inlining. Generated build copies are not
source authorities. No external path or network image is required. This follows
[Vite asset guidance](https://vite.dev/guide/assets.html).

`brand-ink` and `brand-signal` describe the supplied asset; only the original logo
uses brand orange. Primary actions use neutral `accent`, and scientific warnings,
outcomes, provenance and assistant marks retain their separate semantic roles.
