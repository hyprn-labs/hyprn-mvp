/** Supplied vector geometry and wordmark, coloured only by the shared theme tokens. */
export function BrandLogo() {
  return <span className="hf-brand-logo" role="img" aria-label="HYPRN">
    <svg className="hf-brand-logo__mark" viewBox="6 6 108 108" aria-hidden="true" focusable="false">
      <path d="M73.37 18.08 A44 44 0 1 0 101.92 46.63" fill="none" stroke="currentColor" strokeWidth="12" />
      <circle cx="60" cy="60" r="14" fill="currentColor" />
      <rect className="hf-brand-logo__signal" x="79.11" y="16.89" width="24" height="24" />
    </svg>
    <span className="hf-brand-logo__wordmark" aria-hidden="true" />
  </span>;
}
