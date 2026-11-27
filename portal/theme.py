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
#filters label > span, #filters .block > label span {{
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

/* ---------- stat tiles: one surface each ---------- */
#stats {{ gap: 10px; margin: 18px 0 16px; }}
.stat {{
  background: var(--background-fill-secondary);
  border: 1px solid var(--border-color-primary);
  border-top: 2px solid {EMBER};
  border-radius: 3px 3px 9px 9px;
  padding: 13px 15px !important;
  min-width: 0;
}}
.stat .num {{
  display: block; font-size: 24px; font-weight: 600;
  line-height: 1.15; letter-spacing: -0.6px; color: var(--body-text-color);
}}
.stat .cap {{
  display: block; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.9px; color: var(--body-text-color-subdued); margin-top: 4px;
}}

/* ---------- filter strip ---------- */
#filters {{
  background: var(--background-fill-secondary);
  border: 1px solid var(--border-color-primary);
  border-radius: 10px;
  padding: 14px 16px !important; gap: 14px;
  align-items: end; margin-bottom: 2px;
}}
#result-count .prose p {{
  margin: 14px 2px 10px !important; font-size: 12.5px;
  color: var(--body-text-color-subdued);
}}

/* ---------- idea table: one row per idea, opens in place ---------- */
#idea-table-wrap {{ margin-top: 2px; }}
.it-count {{
  margin: 14px 2px 10px !important; font-size: 12.5px;
  color: var(--body-text-color-subdued);
}}
.idea-table {{
  border: 1px solid var(--border-color-primary);
  border-radius: 10px;
  overflow: hidden;
  background: var(--background-fill-secondary);
}}
/* the five columns every row shares */
.it-head, .idea-table summary {{
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr) 160px 132px 104px;
  gap: 14px; align-items: center;
  padding: 10px 16px;
}}
.it-head {{
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.9px;
  font-weight: 650; color: var(--body-text-color-subdued);
  border-bottom: 1px solid var(--border-color-primary);
  background: var(--block-background-fill);
}}

.it-row {{ border-bottom: 1px solid var(--border-color-primary); }}
.it-row:last-child {{ border-bottom: none; }}
.idea-table summary {{
  cursor: pointer; list-style: none; position: relative;
  border-left: 3px solid transparent; padding-left: 13px;
  transition: background 0.12s, border-color 0.12s;
}}
.idea-table summary::-webkit-details-marker {{ display: none; }}
.idea-table summary:hover {{ background: var(--block-background-fill); }}
.it-row[open] > summary {{
  background: var(--block-background-fill);
  border-left-color: {EMBER};
}}
/* chevron, drawn in CSS so the row needs no icon font */
.idea-table summary::after {{
  content: ""; position: absolute; right: 16px; top: 50%;
  width: 6px; height: 6px; margin-top: -4px;
  border-right: 1.6px solid var(--body-text-color-subdued);
  border-bottom: 1.6px solid var(--body-text-color-subdued);
  transform: rotate(45deg); transition: transform 0.15s;
}}
.it-row[open] > summary::after {{
  transform: rotate(-135deg); margin-top: -1px;
  border-color: {EMBER};
}}

.it-id {{
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--body-text-color-subdued);
}}
.it-title {{
  font-size: 14px; font-weight: 550; color: var(--body-text-color);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  padding-right: 18px;
}}
.it-author, .it-dept, .it-date {{
  font-size: 12.5px; color: var(--body-text-color-subdued);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.it-dept {{ text-transform: capitalize; }}
.it-rev {{
  display: inline-block; margin-left: 8px; padding: 1px 7px;
  border: 1px solid {EMBER}; color: {EMBER};
  border-radius: 20px; font-size: 10px; font-weight: 650;
  vertical-align: middle;
}}

/* ---------- the opened row ---------- */
.it-body {{
  padding: 4px 20px 20px 46px;
  border-left: 3px solid {EMBER};
  background: var(--block-background-fill);
}}
.it-body dl {{ margin: 0; display: grid; gap: 11px; }}
.it-field {{
  display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 16px;
  align-items: baseline;
}}
.it-body dt {{
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.9px;
  font-weight: 650; color: {EMBER}; padding-top: 2px;
}}
.it-body dd {{
  margin: 0; font-size: 13.5px; line-height: 1.65;
  color: var(--body-text-color);
}}
.it-stamp {{
  margin: 16px 0 0 !important; padding-top: 11px;
  border-top: 1px solid var(--border-color-primary);
  font-size: 11.5px; color: var(--body-text-color-subdued);
}}

/* ---------- empty state ---------- */
.it-empty {{
  text-align: center; padding: 48px 20px;
  border: 1px dashed var(--border-color-primary);
  border-radius: 12px; background: var(--background-fill-secondary);
}}
.it-empty p {{ margin: 4px 0 !important; color: var(--body-text-color-subdued); }}
.it-empty p.t {{ font-size: 15px; color: var(--body-text-color); }}

/* narrow screens: drop the columns that repeat inside the open row */
@media (max-width: 860px) {{
  .it-head, .idea-table summary {{ grid-template-columns: 76px minmax(0,1fr) 92px; }}
  .it-head span:nth-child(3), .it-author,
  .it-head span:nth-child(4), .it-dept {{ display: none; }}
  .it-body {{ padding-left: 20px; }}
  .it-field {{ grid-template-columns: 1fr; gap: 2px; }}
}}

/* ---------- chat page ---------- */
#chat-hint .prose p {{
  margin: 0 0 12px !important; font-size: 13.5px;
  color: var(--body-text-color-subdued);
}}
#submit-row {{ margin-top: 10px; }}

@media (max-width: 760px) {{
  #stats {{ flex-direction: column; }}
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
