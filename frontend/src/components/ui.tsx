import type { ButtonHTMLAttributes, ReactNode } from 'react';

export function Label({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`text-2xs font-medium text-faint ${className}`}>{children}</div>;
}

export function Badge({ children, tone = 'dim' }: { children: ReactNode; tone?: 'dim' | 'signal' | 'ochre' | 'caution' }) {
  const tones = {
    dim: 'bg-rim text-dim',
    signal: 'bg-signal/10 text-signal',
    ochre: 'bg-ochre/10 text-ochre',
    caution: 'bg-caution/10 text-caution',
  };
  return <span className={`inline-flex items-center rounded-full px-1.5 text-[10px] font-medium leading-4 ${tones[tone]}`}>{children}</span>;
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'ghost' | 'primary' | 'outline' | 'danger'; active?: boolean };

export function Button({ variant = 'outline', active = false, className = '', ...rest }: BtnProps) {
  const v = {
    ghost: 'border-transparent text-dim hover:text-ink hover:bg-card',
    outline: 'border-rim2 text-ink hover:border-faint bg-card',
    primary: 'border-transparent bg-signal/15 text-signal hover:bg-signal/25',
    danger: 'border-transparent bg-alert/10 text-alert hover:bg-alert/20',
  }[variant];
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-signal/50 disabled:cursor-not-allowed disabled:opacity-40 ${v} ${active ? '!bg-signal/15 !text-signal' : ''} ${className}`}
    />
  );
}

export function Row({ k, v, sub }: { k: ReactNode; v: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-rim/60 py-2 last:border-0">
      <div className="text-xs text-dim">{k}</div>
      <div className="text-right">
        <div className="font-mono text-xs text-ink tabular-nums">{v}</div>
        {sub && <div className="text-[10px] text-faint">{sub}</div>}
      </div>
    </div>
  );
}

export function Spinner() {
  return <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-signal/25 border-t-signal" aria-label="Loading" />;
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error' | 'caution'; children: ReactNode }) {
  const t = { info: 'bg-card text-dim', error: 'bg-alert/10 text-alert', caution: 'bg-caution/10 text-caution' }[tone];
  return <div className={`rounded-xl px-3 py-2.5 text-xs leading-relaxed ${t}`}>{children}</div>;
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl bg-card shadow-soft ${className}`}>{children}</div>;
}

export function Pill({ children }: { children: ReactNode }) {
  return <span className="rounded-full bg-rim px-2.5 py-0.5 text-xs font-semibold text-ink">{children}</span>;
}
