# Optional Usersnap feedback

The local workspace loads no Usersnap resource by default. To opt in, set
`HYPRN_MVP_USERSNAP_GLOBAL_ID` in the application process environment to the
canonical lowercase UUID of the reviewed Usersnap global widget and restart that
application. Empty or absent disables the integration; invalid nonempty values
fail startup with a configuration error. The identifier is public configuration,
not a credential. Keep installation values outside the repository.

Activation requires a reviewed Usersnap project enabled for that installation, a
compiled UI containing the adapter, and application HTML served through
`mount_workspace`. Confirm the exact release and recoverable prior configuration
before deployment. No modeling service, worker policy, scientific record or
attestation changes are needed.

## Scoped external-service exception

The user-authorized Usersnap integration is a provider-specific exception to the
external runtime script prohibition in `AGENTS.md` and the repository UI skill.
Enabled HTML uses the following policy, where `NONCE` is generated separately for
every response:

```text
default-src 'none';
script-src 'self' 'nonce-NONCE' https://widget.usersnap.com https://resources.usersnap.com;
style-src 'self' 'nonce-NONCE';
img-src 'self' blob: https://resources.usersnap.com;
connect-src 'self' https://widget.usersnap.com;
font-src 'self';
frame-src 'self';
base-uri 'none';
frame-ancestors 'none';
form-action 'self'
```

The official loader and API use `widget.usersnap.com`; the observed setup bundles
and vendor resources use `resources.usersnap.com`. Their source evidence is in
[UI provenance](../../ui/provenance.md). Same-origin blank frames inherit the
document policy. Script/style propagation uses the same response nonce, including
the loader's `nonce` property and `n` query parameter. External fonts, arbitrary
remote frames, blanket subdomains, inline-script exceptions and evaluation
exceptions remain unavailable. Asset responses and disabled documents retain the
existing restrictive policy.

Enabled documents are `Cache-Control: no-store`, omit ETag/Last-Modified, and ignore
conditional/range reuse so each successful GET or HEAD represents a fresh matching
body/header pair. X-Frame-Options remains DENY, with the existing application host
and origin enforcement unchanged.

## Collection and verification

The adapter initializes `useSystemFonts: true`, `collectGeoLocation: 'none'` and
`useLocalStorage: false`. It attaches no automatic identity, study fields or
credentials. Hosted code still receives network metadata and can see the page;
user-selected screenshots and feedback may contain its contents. Review provider
project settings, including capture features, before enabling a project. A failed
download or rejected initialization leaves the workspace available.

Run `./hyprn-mvp dev check public-api`, `./hyprn-mvp dev check usersnap-ui`,
`./hyprn-mvp dev check combined-static` and
`./hyprn-mvp dev check locality-contracts` for isolated integration evidence.
The browser fixture serves the real application and compiled UI, substitutes only
vendor responses, makes no external submissions and releases its HTTP process.
It does not prove the mutable provider's current compatibility or human acceptance.

After deployment, record the actual widget opening/closing, keyboard dismissal,
workspace navigation, light/dark and narrow layouts, CSP violations and observed
origins. An unexpected origin needs reviewed evidence and a narrowly scoped policy
change; do not broaden the policy to the vendor's general example. Keep feedback
submission, automated observations and human acceptance as separate results.
Focused checks do not replace the full release qualification gate.

## Rollback

Remove or empty `HYPRN_MVP_USERSNAP_GLOBAL_ID` and restart the application to stop
loading the service on new documents. Close or reload existing browser documents,
which may already contain hosted code. If rolling back the integration release,
restore the identified prior application/UI release and its reviewed configuration
using the installation's normal deployment procedure. Preserve authoring stores.
