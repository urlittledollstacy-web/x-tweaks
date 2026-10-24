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

## Four traps that cost real time

### 0. Expires freezes the list, and ASCII matters

`! Expires: 7 days` tells Brave to cache the list for a week. Any fix pushed
inside that window is invisible to the user, which reads exactly like "your
selectors do nothing". Keep it at `1 days` while iterating.

Keep the file pure ASCII. The comment banners once used box-drawing characters;
the list that worked on the same device was plain ASCII. There is no proof the
characters broke parsing, but there is no reason to carry the difference either.
Both files are asserted ASCII in the commit that removed them.

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

### 4. Asserting a declaration is not asserting the layout

The feed rules set `display: grid` on the correct element and the verifier
asserted `display === "grid"`, and passed — while the layout was unchanged. The
grid was applying; it just produced the same picture, because the rule that was
meant to widen the text moved the wrong box. See "Feed row nesting" below.

Assert geometry, not just declarations: relative positions and widths of the
avatar, the name row and the text, plus the text width against the row width.
`verify.py` now does this, and the old rule fails it.

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
original userstyle targeted. Confirmed against live pages (`/jack`, `/home`,
`/jack/status/...` all return 0 occurrences) and against X's own
`styles-*.css` bundle, which does not contain the string either. The source
userstyle is https://userstyles.world/style/31054 and every one of its
selectors was inert.

The replacement markup uses `x-` prefixed classes (`x-avatar`,
`x-engagement-pill`), `data-` attributes (`data-engagement-action`, `data-slot`,
`data-icon`), and Tailwind utilities (`whitespace-pre-wrap`, `flex-1`, `w-10`,
`tabular-nums`).

Useful anchors: the action row is `div:has(> [data-engagement-action])`; the
home feed row is `div:has(> div[class*="w-10"] > div > a > div[class*="x-avatar"])`.

### Feed row nesting (the trap that hid a dead rule)

```
row
 ├─ div.w-10            avatar column
 └─ div.flex-1          content column
      ├─ div.gap-0.5    name/handle row
      │    ├─ div.post-actions   name + handle + time
      │    └─ div[dir=auto]      ...and, for SHORT posts, the tweet text
      └─ div.gap-3      media, quote, buttons
```

The source userstyle dissolves `div.flex-1` and moves its `:first-child` (the
name row) to column 2. On the old markup the name row held only the name. On
the current markup it also holds the tweet text for short posts, so that rule
drags the text into column 2 and the text never regains full width. The fix is
to dissolve `div.gap-0.5` too and place only `div.post-actions` in column 2,
sending `div[dir=auto]` to `grid-column: 1 / -1`.

Measured: with the naive rule the text stays 520px wide in a 568px row, i.e.
identical to no rule at all. With the fix it is 568px.

### Action row pills

X lays the engagement pills out as `flex: 1 1 0%`, so all four are 115px and
each icon floats in the middle of empty space. The userstyle's
`flex: 0 0 auto; width: auto` is what makes them hug their own content, which
is the "no fixed widths, even spacing" its comment describes. Measured widths
go from `[115, 115, 115, 115, 78]` to `[61, 72, 69, 75, 80]`.

## Local server

`bash start.sh` runs `serve.py` on port 12002 (local only) for testing before
publishing. Not needed for delivery.
