import type { ComponentPropsWithRef } from 'react';

export function Select({className = '', ...props}: ComponentPropsWithRef<'select'>) {
  return <span className="hf-select"><select {...props} className={'hf-input ' + className} /><svg className="hf-select__chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6" /></svg></span>;
}
