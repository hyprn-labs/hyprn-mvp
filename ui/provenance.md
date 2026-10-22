# UI dependency and source provenance

All HYPRN MVP UI source is independently authored against the public HYPRN MVP contract. No WhatsOpt product UI, graph engine, editor framework, registry block, icon package or font is copied or embedded.

## Dependencies

| Use | Package | Version | Licence |
|---|---|---|---|
| Runtime | React, React DOM | 19.3.0 | MIT |
| Build | Vite | 8.3.4 | MIT |
| Build | TypeScript | 5.9.3 | Apache-2.0 |
| Browser tests | Playwright | 1.62.1 | Apache-2.0 |

Before installation, `audit_dependencies.py` checks the complete npm lock closure against each package's exact official registry metadata, repository, SHA-512 tarball integrity, name, version and licence inventory. `dependency-audit.json` records raw SHA-256 hashes and notice paths. Official origins include react/react, vitejs/vite, microsoft/TypeScript, microsoft/playwright, DefinitelyTyped/DefinitelyTyped, rolldown/rolldown, oxc-project/oxc, parcel-bundler/lightningcss and the named maintainer repositories of the locked small dependencies; no registry or repository is substituted. The lock is resolved with `--package-lock-only --ignore-scripts` and installed with `npm ci --ignore-scripts`; package lifecycle scripts never run. Dependencies, tarballs, build output and browser evidence live outside the source tree.

Licence notes:

- Fifteen Rolldown platform binding archives omit their own notice file; their MIT licence comes from the main `rolldown` package in the same official repository. Keep that notice alongside any redistributed tooling.
- Lightning CSS is MPL-2.0, used unmodified as a build tool only; it is not part of the served browser JavaScript.
- Distributing build tools keeps their own notices and source obligations.
- The served browser bundle includes React, React DOM and scheduler (all MIT); their notices are retained in `licenses/browser.txt` and embedded in the delivered JavaScript assets. There is no notices page or footer link.

No material proprietary-source or licence conflict was found. New dependencies need the same audit and a permissive licence; see `docs/legal/licensing.md`.

## Comparison and exports

`ComparisonView.tsx` and `exports.ts` are written from HYPRN MVP's public snapshot and portable-record contracts. React renders escaped semantic and source comparisons keyed by stable public identities; imported source is kept as data and never executed.

- Graph exports whitelist SVG elements and attributes, replace interactive HTML labels with SVG text and inline presentation properties. XDSM exports render the displayed table as bounded SVG cells. SVG and HTML exports contain no scripts, `foreignObject`, remote references or private endpoints.
- PNG export uses the browser's SVG decoder and Canvas `toBlob`; the application's content security policy allows `blob:` for images only, with script and connection restrictions unchanged.
- CSV export records the displayed row scope, filters, identities, values and units; text that could be read as a spreadsheet formula is neutralized without changing numeric precision.
- Portable model records and raw sources keep their declared provenance, licence metadata, IDs and bytes through the public API. The UI grants no new licence to user-authored sources or bundled native artifacts. Downloads of stored files go through the application's authorized route.

## Design system layer

`ui/src/design` (components, primitives, graph and source surfaces, `foundry.css`, generated `tokens.css`) and the tooling `design_tokens.py`, `check_design_system.py`, `design_smoke.mjs` and `test_design_tooling.py` are independently authored from the HYPRN MVP Foundry design system in `design-system/`. Built-in glyphs and icons are original inline SVGs; no icon-library path data is copied. The interface uses the operating system's fonts only, so no font file is downloaded, vendored or served. Adding a self-hosted font or icon font would require an official-source, hash and licence audit first, and the served content security policy allows fonts only from the application's own origin.

## References

- https://react.dev/reference/react-dom/client/createRoot
- https://vite.dev/guide/
- https://developer.mozilla.org/en-US/docs/Web/API/XMLSerializer/serializeToString
- https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob

## Optional Usersnap hosted feedback

Usersnap is an explicitly authorized proprietary hosted service, disabled unless the
installation sets `HYPRN_MVP_USERSNAP_GLOBAL_ID`. It is not an installed package or
an audited permissively licensed dependency. No vendor source is copied into this
repository or the compiled UI. See [activation and policy](../docs/operations/usersnap.md)
for the scoped exception to the external-runtime-script rule and its rollback.

Official references checked on 2026-10-20:
[global API](https://help.usersnap.com/reference/global-api) and
[CSP guidance](https://help.usersnap.com/docs/usersnap-with-csp).
The observed official `/global/load/` response was 14,839 bytes with SHA-256
`77dc5d57b35f461bf85f0d4ed20bcbbe46f7f87b65d070cfb13f4c47d2c03d96`.
Its loader/setup chain references `widget.usersnap.com` and `resources.usersnap.com`
and propagates a nonce into same-origin blank frames. This evidence identifies one
observation; the runtime service is mutable and this hash is not a runtime pin.
Actual widget loading and project activation require separate live-provider
verification. The isolated browser suite uses independently authored vendor doubles.

Initialization requests system fonts, no geolocation collection and no local storage.
The adapter supplies no user identity, study data or credentials. Network metadata
still reaches the service, and screenshots or feedback a user chooses to send may
contain workspace information. The adapter does not enable session replay or media
capture. The installation owner must review the active provider project settings.

## Product brand asset

`src/design/assets/brand/hyprn-stacked-color-on-light.png` is the HYPRN stacked colour-on-light logo supplied and authorized by the product owner for this interface. It is copied unchanged; it is not third-party software or a generated replacement. The source identity is recorded in the demo-polish checkpoint.

`BrandLogo` owns the accessible name and theme-independent light ground. Vite imports
this one source asset with `?no-inline`, generating a base-aware, hashed self-origin
URL. Production disables asset inlining for compatibility with the self-only CSP.
There is no runtime dependency on the original external location and no duplicate
public master asset. The unchanged PNG SHA-256 is
`3ec5f72242e291ff570315ea60ae7b669ce20e8dea20d62d7a712e3d74b9ac43`.
