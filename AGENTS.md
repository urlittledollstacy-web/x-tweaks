# AGENTS.md

## Project

`x-tweaks-brave.txt` — a Brave cosmetic filter list for x.com, rebuilt from a
Stylus userstyle. Bigger tweet text (17px/1.45), display name 16px, action row
`flex`, solid header, two-column home feed row, and a decluttered menu.

The file *is* the deliverable. No build step.

**Standalone project.** Not to be mixed with `x-declutter`, `x-floating-bar`,
the Reddit lists, or the abandoned fortnite.gg work. Separate repo, separate
port, separate concerns.

## Published

Repo: https://github.com/urlittledollstacy-web/x-tweaks

Install URL for Brave (custom filter lists):

    https://raw.githubusercontent.com/urlittledollstacy-web/x-tweaks/main/x-tweaks-brave.txt

`GH_ADMIN_TOKEN` is the only token that can create a repo and push here.
`GITHUB_TOKEN` returns 403 "Resource not accessible by integration" on repo
creation, and `GH_PUSH_TOKEN` is denied on push. Push with:

    git push "https://x-access-token:${GH_ADMIN_TOKEN}@github.com/urlittledollstacy-web/x-tweaks.git" main:main

The sandbox exposes only ports 12000 and 12001. `work-3` and up resolve to the
same IP but return a proxy 404, so they are not routed to a third port. That is
why this list ships over the raw GitHub URL rather than a workspace URL: the
workspace URL dies on every sandbox restart.

## Verifying

    python3 verify.py

Needs the Rust harness at `/tmp/abltest`, built **with the `css-validation`
feature**. See below.

## Three traps that cost real time

### 1. Bare procedural selectors are silently dead

adblock-rust files a rule with no action as a *hide selector*. Brave injects
each hide selector as plain CSS:

```js
insertRule(selector + '{display:none !important}')
```

`:has-text(Grok)` and `:upward(1)` are not CSS. The browser throws, Brave logs
an ignored-injection message to the console, and the entry stays visible. No
parse error, no warning at load time.

Every procedural rule must carry an explicit `:style(display: none !important)`.
The original userstyle's 14 declutter rules were all broken this way.

### 2. The Rust harness must enable `css-validation`

`css-validation` is **not** in adblock-rust's default features. Brave enables
it. Without it the engine does not split procedural operators into steps:

```
without: {"selector":[{"type":"css-selector","arg":"article div:matches-path(/home/):has(...) > div"}]}
with:    {"selector":[{"type":"css-selector","arg":"article div"},
                      {"type":"matches-path","arg":"/home/"},
                      {"type":"css-selector","arg":":has(...) > div"}]}
```

The first form is one opaque step no browser can run, so the list looks broken
when it is fine. In `Cargo.toml`:

```toml
adblock = { version = "0.13.3", features = ["css-validation"] }
```

### 3. `href*=` hides external links

`a[href*="/i/lists"]` also matches `https://example.com/i/lists`, so a tweet
linking there loses its link. All seven route rules were confirmed to have this
bug against the harness. They are anchored with `href^="/..."` instead.

The nav harness keeps those external links as controls (`want-ext-*`), so the
bug cannot come back silently.

## Testing notes

### The capture is server-rendered

`_fixtures/home.html` is the server-rendered document. Loaded as-is, React boots,
finds no API, and blanks the page (0 articles). `verify.py` strips `<script>`
tags before serving it. It also serves it at `https://x.com/home` so that
`location.pathname` is right for `:matches-path`.

### The logged-out capture has no signed-in nav

So the declutter rules are exercised against `_fixtures/nav-harness.html`, which
reproduces the same hrefs, aria-labels, roles and label text. `data-want="1"`
marks controls that must survive; the controls deliberately share tag, role and
shape with the entries that are removed, so an over-broad rule shows up.

Every probed element carries its own hide rule. Do not leave an element to
inherit a parent's `display:none` — that would not prove the rule matched it.

### Nested at-rules in `:style()` do work

Brave builds `[attr][attr]{ <style body> }`. A nested `@media { ... }` inside
that body parses and applies as CSS nesting, verified in Chromium. An earlier
comment in the list claimed otherwise; that was wrong and has been corrected.
The rules here still use only plain declarations, because none needs a media
query.

### `:has()` is native CSS

adblock-rust converts `:-abp-has` to `:has` and passes it through, so `:has()`
works in Brave as ordinary CSS. Only the ABP-procedural operators
(`:has-text()`, `:upward()`, `:matches-path()`) need the step machinery.

## Markup facts

x.com today serves **no `data-testid`** attributes on the timeline elements the
original userstyle targeted. A census of profile, home, search, status, settings
and messages pages finds 0. X's own `styles-*.css` does not contain the string
either. That is why every original selector was inert.

The replacement markup uses `x-` prefixed classes (`x-avatar`,
`x-engagement-pill`), `data-` attributes (`data-engagement-action`, `data-slot`,
`data-icon`), and Tailwind utilities (`whitespace-pre-wrap`, `flex-1`, `w-10`,
`tabular-nums`).

Useful anchors: the action row is `div:has(> [data-engagement-action])`; the
home feed row is `div:has(> div[class*="w-10"] > div > a > div[class*="x-avatar"])`.

## Local server

`bash start.sh` runs `serve.py` on port 12002 (local only) for testing before
publishing. Not needed for delivery.
