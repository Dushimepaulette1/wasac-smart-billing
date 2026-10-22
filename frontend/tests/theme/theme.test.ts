import { applyTheme, THEME_COLOR } from '../../src/theme/theme';

function addThemeColorMetas() {
  document.head.innerHTML = `
    <meta name="theme-color" content="#040A16" media="(prefers-color-scheme: dark)" />
    <meta name="theme-color" content="#EEF3F9" media="(prefers-color-scheme: light)" />`;
}

describe('applyTheme', () => {
  it('when the household picks a theme, should colour the status bar to match it', () => {
    addThemeColorMetas();
    applyTheme('light');
    const colours = [...document.querySelectorAll('meta[name="theme-color"]')].map((m) => m.getAttribute('content'));
    expect(colours).toEqual([THEME_COLOR.light, THEME_COLOR.light]);
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it("when switching back to dark, should not keep the phone's system colour", () => {
    addThemeColorMetas();
    applyTheme('light');
    applyTheme('dark');
    const colours = [...document.querySelectorAll('meta[name="theme-color"]')].map((m) => m.getAttribute('content'));
    expect(colours).toEqual([THEME_COLOR.dark, THEME_COLOR.dark]);
  });
});
