"""One look for the whole portal: a Gradio theme, the app CSS, and the login page.

Kept in one file so the chat page, the dashboard and the login screen cannot
drift apart.

Palette is deliberately warm - burnt orange on warm grey, not the default
indigo-on-slate every Gradio app ships with. Colours are written against
Gradio's own CSS variables (--body-text-color, --border-color-primary,
--block-background-fill, ...) wherever possible, so the portal follows the
visitor's light or dark preference instead of fighting it.
"""

import gradio as gr

# orange + stone: stone is a warm grey, so even the neutral surfaces carry a
# little warmth instead of reading blue.
THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.orange,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.stone,
    radius_size=gr.themes.sizes.radius_md,
    spacing_size=gr.themes.sizes.spacing_md,
)
# No custom font: Gradio compares themes by font object, so a plain string
# tuple raises AttributeError in launch(). The Soft theme's own stack is a
# good system stack already, and it needs no network.

# Shared ink values. Defined once here and reused by the app CSS and the login
# page, which cannot see each other's stylesheets.
EMBER = "#c2410c"        # burnt orange, the one strong accent
EMBER_SOFT = "#fff3ea"   # its tint, for light surfaces
SAND = "#f7f4f0"         # warm page ground

CSS = f"""
/* ---------- page frame ---------- */
.gradio-container {{ max-width: 1120px !important; margin: 0 auto !important; }}
/* The dashboard table needs the full width. Gradio otherwise sizes the page to
   its content, and a table that scrolls inside its card asks for none. */
.gradio-container:has(#filters), .app:has(#filters) {{
  width: 100% !important; max-width: 1440px !important;
}}
footer {{ display: none !important; }}

/* Gradio paints every block with its own background, border and label pill.
   Inside our own cards and tiles that produces a box within a box, so the
   chrome is switched off by overriding Gradio's variables on the container
   rather than fighting each child selector. */
.flat, .flat * {{
  --block-background-fill: transparent;
  --block-border-width: 0px;
  --block-shadow: none;
  --panel-background-fill: transparent;
}}
.flat > div, .flat .block, .flat .form {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}}

/* ---------- labels: subtle text, not a coloured pill ---------- */
.gradio-container {{
  --block-label-background-fill: transparent;
  --block-label-border-color: transparent;
  --block-label-text-color: var(--body-text-color-subdued);
}}
#filters label > span, #filters .block > label span,
#filters [data-testid="block-info"] {{
  background: transparent !important;
  color: var(--body-text-color-subdued) !important;
  font-size: 11px !important;
  font-weight: 650 !important;
  letter-spacing: 0.7px;
  text-transform: uppercase;
  padding: 0 0 5px !important;
  border: none !important;
}}

/* ---------- top bar ---------- */
#portal-bar {{
  border-bottom: 1px solid var(--border-color-primary);
  padding: 2px 0 14px;
  margin-bottom: 22px;
  align-items: center;
}}
#portal-bar .prose h1 {{
  font-size: 19px !important; margin: 0 !important;
  letter-spacing: -0.3px; font-weight: 650;
}}
#portal-bar .prose h1::before {{
  content: ""; display: inline-block;
  width: 8px; height: 8px; border-radius: 2px;
  background: {EMBER}; margin-right: 9px; vertical-align: middle;
}}
#portal-brand .prose p {{
  margin: 3px 0 0 17px !important; font-size: 11px;
  letter-spacing: 1px; text-transform: uppercase;
  color: var(--body-text-color-subdued);
}}
/* the signed-in line is sentence case and stays on one line */
#portal-who .prose p {{
  margin: 0 !important; font-size: 13px; text-align: right;
  text-transform: none !important; letter-spacing: 0 !important;
  color: var(--body-text-color-subdued); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}}
#portal-who strong {{ color: var(--body-text-color); font-weight: 600; }}

/* ---------- page headings ---------- */
.page-head h2 {{
  font-size: 23px !important; margin: 0 0 5px !important;
  letter-spacing: -0.4px; font-weight: 650;
}}
.page-head p {{
  margin: 0 !important; color: var(--body-text-color-subdued);
  font-size: 14px; max-width: 66ch; line-height: 1.6;
}}

/* ---------- colours of the listing, lighter on dark ground ---------- */
.tiles, .ideas {{
  --tone-blue: #1f5fa8; --tone-green: #2e7d32; --tone-amber: #a66a14;
  --tone-red: #b03a2e; --tone-purple: #7b4f9e; --tone-grey: #6b6560;
}}
/* Two rules: Gradio rewrites selectors, and mishandles a second .dark in a list. */
.dark .tiles {{
  --tone-blue: #85b7f0; --tone-green: #7fcf85; --tone-amber: #e8b45c;
  --tone-red: #f08a7e; --tone-purple: #c39be0; --tone-grey: #b8b0a8;
}}
.dark .ideas {{
  --tone-blue: #85b7f0; --tone-green: #7fcf85; --tone-amber: #e8b45c;
  --tone-red: #f08a7e; --tone-purple: #c39be0; --tone-grey: #b8b0a8;
}}
.blue {{ --tone: var(--tone-blue); }}
.green {{ --tone: var(--tone-green); }}
.amber {{ --tone: var(--tone-amber); }}
.red {{ --tone: var(--tone-red); }}
.purple {{ --tone: var(--tone-purple); }}
.grey {{ --tone: var(--tone-grey); }}

/* tiles and table line up with the filter strip */
.html-container:has(.tiles), .html-container:has(.ideas) {{ padding: 0 !important; }}

/* ---------- stat tiles ---------- */
.tiles {{
  display: grid; gap: 12px; margin: 14px 0;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}}
.tile {{
  background: var(--block-background-fill);
  border: 1px solid var(--border-color-primary);
  border-radius: 12px; padding: 13px 18px;
}}
.tile b {{
  display: block; font-size: 28px; line-height: 1.2; font-weight: 700;
  color: var(--tone, var(--body-text-color));
}}
.tile span {{ font-size: 12.5px; color: var(--body-text-color-subdued); }}

/* ---------- filter strip ---------- */
#filters {{
  background: var(--background-fill-secondary);
  border: 1px solid var(--border-color-primary);
  border-radius: 10px;
  padding: 14px 16px !important; gap: 14px;
  align-items: end; margin-bottom: 2px;
}}
#filters .form {{ background: transparent; border: none; box-shadow: none; }}
#result-count .prose p {{
  margin: 14px 2px 10px !important; font-size: 12.5px;
  color: var(--body-text-color-subdued);
}}

/* ---------- idea table: one white card, a row per idea ---------- */
.ideas {{
  background: var(--block-background-fill);
  border: 1px solid var(--border-color-primary);
  border-radius: 14px; padding: 4px 14px 8px;
  overflow-x: auto; color: var(--body-text-color); font-size: 13.5px;
  /* a wide table scrolls inside its card instead of widening the page */
  contain: inline-size;
}}
.ideas .grid {{ min-width: calc(826px + var(--metrics) * 102px); }}
.ideas .line {{
  display: grid; align-items: center; column-gap: 10px; padding: 10px 6px;
  grid-template-columns:
    76px minmax(190px, 1fr) 98px repeat(var(--metrics), 92px)
    104px 132px 110px 44px;
}}
.ideas .head {{
  font-size: 12px; font-weight: 650; color: var(--body-text-color-subdued);
  border-bottom: 1px solid var(--border-color-primary); align-items: end;
}}
.ideas .head small {{ display: block; font-weight: 400; opacity: .75; }}
.ideas .head .sorted {{ color: {EMBER}; }}
.ideas .idea {{ border-bottom: 1px solid var(--border-color-primary); }}
.ideas .idea:last-child {{ border-bottom: none; }}
.ideas summary {{ cursor: pointer; list-style: none; }}
.ideas summary::-webkit-details-marker {{ display: none; }}
.ideas summary.line:hover, .ideas .idea[open] > summary {{
  background: color-mix(in srgb, {EMBER} 7%, transparent);
}}
.ideas summary:focus-visible {{ outline: 2px solid {EMBER}; outline-offset: -2px; }}
.ideas .id {{ font-family: var(--font-mono); font-size: 12px; white-space: nowrap; }}
.ideas .id::before {{
  content: "▸"; display: inline-block; width: 12px; color: {EMBER};
}}
.ideas .idea[open] .id::before {{ content: "▾"; }}
.ideas .title b {{ display: block; font-weight: 600; line-height: 1.35; }}
.ideas small {{
  display: block; font-size: 11.5px; color: var(--body-text-color-subdued);
}}
.ideas .score {{
  display: grid; grid-template-columns: 52px auto; align-items: center;
  column-gap: 8px;
}}
.ideas .score small, .ideas .score .muted {{ grid-column: 1 / -1; }}
.ideas .score b {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
.ideas .meter {{
  height: 7px; border-radius: 7px; overflow: hidden;
  background: var(--border-color-primary);
}}
.ideas .meter i {{ display: block; height: 100%; background: var(--tone-blue); }}
.ideas .muted {{ color: var(--body-text-color-subdued); font-size: 12px; }}
.ideas .pill {{
  display: inline-block; font-size: 11.5px; font-weight: 600; line-height: 1.4;
  padding: 2px 9px; border-radius: 20px; color: var(--tone);
  background: color-mix(in srgb, var(--tone) 13%, transparent);
}}

/* the opened row: the idea on the left, the reasons on the right */
.ideas .detail {{
  display: grid; gap: 28px; padding: 6px 20px 20px 24px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  border-left: 3px solid {EMBER}; margin: 6px 0 10px;
}}
.ideas .detail h4, .ideas .detail h5 {{
  margin: 12px 0 3px; color: {EMBER}; font-weight: 650;
}}
.ideas .detail h4 {{ font-size: 13.5px; }}
.ideas .metric {{ border-bottom: 1px solid var(--border-color-primary); }}
.ideas .metric > summary {{ padding: 8px 0; font-weight: 650; color: {EMBER}; }}
.ideas .metric > summary::before {{ content: "▸ "; }}
.ideas .metric[open] > summary::before {{ content: "▾ "; }}
.ideas .metric[open] {{ padding-bottom: 8px; }}
.ideas .detail h5 {{
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .9px;
}}
.ideas .detail p {{ margin: 2px 0; line-height: 1.6; overflow-wrap: anywhere; }}
.ideas .detail ul {{ margin: 4px 0; padding-left: 18px; list-style: disc; }}
.ideas .detail li {{ margin: 3px 0; line-height: 1.55; overflow-wrap: anywhere; }}
.ideas .detail hr {{
  border: none; border-top: 1px solid var(--border-color-primary); margin: 14px 0 4px;
}}
.ideas-note {{ font-size: 12px; color: var(--body-text-color-subdued); margin: 8px 4px; }}
#ranking-note .prose p {{
  margin: 6px 2px !important; font-size: 12.5px;
  color: var(--body-text-color-subdued);
}}

/* ---------- empty state ---------- */
.empty {{
  text-align: center; padding: 46px 20px !important;
  border: 1px dashed var(--border-color-primary) !important;
  border-radius: 12px !important;
  background: var(--background-fill-secondary) !important;
}}
.empty .prose p {{ margin: 4px 0 !important; color: var(--body-text-color-subdued); }}
.empty .prose p:first-child {{ font-size: 15px; color: var(--body-text-color); }}

/* ---------- chat page ---------- */
#chat-hint .prose p {{
  margin: 0 0 12px !important; font-size: 13.5px;
  color: var(--body-text-color-subdued);
}}
#submit-row {{ margin-top: 10px; }}

@media (max-width: 760px) {{
  .ideas .detail {{ grid-template-columns: 1fr; }}
  #portal-who .prose p {{ text-align: left; white-space: normal; }}
}}
"""


def login_message(commit_time: str) -> str:
    """The login screen.

    Gradio's login page is rendered separately and never sees the `css=`
    stylesheet, but it does render whatever HTML `auth_message` contains - so
    the styles have to travel with the markup. That is also why the selectors
    below reach up into Gradio's own login form with :has() and sibling
    combinators rather than using classes of our own.
    """
    return f"""
<style>
  /* warm the page ground behind the card */
  body {{ background: {SAND}; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #17120f; }} }}

  .auth-message, .auth-message * {{ text-align: left; }}
  .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 2px; }}
  .brand .mark {{
    width: 26px; height: 26px; border-radius: 7px; flex: none;
    background: linear-gradient(140deg, #f59e0b, {EMBER});
  }}
  .brand .name {{
    font-size: 19px; font-weight: 650; letter-spacing: -0.3px; line-height: 1;
  }}
  .brand .org {{
    font-size: 10.5px; letter-spacing: 1.1px; text-transform: uppercase;
    opacity: 0.6; margin-top: 3px;
  }}
  .tagline {{
    font-size: 14px; line-height: 1.6; opacity: 0.82;
    margin: 14px 0 16px; max-width: 42ch;
  }}
  .hint {{
    font-size: 12.5px; line-height: 1.65;
    border-left: 2px solid {EMBER}; padding: 2px 0 2px 11px;
    margin: 0 0 4px; opacity: 0.78;
  }}
  .hint code {{
    font-size: 12px; padding: 1px 5px; border-radius: 4px;
    background: rgba(194,65,12,0.12); color: {EMBER};
  }}
  .built {{
    position: fixed; bottom: 1.1rem; left: 0; right: 0;
    text-align: center; font-size: 11px; letter-spacing: 0.4px; opacity: 0.45;
  }}
</style>
<div class="brand" style="display:flex;align-items:center;gap:10px;margin-bottom:2px">
  <span class="mark" style="width:26px;height:26px;border-radius:7px;flex:none;
        background:linear-gradient(140deg,#f59e0b,{EMBER})"></span>
  <span>
    <div class="name" style="font-size:19px;font-weight:650;letter-spacing:-0.3px;line-height:1">Idea Portal</div>
    <div class="org" style="font-size:10.5px;letter-spacing:1.1px;text-transform:uppercase;opacity:.6;margin-top:3px">Brambleworks GmbH</div>
  </span>
</div>
<p class="tagline" style="font-size:14px;line-height:1.6;opacity:.82;margin:14px 0 16px;max-width:42ch">
  Tell us how a process could work better. An assistant asks the follow-up
  questions, you check the draft, and nothing is stored until you say so.
</p>
<p class="hint" style="font-size:12.5px;line-height:1.65;border-left:2px solid {EMBER};
   padding:2px 0 2px 11px;margin:0 0 4px;opacity:.78">
  Employees sign in with their <strong>last name in lowercase</strong>.<br>
  The innovation team signs in as <code style="font-size:12px;padding:1px 5px;border-radius:4px;
  background:rgba(194,65,12,.12);color:{EMBER}">innovation</code>.
</p>
<span class="built" style="position:fixed;bottom:1.1rem;left:0;right:0;text-align:center;font-size:11px;letter-spacing:.4px;opacity:.45">Latest commit: {commit_time}</span>
"""
