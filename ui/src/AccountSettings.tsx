import { useEffect, useRef, useState } from 'react';
import { ApiError, message, type HyprnMvpApi } from './api';
import type { UserProfile1 } from './contract';
import {
  Button,
  DialogActions,
  FormActions,
  FormField,
  FieldHint,
  Select,
  SettingsSection,
  TextInput,
} from './design';
import { cleanGuard, type EditorGuard } from './workspaceModel';

/** The profile is shared; saved scientific authorship keeps its original name. */
export function AccountSettings({
  api,
  profile,
  onProfile,
  onHandle,
  onClose,
  appearance = false,
  onBusyChange,
}: {
  onClose?: () => void;
  onBusyChange?: (busy: boolean) => void;
  appearance?: boolean;
  api: HyprnMvpApi;
  profile: UserProfile1 | null;
  onProfile: (value: UserProfile1) => void;
  onHandle: (handle: EditorGuard) => void;
}) {
  const [initialTheme, setInitialTheme] = useState(
    () => document.documentElement.dataset.theme ?? 'dark',
  );
  const [theme, setTheme] = useState(initialTheme);
  const [alias, setAlias] = useState(profile?.display_alias ?? '');
  const [busy, setBusy] = useState(false);
  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const active = useRef(true);
  const aliasDirty = alias !== (profile?.display_alias ?? '');
  const dirty = aliasDirty || theme !== initialTheme;
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      onHandle(cleanGuard());
    };
  }, []);

  async function load() {
    setBusy(true);
    setError('');
    try {
      const value = await api.profile();
      if (!active.current) return;
      onProfile(value);
      setAlias(value.display_alias ?? '');
    } catch (e) {
      if (active.current) setError(message(e));
    } finally {
      if (active.current) setBusy(false);
    }
  }
  useEffect(() => {
    if (!profile) void load();
  }, []);

  async function save() {
    if (!profile || busy) return false;
    setBusy(true);
    setError('');
    setSaved(false);
    try {
      const value = aliasDirty ? await api.saveProfile(alias || null, profile.revision) : profile;
      if (!active.current) return false;
      onProfile(value);
      setAlias(value.display_alias ?? '');
      if (appearance) {
        document.documentElement.dataset.theme = theme;
        try {
          localStorage.setItem('hyprn-appearance', theme);
        } catch {
          /* Browser-local preference. */
        }
        setInitialTheme(theme);
      }
      setSaved(true);
      onClose?.();
      return true;
    } catch (e) {
      if (active.current) {
        const changed = e instanceof ApiError && e.detail.code === 'stale_revision';
        setError(
          changed
            ? 'Your profile changed elsewhere. Your edits are kept. Load the latest profile before saving.'
            : 'Alias could not be confirmed. Your edits are kept. Load the latest profile to check. ' +
                message(e),
        );
      }
      return false;
    } finally {
      if (active.current) setBusy(false);
    }
  }
  useEffect(() => {
    onHandle({
      dirty: dirty || busy,
      save,
      discard: () => {
        setAlias(profile?.display_alias ?? '');
        setTheme(initialTheme);
        setError('');
      },
    });
  });
  const primary = (
    <Button variant="primary" disabled={busy || !profile || !dirty} onClick={() => void save()}>
      Save
    </Button>
  );
  const recovery = (error || !profile) && (
    <Button disabled={busy} onClick={() => void load()}>
      Load latest profile
    </Button>
  );
  return (
    <>
      <div className="hf-settings-content">
        <SettingsSection title="Account">
          <dl className="profile-account">
            <dt>Account name:</dt>
            <dd>{profile?.account_name ?? 'Loading…'}</dd>
          </dl>
          <FormField label="Display alias" optional>
            <TextInput
              aria-label="Display alias"
              value={alias}
              maxLength={128}
              disabled={busy || !profile}
              aria-describedby="display-alias-hint"
              onChange={(e) => {
                setAlias(e.target.value);
                setSaved(false);
              }}
            />
            <FieldHint id="display-alias-hint">Leave blank to use your account name.</FieldHint>
          </FormField>
        </SettingsSection>
        {appearance && (
          <SettingsSection title="Appearance">
            <FormField label="Theme">
              <Select
                aria-label="Appearance"
                value={theme}
                disabled={busy}
                onChange={(e) => setTheme(e.target.value)}
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </Select>
              <FieldHint>Saved in this browser.</FieldHint>
            </FormField>
          </SettingsSection>
        )}
        {error && <p role="alert">{error}</p>}
        {saved && !onClose && <p role="status">Settings saved.</p>}
        {recovery}
      </div>
      {onClose ? (
        <DialogActions primary={primary}>
          <Button disabled={busy} onClick={onClose}>
            Cancel
          </Button>
        </DialogActions>
      ) : (
        <FormActions primary={primary} />
      )}
    </>
  );
}
