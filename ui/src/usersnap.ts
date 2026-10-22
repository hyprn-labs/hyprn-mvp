/** Optional hosted feedback. Configuration contains no account or study information. */
type UsersnapApi = {
  init(options: {
    useSystemFonts: true;
    collectGeoLocation: 'none';
    useLocalStorage: false;
  }): Promise<unknown>;
};

declare global {
  interface Window {
    onUsersnapLoad?: (api: UsersnapApi) => void;
  }
}

let started = false;

export function initializeUsersnap(): void {
  if (started) return;
  const configuration = document.querySelector<HTMLMetaElement>('meta[name="hyprn-usersnap"]');
  if (!configuration) return;
  const id = configuration.content;
  const nonce = configuration.dataset.nonce ?? '';
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(id) ||
    !/^[A-Za-z0-9_-]{43}$/.test(nonce)
  )
    return;
  started = true;
  let initialized = false;
  window.onUsersnapLoad = (api) => {
    if (initialized) return;
    initialized = true;
    // Promise.resolve also catches synchronous vendor failures without blocking React.
    void Promise.resolve()
      .then(() =>
        api.init({
          useSystemFonts: true,
          collectGeoLocation: 'none',
          useLocalStorage: false,
        }),
      )
      .catch(() => undefined);
  };
  const script = document.createElement('script');
  const url = new URL('https://widget.usersnap.com/global/load/' + id);
  url.searchParams.set('onload', 'onUsersnapLoad');
  url.searchParams.set('n', nonce);
  script.src = url.href;
  script.async = true;
  script.nonce = nonce;
  script.addEventListener(
    'error',
    () => {
      window.onUsersnapLoad = undefined;
    },
    { once: true },
  );
  document.head.appendChild(script);
}
