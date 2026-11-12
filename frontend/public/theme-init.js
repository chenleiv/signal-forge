// Applies the saved theme before the first paint, so there is no flash of the
// wrong theme. A separate file (not inline) so the CSP can forbid inline
// scripts. Loaded with a plain blocking <script> in <head>.
(function () {
  var theme = null;
  try {
    theme = localStorage.getItem('sf_theme');
  } catch (e) {
    // Storage blocked (private mode, disabled cookies): use the default.
  }
  document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
})();
