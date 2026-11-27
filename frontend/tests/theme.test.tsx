import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ThemeProvider, ThemeToggle } from '../src/app/ThemeControl';

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});
afterEach(() => cleanup());

function MountTheme() {
  return <ThemeProvider><ThemeToggle /></ThemeProvider>;
}

describe('theme control', () => {
  it('toggles the root theme and persists the choice across mounts', () => {
    const { unmount } = render(<MountTheme />);
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('shield-theme')).toBe('dark');
    unmount();
    render(<MountTheme />);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();
  });
});
