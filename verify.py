"""Browser-level verification of the filter list.

Mirrors what Brave does, end to end:

  1. adblock-rust parses the list and returns hide_selectors plus
     procedural_actions. The harness must be built with the css-validation
     feature, because that is what Brave uses; without it the engine does not
     split procedural operators into steps, and the procedural path silently
     degrades into a single opaque css-selector step that no browser can run.

  2. Playwright serves the captured real x.com markup at https://x.com/home so
     that location.pathname is right for :matches-path. The capture is the
     server-rendered document; its <script> tags are stripped before serving so
     React cannot boot, find no API, and blank the page. JavaScript stays
     enabled, because the harness itself is JavaScript.

  3. Hide selectors are injected the way Brave's kHideSelectorsInjectScript
     does (one insertRule per selector, invalid ones skipped), then Brave's own
     operator set runs over the procedural actions.

  4. Computed styles are compared before and after, so a rule that does nothing
     cannot pass.
"""
import json
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

HARNESS = "/tmp/abltest/target/release/abltest"
LIST = "/workspace/x-tweaks/x-tweaks-brave.txt"
FIXTURE = "/workspace/x-tweaks/_fixtures/home.html"
NAV_HARNESS = "/workspace/x-tweaks/_fixtures/nav-harness.html"
URL = "https://x.com/home"

# Brave's operator implementations, following
# components/cosmetic_filters/resources/data/procedural_filters.ts
BRAVE_JS = r"""
window.__braveApply = (filters) => {
  const extractValue = (text, needle = 0) => {
    const quoted = text[needle] === '"'
    let end
    if (quoted) { needle += 1; end = text.length - 1 } else { end = text.length }
    return text.slice(needle, end)
  }
  const testMatches = (test, value, exact) => {
    if (test[0] === '/') {
      const parts = test.split('/')
      return value.match(new RegExp(parts[1], parts[2])) !== null
    }
    if (test === '') return value.trim() === ''
    return exact ? value === test : value.includes(test)
  }
  const ops = {
    'css-selector': (arg, el) => {
      const t = arg.trimStart()
      if (t.startsWith('+')) {
        const n = el.nextElementSibling
        return n && n.matches(t.slice(1).trim()) ? [n] : []
      }
      if (t.startsWith('~')) {
        const out = []
        let n = el.nextElementSibling
        while (n) { if (n.matches(t.slice(1).trim())) out.push(n); n = n.nextElementSibling }
        return out
      }
      if (t.startsWith('>')) {
        return [...el.children].filter(c => c.matches(t.slice(1).trim()))
      }
      if (arg.startsWith(' ')) return [...el.querySelectorAll(':scope ' + t)]
      return el.matches(arg) ? [el] : []
    },
    'has': (arg, el) => el.querySelector(arg) ? [el] : [],
    'has-text': (arg, el) => {
      const v = extractValue(arg)
      return testMatches(v, el.innerText || '') ? [el] : []
    },
    'upward': (arg, el) => {
      let n = parseInt(arg, 10), cur = el
      while (n > 0 && cur) { cur = cur.parentElement; n-- }
      return cur ? [cur] : []
    },
    'xpath': (arg, el) => {
      const r = document.evaluate(arg, el, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null)
      const out = []
      for (let i = 0; i < r.snapshotLength; i++) out.push(r.snapshotItem(i))
      return out
    },
    'matches-path': (arg, el) => {
      const pq = location.pathname + location.search
      return testMatches(arg, pq, true) ? [el] : []
    },
    'matches-attr': (arg, el) => {
      const eq = arg.indexOf('=')
      if (eq < 0) return el.hasAttribute(arg) ? [el] : []
      return (el.getAttribute(arg.slice(0, eq)) || '') === arg.slice(eq + 1) ? [el] : []
    },
    'min-text-length': (arg, el) =>
      (el.textContent || '').length >= parseInt(arg, 10) ? [el] : [],
    'not': (arg, el) => el.matches(arg) ? [] : [el],
  }
  const results = []
  for (const {selector, action} of filters) {
    try {
      let matches, start
      if (selector[0].type === 'css-selector') {
        const t = selector[0].arg.trimStart()
        // A leading combinator applies to the previous step's results, so the
        // css-selector step has to run per element rather than once globally.
        if (t.startsWith('>') || t.startsWith('+') || t.startsWith('~')) {
          matches = [...document.querySelectorAll('*')]
          start = 0
        } else {
          matches = [...document.querySelectorAll(selector[0].arg)]
          start = 1
        }
      } else { matches = [...document.querySelectorAll('*')]; start = 0 }
      for (let i = start; i < selector.length; i++) {
        const step = selector[i]
        const fn = ops[step.type]
        if (!fn) { matches = []; break }
        const next = []
        for (const el of matches) next.push(...fn(step.arg, el))
        matches = next
      }
      for (const el of matches) {
        const style = (action && action.type === 'style')
          ? action.arg : 'display: none !important'
        const cur = el.getAttribute('data-brave-style') || ''
        el.setAttribute('data-brave-proc', '')
        el.setAttribute('data-brave-style', (cur ? cur + ';' : '') + style)
        results.push({style, tag: el.tagName})
      }
    } catch (e) { results.push({error: String(e)}) }
  }
  const styles = new Set()
  for (const r of results) if (r.style) styles.add(r.style)
  let css = ''
  for (const style of styles) {
    css += `[data-brave-proc][data-brave-style*="${style.replace(/"/g, '\\"')}"]{${style}}\n`
  }
  const s = document.createElement('style')
  s.textContent = css
  document.head.appendChild(s)
  return results
}
"""

PROBE = """() => {
    const cs = (el) => el ? getComputedStyle(el) : null
    const q = (s) => document.querySelector(s)
    const out = {}
    const text = q('article div[dir="auto"][class*="whitespace-pre-wrap"]')
    out.tweetTextSize = text ? cs(text).fontSize : null
    out.tweetTextLine = text ? cs(text).lineHeight : null
    const name = q('article a[href] div[class*="font-bold"]')
    out.displayNameSize = name ? cs(name).fontSize : null
    const row = q('article div:has(> [data-engagement-action])')
    out.rowDisplay = row ? cs(row).display : null
    out.rowJustify = row ? cs(row).justifyContent : null
    const hdr = q('div[class*="backdrop-blur"][class*="sticky"]')
    out.headerBlur = hdr ? cs(hdr).backdropFilter : null
    const feed = q('article div:has(> div[class*="w-10"] > div > a > div[class*="x-avatar"])')
    out.feedDisplay = feed ? cs(feed).display : null
    out.feedCols = feed ? cs(feed).gridTemplateColumns : null
    // visible-element counts, so a hide rule can be proven to have worked
    const visible = (s) => [...document.querySelectorAll(s)]
        .filter(e => cs(e).display !== 'none' && e.offsetParent !== null).length
    out.vGrokLinks = visible('a[href="/i/grok"], a[href*="/i/grok"]')
    out.vPremiumLinks = visible('a[href*="/i/premium"], a[href*="/premium"]')
    out.vArticles = visible('article')
    out.articles = document.querySelectorAll('article').length
    out.engagementRows = document.querySelectorAll('[data-engagement-action]').length
    return out
}"""


def engine_dump(url):
    out = subprocess.run([HARNESS, LIST, url], capture_output=True, text=True, check=True)
    hide, proc, section = [], [], None
    for line in out.stdout.splitlines():
        if line.startswith("--- HIDE"):
            section = "hide"
        elif line.startswith("--- PROC"):
            section = "proc"
        elif line.startswith("  "):
            (hide if section == "hide" else proc).append(line.strip())
    return hide, [json.loads(p) for p in proc]


def fixture_html():
    """The capture with <script> removed, so React cannot blank the page."""
    raw = open(FIXTURE, encoding="utf-8").read()
    return re.sub(r"<script\b[^>]*>.*?</script>", "", raw, flags=re.S | re.I)


def new_page(ctx):
    body = fixture_html()
    pg = ctx.new_page()
    pg.route(URL, lambda r: r.fulfill(
        status=200, content_type="text/html; charset=utf-8", body=body))
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    return pg


def main():
    hide, proc = engine_dump(URL)
    print(f"engine: {len(hide)} hide selectors, {len(proc)} procedural actions")

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/chromium",
                              args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(viewport={"width": 1280, "height": 900})

        # 1. hide selectors must all be valid CSS
        pg = ctx.new_page()
        pg.goto("about:blank")
        pg.set_content("<html><body></body></html>")
        invalid = pg.evaluate(
            "(s) => s.filter(x => { try { document.createDocumentFragment()"
            ".querySelector(x); return false } catch(e) { return true } })", hide)
        print(f"invalid hide selectors: {len(invalid)}")
        for s in invalid:
            print("   INVALID:", s)

        # 2. baseline, no list applied
        pg2 = new_page(ctx)
        before = pg2.evaluate(PROBE)
        articles = before["articles"]
        print(f"fixture: {articles} articles, {before['engagementRows']} engagement rows")

        # 3. inject hide selectors the way Brave does
        pg2.evaluate("""(sels) => {
            const sheet = new CSSStyleSheet()
            document.adoptedStyleSheets = [sheet, ...document.adoptedStyleSheets]
            let idx = 0
            window.__bad = []
            for (const s of sels) {
                try { sheet.insertRule(`${s}{display:none !important}`, idx++) }
                catch (e) { window.__bad.push(s) }
            }
        }""", hide)
        pg2.add_script_tag(content=BRAVE_JS)
        applied = pg2.evaluate("(f) => window.__braveApply(f)", proc)
        after = pg2.evaluate(PROBE)

        print(f"procedural matches: {len(applied)}")
        for a in applied:
            if a.get("error"):
                print("   ERROR:", a["error"])
        bad = pg2.evaluate("() => window.__bad")
        print(f"bad hide injections: {len(bad)}")
        for s in bad:
            print("   BAD:", s)

        print("\n--- computed styles: before -> after ---")
        for k in before:
            b_, a_ = before[k], after[k]
            flag = "" if b_ == a_ else "   <== CHANGED"
            print(f"   {k:16} {str(b_):22} -> {str(a_):22}{flag}")

        print("\n--- assertions ---")
        fails = []
        def expect(cond, msg):
            print(("   PASS  " if cond else "   FAIL  ") + msg)
            if not cond:
                fails.append(msg)

        expect(not invalid, "every hide selector is valid CSS")
        expect(not bad, "Brave never rejected a hide selector")
        expect(not [a for a in applied if a.get("error")],
               "every procedural action executed without error")
        expect(after["tweetTextSize"] == "17px",
               f"tweet text is 17px (got {after['tweetTextSize']})")
        expect(after["tweetTextLine"] == "24.65px",
               f"tweet text line-height is 1.45x17px (got {after['tweetTextLine']})")
        expect(after["displayNameSize"] == "16px",
               f"display name is 16px (got {after['displayNameSize']})")
        expect(after["rowDisplay"] == "flex",
               f"action row is flex (got {after['rowDisplay']})")
        expect(after["rowJustify"] == "space-between",
               f"action row is space-between (got {after['rowJustify']})")
        expect(after["headerBlur"] == "none",
               f"header blur removed (got {after['headerBlur']})")
        expect(after["feedDisplay"] == "grid",
               f"home feed row is grid (got {after['feedDisplay']})")
        expect(after["articles"] == articles and articles > 0,
               f"fixture articles intact ({after['articles']}/{articles})")
        expect(after["vArticles"] == before["vArticles"] and articles > 0,
               "no article was hidden by accident")

        # 4. declutter rules, against the synthetic logged-in nav
        print("\n--- declutter (synthetic logged-in nav) ---")
        pg3 = ctx.new_page()
        pg3.route(URL, lambda r: r.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body=open(NAV_HARNESS, encoding="utf-8").read()))
        pg3.goto(URL, wait_until="domcontentloaded")
        pg3.wait_for_timeout(500)
        pg3.evaluate("""(sels) => {
            const sheet = new CSSStyleSheet()
            document.adoptedStyleSheets = [sheet, ...document.adoptedStyleSheets]
            let idx = 0
            window.__bad = []
            for (const s of sels) {
                try { sheet.insertRule(`${s}{display:none !important}`, idx++) }
                catch (e) { window.__bad.push(s) }
            }
        }""", hide)
        pg3.add_script_tag(content=BRAVE_JS)
        nav_applied = pg3.evaluate("(f) => window.__braveApply(f)", proc)

        state = pg3.evaluate("""() => {
            const out = {}
            for (const el of document.querySelectorAll('[data-probe]')) {
                out[el.dataset.probe] = {
                    display: getComputedStyle(el).display,
                    want: el.dataset.want === '1',
                }
            }
            return out
        }""")
        removed = sorted(k for k, v in state.items() if not v["want"] and v["display"] == "none")
        survived = sorted(k for k, v in state.items() if not v["want"] and v["display"] != "none")
        controls = sorted(k for k, v in state.items() if v["want"])
        print(f"   nav procedural matches: {len(nav_applied)}")
        print(f"   removed ({len(removed)}): {', '.join(removed)}")
        print(f"   controls kept: {', '.join(controls)}")
        if survived:
            print(f"   NOT removed ({len(survived)}): {', '.join(survived)}")

        # every href-based declutter entry, plus the menu-role ones, must go
        must_remove = [k for k, v in state.items() if not v["want"]]
        expect(not [k for k in must_remove if k not in removed],
               "every declutter entry is hidden")
        expect(all(state[k]["display"] != "none" for k in controls),
               "every control entry survives")
        b.close()

    print(f"\n{'ALL CHECKS PASSED' if not fails else str(len(fails)) + ' CHECK(S) FAILED'}")
    sys.exit(1 if fails else 0)


main()
