import logoUrl from './assets/brand/hyprn-stacked-color-on-light.png?no-inline';

/** One approved asset and accessible name; its light ground is theme-independent. */
export function BrandLogo() {
  return <img className="hf-brand-logo" src={logoUrl} alt="HYPRN" />;
}
