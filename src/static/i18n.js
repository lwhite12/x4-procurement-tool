// This app's own UI text (button labels, section titles, modal copy,
// About page prose) -- completely separate from the game data's own
// localization (a shared localized_strings DB table keyed by ware_id, see
// generate_ships_table.py's parse_localized_strings() and api.py's
// GET /api/ships own docstring), which has nothing to do with this file.
// Ship/ware/equipment names come from the API's own ?lang=<code> query
// param (app.js's loadShips() passes i18next.language automatically),
// falling back to English per-ware wherever no translation exists --
// entirely that endpoint's own concern, this file never touches ship/ware
// text directly. Both systems happen to share one language code (e.g.
// "de") and this file's own SUPPORTED_LANGUAGES/picker choice is what
// drives which one loadShips() asks for, but they're otherwise
// independent: this file's job stops at the UI text and at deciding (and
// persisting) which language code is "current."
//
// Library: src/static/vendor/i18next.min.js -- i18next v23.16.8
// (https://www.i18next.com/), MIT licensed, fetched once from jsdelivr and
// committed here rather than loaded from a CDN at request time. This app
// has no other runtime dependency on an external host (fonts, images, and
// every other script are all served from itself already), and vendoring
// keeps a CDN outage from ever breaking page load.
//
// Resource files: src/static/i18n/<lang>.json, one flat (nested-by-
// section) key -> string map per language, fetched directly here rather
// than via i18next's own HTTP backend plugin -- avoids pulling in a
// second library for what's just a couple of same-origin static-file
// fetches. Every SUPPORTED_LANGUAGES entry is loaded eagerly at init (both
// files together are a few KB, not worth lazy-loading). English (en.json)
// is always loaded as the fallback language, so a missing key in any
// other language's file degrades to English rather than showing the raw
// dotted key name -- de.json today deliberately only has a representative
// subset of real German translations (nav bar, header, main section
// legends, Size/Purpose/Type/Race/Vendor filter labels) proving the
// mechanism works end-to-end; everything else correctly falls back to
// English until a real full translation pass happens.
//
// Two ways this gets used, both safe to call only after i18nReady
// resolves:
//   - Static markup: any element with a data-i18n="<key>" attribute gets
//     its textContent replaced; data-i18n-html="<key>" sets innerHTML
//     instead, for the handful of strings with embedded markup (e.g. the
//     About page's inline <code>/<strong>/<a> tags) that a plain
//     textContent swap would flatten to literal text; data-i18n-
//     placeholder="<key>" / data-i18n-title="<key>" / data-i18n-aria-
//     label="<key>" set that attribute instead of any text content. All
//     are applied by applyTranslations() below, called once automatically
//     as soon as i18nReady resolves. Leaving the original English text/
//     attribute in the HTML source itself is deliberate -- that's what a
//     user briefly sees before this first runs, and all they ever see if
//     JS fails outright.
//   - JS-generated content (app.js): call the global t(key, options)
//     directly (options is i18next's own interpolation/pluralization
//     argument -- see https://www.i18next.com/translation-function/essentials)
//     wherever app.js builds text itself. Not yet done anywhere -- app.js's
//     own dynamically-created button/label/message text is still plain
//     English string literals throughout; converting those is a separate,
//     much larger follow-up (this file and the static-markup conversion in
//     index.html are just the foundation).
//
// Switching languages (the #language-picker below) reloads the whole page
// rather than trying to live-swap everything in place -- see
// changeLanguage()'s own comment for why.
//
// Language selection, in priority order: an explicit prior choice from the
// #language-picker dropdown (persisted to localStorage), else the
// browser's own navigator.language, else English. The picker itself
// (markup in index.html, next to the Share button) just lists language
// codes (see setupLanguagePicker() below) -- SUPPORTED_LANGUAGES is the
// one place a new language's code needs adding once its resource file
// exists.

const SUPPORTED_LANGUAGES = ["en", "de", "es", "fr", "it", "pt", "cs", "pl", "ru", "uk", "zh", "ko", "ja", "bg", "tr"];
const LANGUAGE_STORAGE_KEY = "x4-fleet-planner-language";

function resolveInitialLanguage() {
  let stored = null;
  try {
    stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  } catch {
    // localStorage unavailable (private browsing etc.) -- fall through to
    // the browser-language/English defaults below.
  }
  if (stored && SUPPORTED_LANGUAGES.includes(stored)) return stored;

  const browserLang = (navigator.language || "en").slice(0, 2).toLowerCase();
  return SUPPORTED_LANGUAGES.includes(browserLang) ? browserLang : "en";
}

async function loadLanguageResource(lang) {
  const response = await fetch(`/i18n/${lang}.json`);
  if (!response.ok) throw new Error(`No resource file for language "${lang}"`);
  return response.json();
}

async function initI18n() {
  const resources = {};
  for (const lang of SUPPORTED_LANGUAGES) {
    try {
      resources[lang] = { translation: await loadLanguageResource(lang) };
    } catch {
      // No resource file for this language yet -- fallbackLng (set below)
      // makes every t() call for it resolve to English instead.
    }
  }
  await i18next.init({
    lng: resolveInitialLanguage(),
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGES,
    resources,
  });
  document.documentElement.lang = i18next.language;
}

function t(key, options) {
  return i18next.t(key, options);
}

function applyTranslations(root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-html]")) el.innerHTML = t(el.dataset.i18nHtml);
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  }
  for (const el of root.querySelectorAll("[data-i18n-title]")) el.setAttribute("title", t(el.dataset.i18nTitle));
  for (const el of root.querySelectorAll("[data-i18n-aria-label]")) {
    el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel));
  }
  document.title = t("app.title");
}

// Persists the choice, then reloads the page rather than trying to
// re-render everything in place. UI text alone could switch live (i18next's
// resource bundles are already loaded -- see initI18n()), but ship/ware
// names are a separate fetch (app.js's loadShips() sends ?lang=<code>, see
// api.py's /api/ships), and by the time this fires the app has already
// built a lot of state from the old language's data (allShips, filter
// checkboxes, whatever's in the ship builder, fleet lists' own cached
// ware names, ...) -- re-fetching and re-deriving all of that correctly
// in place is a lot of surface area for what's fundamentally a rare
// action. A reload re-runs bootstrap() from scratch under the new
// language and restores everything else from localStorage (fleets, price
// overrides, filters) exactly as any other page reload already does.
function changeLanguage(lang) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
  } catch {
    // Choice just won't survive the reload -- not worth failing over.
  }
  location.reload();
}

// #language-picker (index.html, header row) lists every SUPPORTED_LANGUAGES
// code as a plain <option> -- kept in sync with whichever language
// actually won out in initI18n() (a persisted choice can differ from the
// picker's own markup-order default), then wired to changeLanguage() on
// selection.
function setupLanguagePicker() {
  const picker = document.getElementById("language-picker");
  if (!picker) return;
  picker.value = i18next.language;
  picker.addEventListener("change", () => changeLanguage(picker.value));
}

// app.js awaits this before its own bootstrap() proceeds, so nothing it
// renders races a still-in-flight translation load.
const i18nReady = initI18n().then(() => {
  applyTranslations();
  setupLanguagePicker();
});
