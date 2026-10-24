# X reading tweaks (Brave)

A Stylus userstyle for x.com rebuilt as a standalone adblock cosmetic filter
list: bigger tweet text, bigger display names, an evenly spaced action row, a
solid header, a roomier home feed, and a decluttered menu (Grok, Premium,
Calls, Ads, Creator Studio, Business, Lists).

Separate project from `x-declutter` and `x-floating-bar` on purpose. Nothing is
mixed between them.

## Install

Copy this URL into **brave://settings/shields/filters** → *Custom filter lists*:

```
https://raw.githubusercontent.com/urlittledollstacy-web/x-tweaks/main/x-tweaks-brave.txt
```

Then reload x.com. If nothing changes, force-stop Brave and reopen it so the
list is fetched.

## What it changes

| Area | Effect |
|---|---|
| Tweet text | 17px, line-height 1.45 |
| Display name | 16px |
| Action row | `flex`, `space-between`, evenly spaced |
| Header | solid background, blur removed |
| Home feed row | avatar and body on a two-column grid |
| Menu | Grok, Premium, Calls, Ads, Creator Studio, Business, Lists hidden |

## Why the original selectors stopped working

Every selector in the source userstyle used `data-testid`
(`div[data-testid="tweetText"]`, `[data-testid="User-Name"]`, and so on). X
shipped a new front end, and today x.com serves no `data-testid` attributes on
these elements at all. The old class names are gone too; X now uses `x-`
prefixed classes, `data-` attributes, and plain Tailwind utility classes. The
list targets the markup X actually serves now.

## Two traps worth knowing about

**Bare procedural selectors do not work.** adblock-rust files a rule with no
action as a *hide selector*, and Brave injects those as plain CSS:

```css
selector { display: none !important; }
```

That is fine for a real CSS selector, but `:has-text(Grok)` and `:upward(1)`
are not CSS. The browser throws and the entry stays visible. Every procedural
rule here therefore carries an explicit `:style(display: none !important)`.

**`href*=` matches external links.** The substring form also matches absolute
URLs, so a tweet linking to `https://example.com/i/lists` would lose its link.
Every route rule is anchored to the relative form, `href^="/..."`. The test
harness keeps external links as controls so this cannot regress.

## Files

| File | Purpose |
|---|---|
| `x-tweaks-brave.txt` | The filter list. This is the one to install. |
| `verify.py` | End-to-end verification. See below. |
| `_fixtures/` | Captured x.com markup and a synthetic logged-in nav. |
| `serve.py`, `start.sh` | Local HTTP server, for testing before publishing. |

## Verifying

```bash
python3 verify.py
```

`verify.py` runs the real pipeline:

1. adblock-rust parses the list and returns hide selectors and procedural
   actions.
2. Playwright serves the captured x.com markup at `https://x.com/home` and
   injects the hide selectors the way Brave's `kHideSelectorsInjectScript` does.
3. Brave's own operator set runs over the procedural actions.
4. Computed styles are compared before and after, so a rule that does nothing
   cannot pass.

The Rust harness lives in `/tmp/abltest` and must be built with the
`css-validation` feature, because that is what Brave uses. Without it the
engine does not split procedural operators into steps, and the list looks
broken when it is fine.

## Notes

The `_fixtures/home.html` capture is the server-rendered document, so `verify.py`
strips its `<script>` tags before serving it. Left in place, React boots, finds
no API, and blanks the page.

The logged-out capture cannot contain the signed-in navigation, so the declutter
rules are exercised against `_fixtures/nav-harness.html`, which reproduces the
same hrefs, aria-labels, roles and label text.
