export interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  close: () => void;
  showAlert: (msg: string) => void;
  themeParams: Record<string, string>;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

export function getQueryParam(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}
