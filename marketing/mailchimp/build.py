#!/usr/bin/env python3
"""Build LBA Mailchimp e-blasts from shared brand chrome.

Each campaign is a spec in CAMPAIGNS: a preheader plus a list of sections. The
header, footer, palette, type scale and responsive rules live here once, so
every send renders identically and a design change is a one-line edit.

Sections sit on one of three grounds — white, Light Gray, or LBA Blue reversed.
The blue band is the emphasis device: one per email, on whatever that send is
actually asking for.

Run:  python3 build.py
"""
import os, re, shutil, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "_assets")

# --- LBA Brand Guidelines, 08/31/26 -----------------------------------------
BLUE, TEAL = "#204396", "#008C8C"
CHAR, GRAY = "#333333", "#6B7280"
PANEL, WHITE = "#F2F4F5", "#FFFFFF"
RULE, PANEL_EDGE = "#E3E6E9", "#DCE0E4"

# Reversed palette for the blue band. Brand teal on LBA Blue is 2.23:1 and
# fails outright, so kickers and bullets there use a light tint of it. Measured
# against #204396: white 9.11, body 7.55, kicker 5.52, muted 5.32.
R_KICK, R_BODY, R_MUTED = "#7FD8D8", "#E4EAF6", "#B9C6E4"

# One dark ground, used only by the 9/17 partner invite so the email sits with
# the event's own black-and-blue artwork instead of fighting it. The flyer's
# field is pure black, so the ground is too, and the two meet with no seam.
# Measured against #000000: white 21.00, body 12.28, accent 7.37, muted 7.00.
SPACE, S_CARD = "#000000", "#0E1422"
S_ACCENT, S_BODY, S_MUTED, S_CARD_INK = "#4C9AFF", "#B8C7E0", "#8296B8", "#E8EEF9"

FONT = "'Proxima Nova','Helvetica Neue',Helvetica,Arial,sans-serif"
BODY = "font-size:16px;line-height:27px"
SMALL = "font-size:15px;line-height:25px"


def ink(ground):
    """Colour roles for a given section ground."""
    if ground == "blue":
        return dict(bg=BLUE, kick=R_KICK, head=WHITE, body=R_BODY, strong=WHITE,
                    mark=R_KICK, muted=R_MUTED, card=WHITE, card_ink=CHAR,
                    link=WHITE, btn_bg=WHITE, btn_ink=BLUE, hair="#4763A9")
    if ground == "space":
        return dict(bg=SPACE, kick=S_ACCENT, head=WHITE, body=S_BODY, strong=WHITE,
                    mark=S_ACCENT, muted=S_MUTED, card=S_CARD, card_ink=S_CARD_INK,
                    link=S_ACCENT, btn_bg=S_ACCENT, btn_ink=SPACE, hair="#1E2740")
    bg = PANEL if ground == "tint" else WHITE
    return dict(bg=bg, kick=TEAL, head=BLUE, body=CHAR, strong=BLUE,
                mark=TEAL, muted=GRAY, card=(WHITE if ground == "tint" else PANEL),
                card_ink=CHAR, link=BLUE, btn_bg=BLUE, btn_ink=WHITE, hair=PANEL_EDGE)


def head_html(title, preheader):
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light" />
<meta name="supported-color-schemes" content="light" />
<title>{title}</title>
<!--[if mso]>
<xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
<![endif]-->
<style type="text/css">
  body,table,td,a{{font-family:{FONT};-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}}
  table,td{{mso-table-lspace:0pt;mso-table-rspace:0pt;}}
  img{{-ms-interpolation-mode:bicubic;border:0;height:auto;line-height:100%;outline:none;text-decoration:none;display:block;}}
  table{{border-collapse:collapse!important;}}
  body{{margin:0!important;padding:0!important;width:100%!important;background-color:#DDE3EA;}}
  a{{color:{BLUE};}}
  .d1{{font-size:34px!important;line-height:41px!important;}}
  @media screen and (max-width:620px){{
    .wrap{{width:100%!important;}}
    .px{{padding-left:24px!important;padding-right:24px!important;}}
    .d1{{font-size:26px!important;line-height:33px!important;}}
    .lba-h2{{font-size:19px!important;line-height:26px!important;}}
    .btn a{{display:block!important;}}
    .fstack{{display:block!important;width:100%!important;max-width:100%!important;text-align:center!important;padding:0 0 20px 0!important;}}
    .fstack img{{margin:0 auto!important;}}
    .fcenter table{{margin:0 auto!important;}}
    .hcell{{display:block!important;width:100%!important;max-width:100%!important;padding:0 0 28px 0!important;text-align:center!important;}}
    .hcell img{{margin:0 auto!important;}}
    .gut{{display:none!important;}}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:#DDE3EA;">

<!-- Preview text: shows in the inbox beside the subject line. -->
<div style="display:none;font-size:1px;color:#DDE3EA;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">
  {preheader}
  {'&#847;&zwnj;&nbsp;' * 20}
</div>

<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#DDE3EA;">
<tr><td align="center" style="padding:26px 10px;">

<table role="presentation" class="wrap" border="0" cellpadding="0" cellspacing="0" width="600" style="width:600px;max-width:600px;background-color:{WHITE};">

  <tr>
    <td align="center" class="px" style="padding:28px 32px 22px 32px;background-color:{WHITE};">
      <img src="images/lba-logo.png" width="220" alt="Long Beach Accelerator" style="width:220px;max-width:220px;height:auto;display:block;" />
    </td>
  </tr>
  <tr><td style="font-size:0;line-height:0;height:5px;background-color:{TEAL};">&nbsp;</td></tr>
"""


PERMISSION_OPTIN = "You are receiving this email because you opted in via our website."

FOOT_TMPL = f"""  <tr>
    <td style="background-color:{WHITE};">
      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
        <tr><td class="px" style="padding:36px 40px 0 40px;"><table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0"><tr><td style="border-top:2px solid {BLUE};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
        <tr>
          <td class="px fcenter" style="padding:24px 40px 0 40px;">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:14px;"><a href="https://www.linkedin.com/company/long-beach-accelerator/" target="_blank"><img src="images/icon-linkedin.png" width="44" height="44" alt="LBA Accelerator on LinkedIn" style="display:block;width:44px;height:44px;border:0;" /></a></td>
                <td style="padding-right:14px;"><a href="mailto:info@lbaccelerator.org"><img src="images/icon-email.png" width="44" height="44" alt="Email the Long Beach Accelerator" style="display:block;width:44px;height:44px;border:0;" /></a></td>
                <td><a href="https://lbaccelerator.org" target="_blank"><img src="images/icon-web.png" width="44" height="44" alt="Long Beach Accelerator website" style="display:block;width:44px;height:44px;border:0;" /></a></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td class="px" style="padding:26px 40px 38px 40px;">
            <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
              <tr>
                <td class="fstack" width="230" valign="top" style="padding:6px 0 0 0;">
                  <img src="images/lba-logo.png" width="200" alt="Long Beach Accelerator" style="width:200px;max-width:200px;height:auto;display:block;" />
                </td>
                <td class="fstack" align="right" valign="top" mc:edit="footer_legal" style="font-family:{FONT};font-size:13px;line-height:22px;color:{GRAY};text-align:right;">
                  <p style="margin:0 0 14px 0;">
                    &copy; *|CURRENT_YEAR|* Long Beach Accelerator<br />
                    All rights reserved.<br />
                    {{permission_line}}
                  </p>
                  <p style="margin:0 0 14px 0;">
                    Our mailing address is:<br />
                    Long Beach Accelerator<br />
                    245 E. 3rd St<br />
                    Long Beach, CA 90802
                  </p>
                  <p style="margin:0;">
                    <a href="*|UPDATE_PROFILE|*" style="color:{BLUE};text-decoration:underline;">Update your preferences</a> or
                    <a href="*|UNSUB|*" style="color:{BLUE};text-decoration:underline;">Unsubscribe</a>
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


# --- section shell -----------------------------------------------------------

def section(rows, ground="white", rule_after=True):
    """One band. A solid blue rule closes every section so the seams are explicit."""
    g = ink(ground)
    out = (f'  <tr>\n    <td style="background-color:{g["bg"]};">\n'
           f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
           + "".join(rows) +
           f'      </table>\n    </td>\n  </tr>\n')
    if rule_after:
        out += f'  <tr><td style="font-size:0;line-height:0;height:9px;background-color:{BLUE};">&nbsp;</td></tr>\n'
    return out


def r_image(src, alt, href=None):
    img = (f'<img src="images/{src}" width="600" alt="{alt}" '
           f'style="width:100%;max-width:600px;height:auto;display:block;" />')
    if href:
        img = f'<a href="{href}" target="_blank">{img}</a>'
    return f'        <tr><td align="center" style="font-size:0;line-height:0;">{img}</td></tr>\n' 


def r_text(body, g, edit=None, pad="36px 40px 0 40px"):
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px"{e} style="padding:{pad};font-family:{FONT};{BODY};color:{g["body"]};">\n'
            f'{body}\n        </td></tr>\n')


def r_pad(px=36):
    return f'        <tr><td style="font-size:0;line-height:0;height:{px}px;">&nbsp;</td></tr>\n'


def r_button(label, href, g, invert=False, align="center", pad_top=28):
    """align='left' sits the button in the text column, for buttons placed
    mid-section where a centred one breaks the left-aligned run of copy."""
    bg = g["btn_bg"] if not invert else TEAL
    fg = g["btn_ink"] if not invert else WHITE
    return (f'        <tr><td align="{align}" class="px btn" style="padding:{pad_top}px 40px 0 40px;">\n'
            f'          <table role="presentation" border="0" cellpadding="0" cellspacing="0">\n'
            f'            <tr><td align="center" bgcolor="{bg}" style="border-radius:4px;">\n'
            f'              <a href="{href}" target="_blank" style="display:inline-block;padding:17px 40px;font-family:{FONT};font-size:16px;line-height:20px;font-weight:bold;letter-spacing:0.3px;color:{fg};text-decoration:none;border-radius:4px;">{label}&nbsp;&nbsp;&rarr;</a>\n'
            f'            </td></tr>\n          </table>\n        </td></tr>\n')


def r_card(inner, g, edit=None):
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px" style="padding:28px 40px 0 40px;">\n'
            f'          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{g["card"]};border-left:5px solid {g["mark"]};">\n'
            f'            <tr><td{e} style="padding:28px 30px;font-family:{FONT};{SMALL};color:{g["card_ink"]};">\n'
            f'{inner}\n            </td></tr>\n          </table>\n        </td></tr>\n')


# --- content pieces ----------------------------------------------------------

def kicker(t, g):
    return (f'      <table role="presentation" border="0" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="52" style="width:52px;height:4px;background-color:{g["mark"]};font-size:0;line-height:0;">&nbsp;</td>'
            f'</tr></table>\n'
            f'      <p style="margin:18px 0 10px 0;font-size:12px;line-height:16px;letter-spacing:1.8px;'
            f'text-transform:uppercase;color:{g["kick"]};font-weight:bold;">{t}</p>')


def big_kicker(t, g):
    """An oversized overline — used where the line above the headline is the point."""
    return (f'      <table role="presentation" border="0" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="52" style="width:52px;height:4px;background-color:{g["mark"]};font-size:0;line-height:0;">&nbsp;</td>'
            f'</tr></table>\n'
            f'      <p style="margin:18px 0 6px 0;font-size:24px;line-height:30px;letter-spacing:3px;'
            f'text-transform:uppercase;color:{g["kick"]};font-weight:bold;">{t}</p>')


def display(t, g):
    """Section headline. Larger than before — this is the striking element."""
    return (f'      <h1 class="d1" style="margin:0 0 18px 0;font-family:{FONT};font-size:34px;'
            f'line-height:41px;letter-spacing:-0.4px;color:{g["head"]};font-weight:bold;">{t}</h1>')


def h2(t, g):
    return (f'            <h2 class="lba-h2" style="margin:0 0 14px 0;font-size:21px;line-height:29px;'
            f'color:{BLUE};font-weight:bold;">{t}</h2>')


def p(t, g, mb=16):
    return f'      <p style="margin:0 0 {mb}px 0;color:{g["body"]};">{t}</p>'


def lead(t, g, mb=18):
    return (f'      <p style="margin:0 0 {mb}px 0;font-size:19px;line-height:30px;color:{g["body"]};">{t}</p>')


def badge(t, g):
    """A filled chip carrying the date. High-contrast, and the eye lands on it."""
    if g["bg"] == SPACE:
        bg, fg = S_ACCENT, SPACE
    else:
        bg = WHITE if g["bg"] == BLUE else TEAL
        fg = BLUE if g["bg"] == BLUE else WHITE
    return (f'      <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin:0 0 20px 0;"><tr>'
            f'<td bgcolor="{bg}" style="padding:11px 20px;border-radius:3px;font-family:{FONT};font-size:13px;'
            f'line-height:17px;letter-spacing:1.2px;text-transform:uppercase;color:{fg};font-weight:bold;">{t}</td>'
            f'</tr></table>')


def bullets(items, g, indent=6):
    pad = " " * indent
    rows = ""
    for i, it in enumerate(items):
        gap = "0" if i == len(items) - 1 else "0 0 11px 0"
        rows += (f'{pad}  <tr><td width="20" valign="top" style="padding:{gap};color:{g["mark"]};{SMALL};font-weight:bold;">&bull;</td>'
                 f'<td style="padding:{gap};{SMALL};color:{g["body"]};">{it}</td></tr>\n')
    return f'{pad}<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">\n{rows}{pad}</table>'


def label(t, g, indent=6):
    return " " * indent + f'<p style="margin:0 0 12px 0;font-weight:bold;color:{g["strong"]};">{t}</p>'


def details(date_, time_, loc, indent=12, bare=False, g=None):
    pad = " " * indent
    ink_, lab = (CHAR, BLUE) if g is None else (g["card_ink"], g["kick"])
    edge = PANEL_EDGE if g is None else g["hair"]
    style = "" if bare else f' style="margin-top:20px;border-top:1px solid {edge};"'
    cell = "padding:0;" if bare else "padding:18px 0 0 0;"
    return (f'{pad}<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"{style}>'
            f'<tr><td style="{cell}{SMALL};color:{ink_};">'
            f'<strong style="color:{lab};">Date:</strong> {date_}<br />'
            f'<strong style="color:{lab};">Time:</strong> {time_}<br />'
            f'<strong style="color:{lab};">Location:</strong> {loc}</td></tr></table>')


def series_table(g, start=1):
    """The three-part schedule. `start` drops sessions that have already run,
    keeping the real session numbers rather than renumbering what is left."""
    rows = [("1", "Purpose, People, and AI: Building the Foundation of a Trusted Business", "Tue, Sept 15, 2026", "10:00 &ndash; 11:30 AM PT", S1),
            ("2", "Good for Business: Investing in People and AI as Workforce Capacity", "Wed, Sept 23, 2026", "11:00 AM &ndash; 1:00 PM PT", AI_S2),
            ("3", "Authority Positioning and Strategic Visibility to Yield Market Trust", "Thu, Oct 8, 2026", "12:00 &ndash; 2:00 PM PT", AI_S3)]
    rows = [r for r in rows if int(r[0]) >= start]
    out = ""
    for i, (n, t, d, tm, url) in enumerate(rows):
        border = "" if i == len(rows) - 1 else f"border-bottom:1px solid {RULE};"
        title = (f'<a href="{url}" target="_blank" style="color:{BLUE};text-decoration:underline;">{t}</a>'
                 if url else t)
        out += (f'        <tr>'
                f'<td width="40" valign="top" bgcolor="{TEAL}" style="width:40px;background-color:{TEAL};text-align:center;font-size:18px;line-height:22px;color:#FFFFFF;font-weight:bold;padding:16px 0;">{n}</td>'
                f'<td style="padding:16px 12px 16px 12px;font-size:13px;line-height:21px;color:{CHAR};{border}">'
                f'<strong style="color:{BLUE};font-size:13px;">{title}</strong><br />{d} &nbsp;&middot;&nbsp; {tm}</td></tr>\n')
    return (f'      <p style="margin:0 0 6px 0;font-size:12px;line-height:16px;letter-spacing:1.8px;text-transform:uppercase;color:{g["kick"]};font-weight:bold;">{"The full series" if start == 1 else "Still ahead"}</p>\n'
            f'      <p style="margin:0 0 18px 0;font-size:18px;line-height:27px;color:{g["strong"]};font-weight:bold;">{"Mark your calendars for René Redwood&rsquo;s three-part series." if start == 1 else "René Redwood&rsquo;s three-part series continues."}</p>\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{WHITE};border:1px solid {RULE};">\n{out}      </table>\n'
            f'      <p style="margin:14px 0 0 0;font-size:14px;line-height:22px;color:#000000;font-weight:bold;">'
            f'All sessions via Zoom. Select a session above to register.</p>')


def bio(name, text, g):
    return (f'      <p style="margin:0;font-size:14px;line-height:23px;color:{g["muted"]};">'
            f'<strong style="color:{g["strong"]};">About {name}.</strong> {text}</p>')


HONOREES = [("honoree-hacegaba.jpg", "Visionary of the Year", "Dr. Noel Hacegaba", "Chief Executive Officer<br />Port of Long Beach"),
            ("honoree-marshall.jpg", "Trailblazer of the Year", "Carrie Marshall", "Chief Executive Officer<br />Rebel Space"),
            ("honoree-lee.jpg", "Investor of the Year", "Joshua Lee", "Managing Partner<br />Gumshoe Ventures"),
            ("honoree-glass.jpg", "Founder of the Year", "Ethan Glass", "Chief Executive Officer<br />OCRA")]


def r_honorees(g):
    def cell(img, award, name, role):
        alt = f"{name}, {role.replace('<br />', ', ')}, 2026 LBA {award}"
        ribbon_bg = TEAL if g["bg"] != BLUE else R_KICK
        ribbon_fg = WHITE if g["bg"] != BLUE else BLUE
        return (f'              <td class="hcell" width="250" valign="top" style="width:250px;">\n'
                f'                <img src="images/{img}" width="250" alt="{alt}" style="width:100%;max-width:250px;height:auto;display:block;" />\n'
                f'                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"><tr>'
                f'<td bgcolor="{ribbon_bg}" style="padding:8px 12px;font-family:{FONT};font-size:11px;line-height:15px;'
                f'letter-spacing:1.1px;text-transform:uppercase;color:{ribbon_fg};font-weight:bold;white-space:nowrap;">{award}</td></tr></table>\n'
                f'                <p style="margin:12px 0 3px 0;font-family:{FONT};font-size:18px;line-height:25px;color:{g["head"]};font-weight:bold;">{name}</p>\n'
                f'                <p style="margin:0;font-family:{FONT};font-size:14px;line-height:22px;color:{g["muted"]};">{role}</p>\n'
                f'              </td>')
    gut = '              <td class="gut" width="20" style="width:20px;font-size:0;line-height:0;">&nbsp;</td>'
    a, b, c, d = [cell(*h) for h in HONOREES]
    sp = '            <tr><td colspan="3" height="32" style="height:32px;font-size:0;line-height:0;">&nbsp;</td></tr>'
    return (f'        <tr><td class="px" style="padding:22px 40px 0 40px;">\n'
            f'          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
            f'            <tr>\n{a}\n{gut}\n{b}\n            </tr>\n{sp}\n            <tr>\n{c}\n{gut}\n{d}\n            </tr>\n'
            f'          </table>\n        </td></tr>\n')


# --- links -------------------------------------------------------------------
S1   = "https://hub.catalyzerapp.com/public/events/purpose-people-and-ai-building-the-foundation-of-a-4705-133"
S2C  = "https://hub.catalyzerapp.com/public/events/session-2-preparing-to-pursue-the-work-evaluate-op-4705-67"
AI_S2 = "https://hub.catalyzerapp.com/public/events/good-for-business-investing-in-people-and-ai-as-wo-4705-199"
AI_S3 = "https://hub.catalyzerapp.com/public/events/authority-positioning-and-strategic-visibility-to-4705-232"
PACK = "https://drive.google.com/file/d/1brJxClWdJ9efsuH7RnPNsjyxDq5224CC/view"
TW   = "https://www.lbaccelerator.org/tech-week/"
FORM = "https://hub.catalyzerapp.com/public/form/46c9cb88-0c9a-4eac-9346-f53f61f511d6"
EVT  = "https://lbaccelerator.org/events"
LUM  = "https://www.lumen21.com/"
AERO = "https://www.eventcreate.com/e/winning-the-aerospace-talent-war"
# Luma pages, one per item. Each section links to its own event rather than to
# a page the reader then has to navigate.
LUMA_RECEPTION = "https://luma.com/0r1c6a6a"   # Day 1, Sept 28 Opening Reception
LUMA_PANEL = "https://luma.com/pexv032z"       # Oct 1, Conversation With Visionary Investors
LUMA_SUMMIT = None    # Oct 1 FULL DAY Summit, $150 - not supplied yet
LUMA_DAY2 = None      # Sept 30 Capital Corner / CSU Demo Day - not supplied yet


def luma(url, label, fallback_label, g, **kw):
    """A registration button, falling back to the Tech Week page with a label
    that promises less when the specific Luma link is not in hand."""
    return r_button(label if url else fallback_label, url or TW, g, **kw)

# The Bryson flyer is dropped in by hand - it is their artwork, not ours, and it
# is not in this repo. The 9/17 send picks it up automatically once the file
# exists at the path below, and renders as live text alone until it does, so a
# placeholder can never go out by accident.
AERO_IMG = "aerospace-talent-war.jpg"
AERO_HAS_IMG = os.path.exists(os.path.join(ASSETS, AERO_IMG))
AERO_ALT = ("Winning the Aerospace Talent War, featuring guest speaker Devin Hughes, bestselling author and "
            "internationally recognized leadership and workplace culture expert. The Modern, 2801 E Spring "
            "Street, Long Beach, CA 90806, September 23 at 5:30 PM. Hosted by Bryson. RSVP to reserve a spot.")

RENE = ("René Redwood is a recognized leader in advancing equity, inclusive workplace culture, and strategic "
        "initiatives that drive results. She has directed the Presidential Glass Ceiling Commission and served on "
        "the court-appointed Coca-Cola Task Force, and brings decades of experience helping organizations build "
        "trust and create a lasting advantage in the marketplace.")
RONDA = ("Ronda Jackson is a business adviser, speaker, author, and entrepreneur with more than 20 years of "
         "experience in business development, procurement, strategic planning, and entrepreneurship. As an LBA "
         "Business Adviser, she helps business owners navigate contracting opportunities, strengthen operations, "
         "and prepare for sustainable growth.")

S1_BULLETS = ["Clarify your business purpose and the value you create",
              "Connect your values, mission, and leadership to daily decisions",
              "Align your people, systems, and AI tools with your goals",
              "Communicate your value clearly to build trust and confidence",
              "Lay the foundation for a business that can grow beyond you"]
TW_BULLETS = ["Brand visibility throughout Long Beach Tech Week",
              "Recognition and engagement with founders, investors, and regional leaders",
              "Opportunities to participate in select programs, forums, and the 2026 Investors &amp; Founders Summit"]

S2_ALT = ("Session 2 of Building an AI-Ready Trusted Business: Good for Business, Investing in People "
          "and AI as Workforce Capacity. Wednesday, September 23, 2026, 11:00 am to 1:00 pm PT, via Zoom. "
          "Facilitated by Ren\u00e9 Redwood. Hosted by the Long Beach Accelerator.")
S3_ALT = ("Session 3 of Building an AI-Ready Trusted Business: Authority Positioning and Strategic "
          "Visibility to Yield Market Trust. Thursday, October 8, 2026, 12:00 pm to 2:00 pm PT, via Zoom. "
          "Facilitated by Ren\u00e9 Redwood. Hosted by the Long Beach Accelerator.")
HERO_ALT = ("Building an AI-Ready Trusted Business: a three-part learning journey for small business owners, "
            "facilitated by René Redwood. Hosted by the Long Beach Accelerator.")
RENE_ALT = ("Facilitated by René Redwood, a recognized leader in advancing equity, inclusive workplace "
            "culture, and strategic initiatives that drive results. René brings decades of experience helping "
            "organizations build trust, leverage human potential, and create a lasting advantage in the marketplace.")
CONTRACT_ALT = ("Contracting and Procurement Readiness Series, Session 2: Preparing to Pursue the Work. "
                "Thursday, September 10, 4:00 to 5:30 PM PT, online via Zoom, featuring LBA Business Adviser Ronda Jackson.")
TW_REG_ALT = ("Registration is open for Long Beach Tech Week 2026, hosted by the Long Beach Accelerator, "
              "September 28th to October 1st, 2026, in Long Beach, California.")
TW_ALT = ("Long Beach Tech Week 2026 Sponsorship Opportunities, hosted by the Long Beach Accelerator, "
          "September 28th to October 1st, 2026.")

W, T, B = ink("white"), ink("tint"), ink("blue")
S = ink("space")

LOGO_ROWS = [
    ("Hosted by", [("lbtw-host-lba-v2.jpg", 260, "Long Beach Accelerator")]),
    ("Planning Partners", [
        ("lbtw-partner-iie.jpg", 156, "The Institute for Innovation and Entrepreneurship, CSULB"),
        ("lbtw-partner-sunstone-v2.jpg", 156, "Sunstone"),
        ("lbtw-partner-city-longbeach.jpg", 156, "City of Long Beach")]),
    ("2026 Sponsors", [
        ("lbtw-sponsor-fm-bank.jpg", 156, "F&amp;M Bank"),
        ("lbtw-sponsor-port-longbeach.jpg", 156, "Port of Long Beach"),
        ("lbtw-sponsor-intertrend.jpg", 156, "Intertrend"),
        ("lbtw-sponsor-westcoast.png", 156, "Westcoast Warehousing &amp; Trucking"),
        ("lbtw-sponsor-shimoyama.jpg", 156, "Shimoyama Enterprise"),
        ("lbtw-sponsor-lmb-imprint.jpg", 156, "Imprint"),
        ("lbtw-sponsor-gobiz.jpg", 156, "California Office of the Small Business Advocate (GO-Biz)"),
        ("lbtw-sponsor-sba.jpg", 156, "U.S. Small Business Administration"),
        ("lbtw-sponsor-deo.jpg", 156, "Department of Economic Opportunity, County of Los Angeles")]),
]

LOGO_IMAGES = [f for _, row in LOGO_ROWS for f, _, _ in row]


def r_logos(per_row=3):
    """The host, partner and sponsor wall that closes the Tech Week sends,
    in the same order and grouping as the event page."""
    out = ""
    for heading, logos in LOGO_ROWS:
        out += (f'        <tr><td align="center" style="padding:26px 0 12px 0;font-family:{FONT};font-size:12px;'
                f'line-height:18px;letter-spacing:1.6px;text-transform:uppercase;font-weight:bold;color:{TEAL};">'
                f'{heading}</td></tr>\n')
        n = 1 if len(logos) == 1 else per_row
        out += '        <tr><td><table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
        for i in range(0, len(logos), n):
            out += "          <tr>"
            chunk = logos[i:i + n]
            for f, w, alt in chunk:
                out += (f'<td align="center" valign="middle" width="{100 // n}%" style="padding:8px 6px;">'
                        f'<img src="images/{f}" width="{w}" alt="{alt}" '
                        f'style="display:block;width:100%;max-width:{w}px;height:auto;margin:0 auto;" /></td>')
            for _ in range(n - len(chunk)):
                out += f'<td width="{100 // n}%">&nbsp;</td>'
            out += "</tr>\n"
        out += "        </table></td></tr>\n"
    return (f'  <tr><td style="background-color:{WHITE};">\n'
            f'    <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
            f'      <tr><td class="px" style="padding:6px 40px 26px 40px;">\n'
            f'        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
            f'{out}        </table>\n      </td></tr>\n    </table>\n  </td></tr>\n')


# Spacing is set once in the helpers above. A send that wants to run tighter
# maps those values down here rather than forking every helper; tap targets and
# the section rules are deliberately left alone.
TIGHTEN = {
    "padding:36px 40px 0 40px": "padding:24px 40px 0 40px",
    "padding:28px 40px 0 40px": "padding:18px 40px 0 40px",
    "padding:26px 40px 0 40px": "padding:18px 40px 0 40px",
    "padding:24px 40px 0 40px": "padding:16px 40px 0 40px",
    "padding:22px 40px 0 40px": "padding:15px 40px 0 40px",
    "padding:28px 32px 22px 32px": "padding:20px 32px 15px 32px",
    "padding:26px 40px 38px 40px": "padding:20px 40px 28px 40px",
    "padding:28px 30px": "padding:20px 24px",
    "padding:26px 0 12px 0": "padding:18px 0 9px 0",
    "height:38px": "height:24px",
    "height:36px": "height:22px",
    "height:34px": "height:22px",
    "height:32px": "height:22px",
    "height:30px": "height:20px",
    "margin:18px 0 10px 0": "margin:12px 0 7px 0",
    "margin:18px 0 6px 0": "margin:12px 0 5px 0",
    "margin:0 0 18px 0": "margin:0 0 12px 0",
    "margin:0 0 16px 0": "margin:0 0 11px 0",
    "margin:0 0 20px 0": "margin:0 0 13px 0",
    "margin:0 0 14px 0": "margin:0 0 10px 0",
    "margin:12px 0 3px 0": "margin:8px 0 2px 0",
}


def tighten(html):
    for a, b in TIGHTEN.items():
        html = html.replace(a, b)
    return html


CAMPAIGNS = {}

# ============================ THURSDAY, SEPT 10 ==============================
# Copy sourced from the 2026 LBTW / LBA Summit sponsorship flyer (090126).
CAMPAIGNS["2026-09-10"] = dict(
    title="Long Beach Tech Week 2026 & What's Ahead",
    subject="Long Beach Tech Week, the 2026 LBA honorees, and today at 4 PM",
    alts=["Put your organization at the center of our innovation ecosystem",
          "Meet the 2026 LBA honorees",
          "Sponsorship opportunities are open for Long Beach Tech Week"],
    preheader="Long Beach Tech Week runs Sept 28th - Oct 1st, sponsorship opportunities are open, and contracting readiness is this afternoon.",
    send="Thursday, September 10, 2026, 8:00 AM PT",
    images=["lba-logo.png", "techweek-2026.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "contracting-session2.jpg",
            "hero-ai-title.jpg", "hero-ai-rene.jpg",
            "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        # 1 — LONG BEACH TECH WEEK
        section([
            r_image("techweek-2026.jpg", TW_ALT, href=TW),
            r_button("Register for Long Beach Tech Week", TW, W),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Put Your Organization at the Center of Our Innovation Ecosystems", W),
                badge("Sept 28th &ndash; Oct 1st &middot; Long Beach", W),
                p("Connect with founders, investors, business leaders, corporate innovators, tech experts, entrepreneurs, educators, and public and private sector leaders shaping the region's future in technology for economic impact.", W),
                p(f'Hosted by the Long Beach Accelerator, <a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week 2026</a> offers leaders and organizations a unique opportunity to build visibility, strengthen relationships, and connect directly with the growing innovation and emerging technology ecosystems here in Southern California and throughout our state.', W),
                label("Key sectors:", W),
                bullets(["Transportation, Logistics &amp; Supply Chain",
                         "Aerospace &amp; Space",
                         "Energy &amp; Sustainability",
                         "Health Tech",
                         "Entertainment &amp; Creative Economy",
                         "Other emerging tech industries"], W),
            ]), W, edit="techweek"),
            r_pad(36),
        ]),

        # 2 — SPONSORSHIP OPPORTUNITIES
        section([
            r_text("\n".join([
                kicker("Become a Partner", T),
                display("Sponsorship Opportunities", T),
                p("Sponsorships are available at several levels, each carrying recognition across Long Beach Tech Week and at the Summit:", T),
            ]), T, edit="sponsorship"),
            r_text(f'      Benefits include presenting recognition, speaking opportunities in the 2026&ndash;2027 LBA forum, access to the Founders Roundtable, Summit registrations, and placement across LBA communications. See the <a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">full sponsorship opportunities</a> for what each level carries.',
                   T, edit="packet_line", pad="24px 40px 0 40px"),
            r_button("View Sponsorship Opportunities", PACK, T),
            r_pad(38),
        ], ground="tint"),

        # 3 — HONOREES
        section([
            r_text("\n".join([
                kicker("Celebrate LBA Honorees", B),
                display("Meet the 2026 LBA Honorees", B),
                p("Four visionary leaders who have led the way, blazed the trail, and stand among our top investors and founders.", B, 0),
            ]), B, edit="honorees_intro"),
            r_honorees(B),
            r_pad(38),
        ], ground="blue"),

        # 4 — THE SUMMIT
        section([
            r_text("\n".join([
                big_kicker("3rd Annual", W),
                display("LBA Investors &amp; Founders Summit", W),
                badge("Thu, Oct 1st &middot; 11:00 AM &ndash; 6:00 PM", W),
                p("<strong style=\"color:#204396;\">Hyatt Regency Long Beach &middot; Beacon Ballroom</strong>", W),
                p("The Summit celebrates LBA honorees at the Awards Luncheon. The <strong style=\"color:#204396;\">LBA Visionary Investors Panel</strong>, our signature afternoon forum, is a conversation with visionary investors on the global economy and emerging technology, and includes a special preview of LA2028 Olympics and Paralympics opportunities.", W, 0),
            ]), W, edit="summit"),
            r_pad(36),
        ]),

        # 5 — RONDA JACKSON: CONTRACTING SESSION 2 (today)
        section([
            r_image("contracting-session2.jpg", CONTRACT_ALT),
            r_text("\n".join([
                kicker("Contracting &amp; Procurement Readiness", T),
                display("Prepare. Pursue. Perform.", T),
                badge("Today &middot; 4:00 &ndash; 5:30 PM PT", T),
                lead("It's not too late to join us.", T, 0),
            ]), T, edit="contracting_top"),
            r_button("Register Now", S2C, T, align="left", pad_top=22),
            r_text("\n".join([
                p('Session 2 of our Contracting &amp; Procurement Readiness Series runs this afternoon: <em>Preparing to Pursue the Work, Evaluate Opportunities, Respond Strategically, and Prepare to Perform.</em>', T),
                label("In this session, you will:", T),
                bullets(["Evaluate opportunities and respond strategically",
                         "Understand key requirements, capacity, pricing, and teaming considerations",
                         "Prepare to perform successfully and build toward future opportunities"], T),
            ]), T, edit="contracting"),
            r_text(bio("the facilitator", RONDA, T), T, edit="ronda", pad="26px 40px 0 40px"),
            r_pad(36),
        ], ground="tint"),

        # 6 — RENE REDWOOD: AI-READY SERIES (banner split vertically to stay legible)
        section([
            r_image("hero-ai-title.jpg", HERO_ALT),
            r_pad(20),
            r_image("hero-ai-rene.jpg", "Facilitated by René Redwood, a recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results."),
            r_text("\n".join([
                kicker("A New Three-Part Learning Series", W),
                display("Building an AI-Ready Trusted Business", W),
                badge("Starts Tue, Sept 15 &middot; 10:00 AM PT", W),
                p("Join us for a new three-part learning series facilitated by <strong style=\"color:#204396;\">René Redwood</strong> and designed to help small business owners strengthen how they operate, compete, and grow.", W),
                p("Across three sessions, participants will explore how purpose, people, leadership, AI, and strategic visibility can work together to build a stronger, more trusted business.", W, 0),
            ]), W, edit="ai_intro"),
            r_card("\n".join([
                f'            <p style="margin:0 0 8px 0;font-size:12px;line-height:16px;letter-spacing:1.8px;text-transform:uppercase;color:{TEAL};font-weight:bold;">Start with Session 1</p>',
                h2("Purpose, People, and AI: Building the Foundation of a Trusted Business", W),
                '            <p style="margin:0 0 18px 0;">What makes your business valuable, distinct, and worthy of trust? In this session, business owners will connect their personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how their company operates and grows.</p>',
                label("In this session, you will:", W, indent=12),
                bullets(S1_BULLETS, W, indent=12),
                details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Via Zoom"),
            ]), W, edit="session1"),
            r_button("Register for Session&nbsp;1", S1, W),
            r_text(series_table(W), W, edit="series", pad="36px 16px 0 16px"),
            r_pad(36),
        ]),

        # 7 — BUSINESS ADVISORY
        section([
            r_text("\n".join([
                kicker("LBA Business Advisory Services", T),
                display("Business Advisory Intake Form", T),
                p("We provide no-cost, one-on-one business advising for emerging technology companies and innovation-driven small businesses. Whether you're preparing for growth, exploring debt or equity financing, integrating AI into your operations, pursuing contract opportunities, or developing a long-term business strategy, our experienced advisors are here to help.", T),
                p(f'Complete our <a href="{FORM}" target="_blank" style="color:{BLUE};text-decoration:underline;">business advisory intake form</a> to get matched with the advisor best suited to your goals.', T, 0),
            ]), T, edit="advising"),
            r_button("Register for Business Advisory Services", FORM, T, invert=True),
            r_pad(38),
        ], ground="tint", rule_after=False),
    ],
)

# ============================ MONDAY, SEPT 14 ================================
CAMPAIGNS["2026-09-14"] = dict(
    title="Session 1 starts tomorrow",
    subject="Tomorrow at 10 AM: Purpose, People, and AI",
    alts=["Last call — Session 1 is tomorrow morning",
          "90 minutes tomorrow to sharpen your business",
          "Starts tomorrow: Building an AI-Ready Business"],
    preheader="Ninety minutes on Zoom with René Redwood. Session 1 of three, and there's still room.",
    send="Monday, September 14, 2026, 8:00 AM PT",
    images=["lba-logo.png", "hero-ai-title.jpg", "hero-ai-rene.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([
            r_image("hero-ai-title.jpg", HERO_ALT),
            r_pad(20),
            r_image("hero-ai-rene.jpg", "Facilitated by René Redwood, a recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results."),
            r_text("\n".join([
                kicker("Starts Tomorrow", W),
                display("Building an AI-Ready Trusted Business", W),
                badge("Tue, Sept 15 &middot; 10:00 &ndash; 11:30 AM PT", W),
                lead("Ninety minutes on Zoom with René Redwood, built around your business rather than a slide deck.", W),
                p("If you have been meaning to sign up, this is the moment.", W, 0),
            ]), W, edit="intro"),
            r_pad(34),
        ]),

        section([
            r_text("\n".join([
                kicker("Session 1", B),
                display("Purpose, People, and AI", B),
                p("What makes your business valuable, distinct, and worthy of trust? You will connect your personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how your company operates and grows.", B),
                label("You will leave able to:", B),
                bullets(S1_BULLETS, B),
            ]), B, edit="session1"),
            r_card(details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Via Zoom", indent=12, bare=True), B),
            r_button("Register for Session&nbsp;1", S1, B),
            r_pad(38),
        ], ground="blue"),

        section([
            r_text(series_table(W), W, edit="series", pad="36px 16px 0 16px"),
            r_pad(36),
        ]),

        section([
            r_text(f'      <p style="margin:0;{SMALL};color:{CHAR};"><strong style="color:{BLUE};">Also ahead:</strong> '
                   f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week</a> runs September 28th &ndash; October 1st, and '
                   f'<a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">sponsorships are open</a>.</p>',
                   T, edit="ps"),
            r_pad(36),
        ], ground="tint"),
    ],
)

# ===================== MONDAY, SEPT 14 — RENÉ EDITION =======================
# Goes out Monday the 14th for a Tuesday session, alongside the other 9/14
# spec above. Same slot, different angle: that one leads on the deadline,
# this one leads on the facilitator.
CAMPAIGNS["2026-09-14-rene"] = dict(
    title="Tomorrow at 10 AM with René Redwood",
    subject="Tomorrow at 10 AM with René Redwood",
    alts=["Ninety minutes tomorrow with René Redwood",
          "René Redwood is on Zoom tomorrow at 10 AM",
          "Tomorrow: Purpose, People, and AI"],
    preheader="Session 1 of Building an AI-Ready Trusted Business starts tomorrow morning on Zoom, and there is still room.",
    send="Monday, September 14, 2026",
    images=["lba-logo.png", "hero-ai-rene.jpg", "hero-ai-title.jpg",
            "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        # 1 — RENÉ LEADS
        section([
            r_image("hero-ai-rene.jpg", RENE_ALT),
            r_text("\n".join([
                kicker("Tomorrow at 10 AM", W),
                display("Ninety Minutes with René Redwood", W),
                badge("Tomorrow &middot; 10:00 &ndash; 11:30 AM PT", W),
                lead("Session 1 of <strong style=\"color:#204396;\">Building an AI-Ready Trusted Business</strong> starts tomorrow morning, and there is still room.", W),
                p("René facilitates all three sessions, and she builds them around the businesses in the room rather than a slide deck. Bring the one you are actually running.", W, 0),
            ]), W, edit="intro"),
            r_button("Register and Join Us", S1, W),
            r_pad(34),
        ]),

        # 2 — WHO SHE IS (the one blue band in this send)
        section([
            r_text("\n".join([
                kicker("Your Facilitator", B),
                display("René Redwood", B),
                p("A recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results.", B),
                label("Behind the work:", B),
                bullets(["Directed the Presidential Glass Ceiling Commission",
                         "Served on the court-appointed Coca-Cola Task Force",
                         "Decades helping organizations build trust, leverage human potential, and create a lasting advantage in the marketplace"], B),
            ]), B, edit="rene"),
            r_text(p("That is the experience she brings to a room of small business owners &mdash; three sessions on what makes a business worth trusting, and how purpose, people, leadership, and AI hold that together.", B, 0),
                   B, edit="rene_close", pad="24px 40px 0 40px"),
            r_button("Save Your Seat", S1, B),
            r_pad(38),
        ], ground="blue"),

        # 3 — WHAT SESSION 1 COVERS
        section([
            r_image("hero-ai-title.jpg", HERO_ALT),
            r_text("\n".join([
                kicker("Session 1 of 3", T),
                display("Purpose, People, and AI", T),
                p("What makes your business valuable, distinct, and worthy of trust? You will connect your personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how your company operates and grows.", T),
                label("You will leave able to:", T),
                bullets(S1_BULLETS, T),
            ]), T, edit="session1"),
            r_card(details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Online via Zoom", indent=12, bare=True), T),
            r_button("Register for Session&nbsp;1", S1, T),
            r_pad(38),
        ], ground="tint"),

        # 4 — THE FULL SERIES
        section([
            r_text(series_table(W), W, edit="series", pad="36px 16px 0 16px"),
            r_pad(36),
        ]),

        # 5 — ALSO AHEAD
        section([
            r_text("\n".join([
                kicker("Also Ahead", T),
                display("Long Beach Tech Week 2026", T),
                p(f'Long Beach Tech Week runs <strong style="color:{BLUE};">September 28th &ndash; October 1st</strong> and closes with the 3rd Annual LBA Investors &amp; Founders Summit. <a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">Sponsorship opportunities</a> are open now.', T, 0),
            ]), T, edit="ps"),
            r_button("Register for Long Beach Tech Week", TW, T, invert=True),
            r_pad(38),
        ], ground="tint"),
    ],
)

# ============================ FRIDAY, SEPT 18 ================================
CAMPAIGNS["2026-09-18"] = dict(
    title="Sponsor Long Beach Tech Week 2026",
    subject="Long Beach Tech Week: sponsorships are open",
    alts=["Put your brand at Long Beach Tech Week",
          "Sponsor Long Beach Tech Week 2026",
          "Meet the 2026 Summit honorees"],
    preheader="Sept 28th - Oct 1st. Sponsors join founders, investors, and civic leaders - and sit in the room for the Summit.",
    send="Friday, September 18, 2026, 8:00 AM PT",
    images=["lba-logo.png", "techweek-2026.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([
            r_image("techweek-2026.jpg", TW_ALT, href=TW),
            r_button("Register for Long Beach Tech Week", TW, W),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Put Your Organization at the Center of Long Beach's Innovation Ecosystems", W),
                badge("Sept 28th &ndash; Oct 1st &middot; Long Beach", W),
                lead("Long Beach Tech Week is ten days out, and sponsorships are open.", W),
                p(f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week 2026</a> draws founders, investors, business leaders, tech experts, entrepreneurs, educators, creatives, and civic leaders for a multi-day experience showcasing the people, ideas, and industries shaping our region\'s future.', W),
                label("Sponsorship opportunities are available at multiple levels, offering benefits such as:", W),
                bullets(TW_BULLETS, W),
            ]), W, edit="techweek"),
            r_text(f'      Explore the <a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week 2026 Sponsorship Packet</a> and join us as a partner.',
                   W, edit="packet_line", pad="22px 40px 0 40px"),
            r_button("View the Sponsorship Packet", PACK, W),
            r_pad(36),
        ]),

        section([
            r_text("\n".join([
                kicker("3rd Annual Investors &amp; Founders Summit", B),
                display("Meet the 2026 Honorees", B),
                p("The Summit closes out Long Beach Tech Week on <strong style=\"color:#FFFFFF;\">Thursday, October 1st</strong> at the <strong style=\"color:#FFFFFF;\">Hyatt Regency Long Beach</strong>. Sponsors sit in the room as we recognize four leaders shaping the region's innovation economy.", B, 0),
            ]), B, edit="honorees_intro"),
            r_honorees(B),
            r_pad(38),
        ], ground="blue"),

        section([
            r_text("\n".join([
                kicker("Opening Later This Month", W),
                display("A New Tech Center for Long Beach", W),
                p("Our new tech center opens at the end of September, giving founders and small business owners a dedicated space to build, meet, and grow alongside the rest of the Long Beach innovation community.", W),
                p(f'We\'re partnering with <a href="{LUM}" target="_blank" style="color:{BLUE};text-decoration:underline;">Lumen 21</a> on the installation and IT infrastructure behind the space.', W, 0),
            ]), W, edit="techcenter"),
            r_pad(36),
        ]),

        section([
            r_text("\n".join([
                kicker("Still Open", T),
                display("Building an AI-Ready Trusted Business", T),
                p(f'Session 2, <strong style="color:{BLUE};">Good for Business: Investing in People and AI as Workforce Capacity</strong>, runs <strong style="color:{BLUE};">Wednesday, September 23, 11:00 AM &ndash; 1:00 PM PT</strong> on Zoom. Session 3 follows on October 8. Register at <a href="{EVT}" target="_blank" style="color:{BLUE};text-decoration:underline;">lbaccelerator.org/events</a>.', T, 0),
            ]), T, edit="aiseries"),
            r_pad(36),
        ], ground="tint"),
    ],
)


# ====================== THURSDAY, SEPT 17 — TECH WEEK SIGNUPS ================
# Attendee registration, not sponsorship. Same Tech Week facts as the 9/10 and
# 9/18 sends, turned around to answer "why should I come?" rather than "why
# should we sponsor?". Sponsorship drops to a postscript.
#
# Ships the same evening as the aerospace invite above, so nothing here counts
# days: Tech Week is eleven out, and a countdown that has to be recomputed on
# every re-date is how a send goes out saying the wrong thing.
CAMPAIGNS["2026-09-17-techweek"] = dict(
    title="Register for Long Beach Tech Week 2026",
    subject="Register today for Long Beach Tech Week",
    alts=["Long Beach Tech Week opens Sept 28th",
          "Four days, Sept 28th to Oct 1st, in Long Beach",
          "Your seat at Long Beach Tech Week"],
    preheader="Four days with the founders, investors, and leaders building the region's tech economy. Register today.",
    send="Thursday, September 17, 2026, evening",
    images=["lba-logo.png", "techweek-2026-register.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        # 1 — THE ASK
        section([
            r_image("techweek-2026-register.jpg", TW_REG_ALT, href=TW),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Four Days at the Center of Our Innovation Ecosystems", W),
                badge("Sept 28th &ndash; Oct 1st &middot; Long Beach", W),
                lead("Register today! Long Beach Tech Week Kick Off is Monday, September 28th.", W),
                p("Connect with founders, investors, business leaders, corporate innovators, tech experts, entrepreneurs, educators, and public and private sector leaders shaping the region's future in technology for economic impact.", W, 0),
            ]), W, edit="register"),
            r_button("Register for Long Beach Tech Week", TW, W),
            r_pad(36),
        ]),

        # 2 — WHAT THE WEEK COVERS
        section([
            r_text("\n".join([
                kicker("What's Ahead", T),
                display("A Week Built Around the Region's Industries", T),
                p(f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week 2026</a> is four days to build visibility, strengthen relationships, and connect directly with the growing innovation and emerging technology ecosystems here in Southern California and throughout our state.', T),
                p('Hosted by the Long Beach Accelerator. Planning partners include: Institute for Innovation &amp; Entrepreneurship &ndash; CSULB, City of Long Beach, and Sunstone Management.', T),
                label("Key sectors:", T),
                bullets(["Transportation, Logistics &amp; Supply Chain",
                         "Aerospace &amp; Space",
                         "Energy &amp; Sustainability",
                         "Health Tech",
                         "Entertainment &amp; Creative Economy",
                         "Other emerging tech industries"], T),
            ]), T, edit="sectors"),
            r_pad(38),
        ], ground="tint"),

        # 3 — THE SUMMIT (the one blue band: the marquee reason to come)
        section([
            r_text("\n".join([
                big_kicker("3rd Annual", B),
                display("LBA Investors &amp; Founders Summit", B),
                badge("Thu, Oct 1st &middot; 11:00 AM &ndash; 6:00 PM", B),
                p('<strong style="color:#FFFFFF;">Hyatt Regency Long Beach &middot; Beacon Ballroom</strong>', B),
                p('The Summit closes out Long Beach Tech Week. It celebrates the LBA honorees at the Awards Luncheon, and the <strong style="color:#FFFFFF;">LBA Visionary Investors Panel</strong>, our signature afternoon forum, is a conversation with visionary investors on the global economy and emerging technology, including a special preview of LA2028 Olympics and Paralympics opportunities.', B, 0),
            ]), B, edit="summit"),
            r_button("Register for Long Beach Tech Week", TW, B),
            r_pad(38),
        ], ground="blue"),

        # 4 — HONOREES
        section([
            r_text("\n".join([
                kicker("Celebrate LBA Honorees", W),
                display("Congratulations to the 2026 LBA Honorees", W),
                p("Four visionary leaders who have led the way, blazed the trail, and stand among our top investors and founders. They are recognized at the Awards Luncheon on October 1st.", W, 0),
            ]), W, edit="honorees_intro"),
            r_honorees(W),
            r_pad(38),
        ]),

        # 5 — SPONSORSHIP, AS A POSTSCRIPT
        section([
            r_text("\n".join([
                kicker("For Organizations", T),
                display("Sponsorships Are Still Open", T),
                p("Sponsorships are available at several levels, each carrying recognition across Long Beach Tech Week and at the Summit. Benefits include presenting recognition, speaking opportunities in the 2026&ndash;2027 LBA forum, access to the Founders Roundtable, Summit registrations, and placement across LBA communications.", T, 0),
            ]), T, edit="sponsorship"),
            r_button("View Sponsorship Opportunities", PACK, T, invert=True),
            r_pad(38),
        ], ground="tint"),
    ],
)

# ============== THURSDAY, SEPT 17 — AEROSPACE INVITE (SELECT LIST) ============
# A partner event hosted by Bryson, not by the LBA, so the copy says so in the
# first line. The flyer rides at the top when AERO_IMG is present, linked to the
# RSVP page; the details repeat underneath as live text either way. That is not
# redundancy - the flyer is a 16:9 landscape whose type lands around 7px at
# 600px, and it is gone entirely for anyone reading with images off.
CAMPAIGNS["2026-09-17-aerospace"] = dict(
    title="Winning the Aerospace Talent War",
    subject="Invitation: Winning the Aerospace Talent War",
    alts=["Wed, Sept 23: Winning the Aerospace Talent War",
          "Devin Hughes on aerospace talent, Sept 23",
          "An invitation we're passing along"],
    preheader="Wednesday, September 23 at 5:30 PM at The Modern in Long Beach. Bestselling author Devin Hughes headlines.",
    send="Thursday, September 17, 2026, evening",
    images=(["lba-logo.png"] + ([AERO_IMG] if AERO_HAS_IMG else [])
            + ["icon-linkedin.png", "icon-email.png", "icon-web.png"]),
    sections=[
        # The flyer, when it is on disk, sits directly above a panel on the same
        # near-black ground, so artwork and copy read as one piece rather than a
        # black image pasted onto a white email.
        section([
            *([r_image(AERO_IMG, AERO_ALT, href=AERO)] if AERO_HAS_IMG else []),
            r_text("\n".join([
                kicker("An Invitation We're Passing Along", S),
                display("Winning the Aerospace Talent War", S),
                badge("Wed, Sept 23 &middot; 5:30 PM &middot; Long Beach", S),
                lead(f'<a href="{AERO}" target="_blank" style="color:{S_ACCENT};text-decoration:underline;">Winning the Aerospace Talent War</a> is hosted by <strong style="color:#FFFFFF;">Bryson</strong>, and we are sharing it with a small group of regional leaders we think should be in the room.', S),
                p("Aerospace and space is one of the sectors driving this region's economy, and talent is the constraint those companies name most often.", S, 0),
            ]), S, edit="intro"),
            r_button("RSVP for the Evening", AERO, S),
            r_pad(38),
        ], ground="space", rule_after=False),

        section([
            r_text("\n".join([
                kicker("Featured Guest Speaker", S),
                display("Devin Hughes", S),
                p("Bestselling author, and an internationally recognized leadership and workplace culture expert.", S, 0),
            ]), S, edit="speaker"),
            r_card(details("Wednesday, September 23, 2026", "5:30 PM",
                           "The Modern &middot; 2801 E Spring Street, Long Beach, CA 90806",
                           indent=12, bare=True, g=S), S),
            r_button("Reserve Your Spot", AERO, S),
            r_pad(38),
        ], ground="space"),

        section([
            r_text("\n".join([
                kicker("Also Ahead", T),
                display("Long Beach Tech Week 2026", T),
                p(f'Long Beach Tech Week runs <strong style="color:{BLUE};">September 28th &ndash; October 1st</strong> and closes with the 3rd Annual LBA Investors &amp; Founders Summit. Aerospace and space is one of its key sectors.', T, 0),
            ]), T, edit="ps"),
            r_button("Register for Long Beach Tech Week", TW, T, invert=True),
            r_pad(38),
        ], ground="tint"),
    ],
)

# ============ SEPT 17 — AEROSPACE INVITE, COLD OUTREACH VARIANT ==============
# Same email, sent to the Aero/Transpo prospect list rather than to LBA's own
# audience. Those addresses were collected from public company contact pages,
# so the footer cannot claim they opted in via our website - it says what is
# actually true instead. Everything else is identical.
CAMPAIGNS["2026-09-17-aerospace-outreach"] = dict(
    CAMPAIGNS["2026-09-17-aerospace"],
    permission_line=("You are receiving this email because your organization is part of the "
                     "Long Beach technology and innovation community."),
)

# ================= MONDAY, SEPT 21 — OPENING RECEPTION =======================
# Copy taken from the sent 9/17 archive, with the reception promoted to the
# hero and a Luma link for it. Runs tight: same components, spacing mapped
# down about a third, so the whole send is a shorter scroll.
CAMPAIGNS["2026-09-21-reception"] = dict(
    title="Join Us for the Opening Reception",
    subject="Join us at the Long Beach Tech Week opening",
    alts=["The opening reception is Monday the 28th",
          "Long Beach Tech Week opens Monday",
          "Kick off Long Beach Tech Week with us"],
    preheader="Monday, September 28th. Hear from the city, the SBA and regional CEOs, then stay for the week.",
    send="Monday, September 21, 2026, 8:00 AM PT",
    tight=True,
    images=(["lba-logo.png", "techweek-2026-reception.jpg", "honoree-hacegaba.jpg",
             "honoree-marshall.jpg", "honoree-lee.jpg", "honoree-glass.jpg"]
            + LOGO_IMAGES + ["icon-linkedin.png", "icon-email.png", "icon-web.png"]),
    sections=[
        # 1 — THE RECEPTION
        section([
            r_image("techweek-2026-reception.jpg", TW_REG_ALT, href=TW),
            # Straight under the banner, as live HTML rather than baked into it:
            # a button drawn on the artwork is gone for anyone reading with
            # images off, and is not a tap target.
            r_button("Join the Opening Reception", LUMA_RECEPTION, W, pad_top=26),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Register for the Opening Reception", W),
                badge("Opening Reception &middot; Sept 28th", W),
                lead("Register today! Long Beach Tech Week Kick Off is Monday, September 28th.", W),
                p("Hear from Lucius Martin, Deputy Mayor of Economic Development, and CEOs on economic growth in the region. A special presentation with the U.S. Small Business Administration marks the opening of the new Long Beach Accelerator Tech Hub Center.", W),
                p("Connect with founders, investors, business leaders, corporate innovators, tech experts, entrepreneurs, educators, and public and private sector leaders shaping the region's future in technology for economic impact.", W, 0),
            ]), W, edit="reception"),
            r_button("Register for Long Beach Tech Week", TW, W, invert=True),
            r_pad(30),
        ]),

        # 2 — THE WEEK
        section([
            r_text("\n".join([
                kicker("What's Ahead", T),
                display("A Week Built Around the Region's Industries", T),
                p(f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week 2026</a> runs September 28th &ndash; October 1st: four days to build visibility, strengthen relationships, and connect directly with the growing innovation and emerging technology ecosystems here in Southern California and throughout our state.', T),
                p('Hosted by the Long Beach Accelerator. Planning partners include: Institute for Innovation &amp; Entrepreneurship &ndash; CSULB, City of Long Beach, and Sunstone Management.', T),
                label("Key sectors:", T),
                bullets(["Transportation, Logistics &amp; Supply Chain",
                         "Aerospace &amp; Space",
                         "Energy &amp; Sustainability",
                         "Health Tech",
                         "Entertainment &amp; Creative Economy",
                         "Other emerging tech industries"], T),
            ]), T, edit="week"),
            r_pad(30),
        ], ground="tint"),

        # 3 — THE AWARDS LUNCHEON (the one blue band)
        section([
            r_text("\n".join([
                big_kicker("3rd Annual", B),
                display("LBA Investors &amp; Founders Summit Awards Luncheon", B),
                badge("Thu, Oct 1st &middot; 11:00 AM &ndash; 1:30 PM", B),
                p('<strong style="color:#FFFFFF;">Hyatt Regency Long Beach &middot; Beacon Ballroom</strong>', B, 0),
            ]), B, edit="luncheon"),
            luma(LUMA_SUMMIT, "Register for the Full-Day Summit", "See October 1st Options", B),
            r_pad(30),
        ], ground="blue"),

        # 4 — HONOREES
        section([
            r_text("\n".join([
                kicker("Celebrate LBA Honorees", W),
                display("Congratulations to the 2026 LBA Honorees", W),
                p("Four visionary leaders who have led the way, blazed the trail, and stand among our top investors and founders. They are recognized at the Awards Luncheon on October 1st.", W, 0),
            ]), W, edit="honorees_intro"),
            r_honorees(W),
            r_pad(30),
        ]),

        # 5 — THE FULL SUMMIT DAY, directly under the honorees it recognises
        section([
            r_text("\n".join([
                kicker("The Summit", T),
                display("Thursday, October 1st", T),
                badge("11:00 AM &ndash; 6:00 PM", T),
                p('The Summit closes out Long Beach Tech Week. It celebrates the LBA honorees at the Awards Luncheon, and the <strong style="color:#204396;">LBA Visionary Investors Panel</strong>, our signature afternoon forum, is a conversation with visionary investors on the global economy and emerging technology, including a special preview of LA2028 Olympic and Paralympic opportunities.', T, 0),
            ]), T, edit="summit"),
            r_pad(30),
        ], ground="tint"),

        # 6 — SPONSORSHIP
        section([
            r_text("\n".join([
                kicker("For Organizations", W),
                display("Become a Sponsor", W),
                p("Sponsorships are available at several levels, each carrying recognition across Long Beach Tech Week, the LBA Investors and Founders Summit, and partnership throughout the year. Benefits include presenting recognition, speaking opportunities in the 2026&ndash;2027 LBA forum, access to the Founders Roundtable, and placement across LBA communications.", W, 0),
            ]), W, edit="sponsorship"),
            r_button("View Sponsorship Opportunities", PACK, W),
            r_pad(30),
        ]),

        # 7 — HOST, PARTNERS, SPONSORS
        r_logos(),
    ],
)

# ==================== TUESDAY, SEPT 22 — RENÉ, SESSION 2 =====================
# Session 2 runs tomorrow, so it leads. Copy is Alma's, verbatim where it is
# hers; the bio is the fuller one from the series doc rather than the two
# lines the flyer carries. Runs tight.
CAMPAIGNS["2026-09-22-rene"] = dict(
    title="Session 2 with René Redwood is tomorrow",
    subject="Session 2 with René Redwood is tomorrow",
    alts=["Tomorrow: people, AI and workforce capacity",
          "René Redwood is on Zoom tomorrow at 11",
          "Good for Business: tomorrow, 11 to 1"],
    preheader="Good for Business: Investing in People and AI as Workforce Capacity. Wednesday, 11:00 to 1:00 on Zoom.",
    send="Tuesday, September 22, 2026, morning",
    tight=True,
    images=["lba-logo.png", "ai-session2.jpg", "ai-session3.jpg",
            "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        # 1 — TOMORROW
        section([
            r_image("ai-session2.jpg", S2_ALT, href=AI_S2),
            r_button("Register for Session&nbsp;2", AI_S2, W, pad_top=26),
            r_text("\n".join([
                kicker("Building an AI-Ready Trusted Business", W),
                display("Session 2 Is Tomorrow", W),
                badge("Wed, Sept 23 &middot; 11:00 AM &ndash; 1:00 PM PT &middot; Zoom", W),
                lead("Good for Business: Investing in People and AI as Workforce Capacity.", W),
                p("Build the workforce capacity your business needs to deliver consistently and grow sustainably. Owners will explore how people, culture, collaboration, external relationships, and practical AI tools can improve workflow, save time, reduce overwhelm, strengthen service quality, and support better business results.", W),
                label("In this session, you will:", W),
                bullets(["Assess your current workforce capacity and identify opportunities for improvement",
                         "Strengthen your team, culture, and collaboration for better results",
                         "Leverage practical AI tools to save time and improve productivity",
                         "Build strong external relationships that support growth",
                         "Create systems that support consistency, quality, and scalability"], W),
            ]), W, edit="session2"),
            r_text(p("Join this session to strengthen how your people, systems, and AI tools work together so your business can save time, deliver better service, and grow with greater confidence.", W, 0),
                   W, edit="session2_cta", pad="22px 40px 0 40px"),
            r_pad(30),
        ]),

        # 2 — RENÉ (the one blue band)
        section([
            r_text("\n".join([
                kicker("Facilitated By", B),
                display("Ren&eacute; Redwood", B),
                p("A recognized leader in strategic initiatives that drive judicial, legislative, commercial, and political achievements for organizations in the public and private sectors. Her expertise centers on building trust with internal and external stakeholders, and on winning in the marketplace.", B),
                label("Selected experience:", B),
                bullets(["Directed the Presidential Glass Ceiling Commission",
                         "Served on the court-appointed Coca-Cola Task Force",
                         "Chaired the Equality Task Force for a National Security Agency",
                         "Serves on the Ms. Foundation for Women Investment Committee and the Ms. Action Fund"], B),
            ]), B, edit="rene"),
            r_text(p("Honored by the Smithsonian Institute and the Ford Motor Company Fund as a &ldquo;Freedom&rsquo;s Sister,&rdquo; she is recognized for continuing the legacy of trailblazing African American women. Her work has been highlighted in Time, Elle, Essence, Black Enterprise and on the NASDAQ billboard on Wall Street.", B, 0),
                   B, edit="rene_press", pad="22px 40px 0 40px"),
            r_pad(34),
        ], ground="blue"),

        # 3 — THE SERIES
        section([
            r_text("\n".join([
                p("This three-part learning journey is designed for small business owners who want to grow enterprises that are rooted in their values, strong in day-to-day operations, and positioned to win trust in the marketplace.", T),
                p("Participants leave with practical tools, clearer language, and concrete next steps they can use immediately to strengthen how their companies operate, compete, and grow.", T, 0),
            ]), T, edit="series_intro"),
            r_text(series_table(T, start=2), T, edit="series", pad="24px 16px 0 16px"),
            r_pad(30),
        ], ground="tint"),

        # 4 — SESSION 3
        section([
            r_image("ai-session3.jpg", S3_ALT, href=AI_S3),
            r_text("\n".join([
                kicker("Next in the Series", W),
                display("Authority Positioning and Strategic Visibility", W),
                badge("Thu, Oct 8 &middot; 12:00 &ndash; 2:00 PM PT &middot; Zoom", W),
                p("Position your business so the right customers, partners, funders, and decision-makers understand your value and trust your expertise. Owners will strengthen credibility, refine messaging, show proof of results, and use strategic visibility to attract better opportunities, support stronger pricing, increase repeat business, and build long-term market trust.", W, 0),
            ]), W, edit="session3"),
            r_button("Register for Session&nbsp;3", AI_S3, W),
            r_pad(30),
        ]),

        # 5 — TECH WEEK
        section([
            r_text("\n".join([
                kicker("Also Ahead", T),
                display("Long Beach Tech Week 2026", T),
                p(f'Long Beach Tech Week runs <strong style="color:{BLUE};">September 28th &ndash; October 1st</strong>, closing with the 3rd Annual LBA Investors &amp; Founders Summit and the Awards Luncheon.', T, 0),
            ]), T, edit="ps"),
            r_button("Register for Long Beach Tech Week", TW, T, invert=True),
            r_pad(30),
        ], ground="tint"),
    ],
)

# ================== THURSDAY, SEPT 24 — THE THREE DAYS =======================
# Modelled on the Luma mail CSULB sent their registrants, which Vivian asked us
# to match: lay the three days out plainly so someone holding a ticket to one
# can see the other two. Day structure and wording follow Ingrid's email, which
# is the co-host's own account of what runs when.
CAMPAIGNS["2026-09-24-three-days"] = dict(
    title="Three days at Long Beach Tech Week",
    subject="Three days at Long Beach Tech Week",
    alts=["Pick your days: Sept 28th, 30th and Oct 1st",
          "Long Beach Tech Week starts Monday",
          "Registered for one day? There are three"],
    preheader="September 28th, 30th and October 1st. Registered for one day already? Here is everything else.",
    send="Thursday, September 24, 2026, morning",
    tight=True,
    images=(["lba-logo.png", "techweek-2026-banner.jpg", "honoree-hacegaba.jpg",
             "honoree-marshall.jpg", "honoree-lee.jpg", "honoree-glass.jpg"]
            + LOGO_IMAGES + ["icon-linkedin.png", "icon-email.png", "icon-web.png"]),
    sections=[
        section([
            r_image("techweek-2026-banner.jpg", TW_REG_ALT, href=TW),
            r_button("See the Full Schedule", TW, W, pad_top=26),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Three Days. Pick the Ones That Fit.", W),
                badge("Sept 28th &middot; Sept 30th &middot; Oct 1st", W),
                lead("Three days of innovation, entrepreneurship, investment, and connection, bringing together founders, investors, students, industry leaders, and the Southern California startup community.", W),
                p("Already registered for one day? There is more happening across the week. Each day takes its own registration, so add the ones you want below.", W, 0),
            ]), W, edit="intro"),
            r_pad(30),
        ]),

        section([
            r_text("\n".join([
                kicker("Day 1 &middot; Monday, September 28th", T),
                display("Opening Reception", T),
                bullets(["Kick off Long Beach Tech Week at the Opening Reception",
                         "Network with founders, investors, and members of the innovation community",
                         "Get a first look at the new Innovation Hub"], T),
            ]), T, edit="day1"),
            r_button("Register for the Opening Reception", LUMA_RECEPTION, T),
            r_pad(30),
        ], ground="tint"),

        section([
            r_text("\n".join([
                kicker("Day 2 &middot; Wednesday, September 30th", W),
                display("Capital Corner and CSU Demo Day", W),
                bullets(["Start the day at Capital Corner, built for founders at every stage who want to learn more about funding and growth",
                         "Watch CSU Demo Day as selected CSU founders take the stage to pitch their startups",
                         "Meet and connect with founders, investors, and members of the startup ecosystem",
                         "Keep the conversations going at the Networking Reception"], W),
            ]), W, edit="day2"),
            luma(LUMA_DAY2, "Register for Day 2", "See Day 2 on the Schedule", W),
            r_pad(30),
        ]),

        section([
            r_text("\n".join([
                kicker("Day 3 &middot; Thursday, October 1st", B),
                display("LBA Investors &amp; Founders Summit", B),
                bullets(["Join the 3rd Annual LBA Investors &amp; Founders Summit, 11:00 AM to 6:00 PM",
                         "Celebrate the 2026 LBA Honorees at the Awards Luncheon",
                         "Hear from leaders shaping the future of startup investment at the Visionary Investors Panel",
                         "Wrap up three days of ideas and connections at the Closing Reception"], B),
            ]), B, edit="day3"),
            luma(LUMA_SUMMIT, "Register for the Full Day", "See October 1st Options", B),
            r_button("Visionary Investors Panel Only", LUMA_PANEL, B, invert=True, pad_top=14),
            r_pad(30),
        ], ground="blue"),

        section([
            r_text("\n".join([
                kicker("Celebrate LBA Honorees", W),
                display("Congratulations to the 2026 LBA Honorees", W),
                p("Four visionary leaders who have led the way, blazed the trail, and stand among our top investors and founders. They are recognized at the Awards Luncheon on October 1st.", W, 0),
            ]), W, edit="honorees_intro"),
            r_honorees(W),
            r_pad(30),
        ]),

        r_logos(),
    ],
)

def build(slug, spec):
    out = os.path.join(HERE, f"{slug}-eblast", "email-package")
    imgs = os.path.join(out, "images")
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    os.makedirs(imgs, exist_ok=True)
    foot = FOOT_TMPL.replace("{permission_line}", spec.get("permission_line", PERMISSION_OPTIN))
    html = head_html(spec["title"], spec["preheader"]) + "".join(spec["sections"]) + foot
    if spec.get("tight"):
        html = tighten(html)
    with open(os.path.join(out, "email.html"), "w", encoding="utf-8") as f:
        f.write(html)
    for name in spec["images"]:
        shutil.copy2(os.path.join(ASSETS, name), os.path.join(imgs, name))
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_for(slug, spec))
    zpath = os.path.join(HERE, f"{slug}-eblast", f"lba-eblast-{slug}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(out, "email.html"), "email.html")
        z.write(os.path.join(out, "README.md"), "README.md")
        for name in spec["images"]:
            z.write(os.path.join(imgs, name), f"images/{name}")
    return zpath, len(html), re.findall(r'href="([^"]+)"', html)


def readme_for(slug, spec):
    alts = "\n".join(f"- {a}" for a in spec["alts"])
    return f"""# LBA E-Blast — {slug} — Mailchimp Package

Generated by `marketing/mailchimp/build.py`. Edit the campaign spec there and re-run rather
than hand-editing `email.html`, so the chrome stays in sync across sends.

## Campaign settings

| Field | Value |
|---|---|
| Subject | {spec['subject']} |
| Preview text | Baked into the HTML as a hidden preheader. Leave Mailchimp's own field blank, or set it — it takes precedence. Setting both can show them back to back. |
| Send | {spec['send']} |
| From | Long Beach Accelerator / info@lbaccelerator.org |

Subject line alternates:

{alts}

Preheader in this template:

> {spec['preheader']}

## Load it into Mailchimp

**Content → Email templates → Create Template → Code your own → Import Zip**, upload
`lba-eblast-{slug}.zip`, then start a campaign from the saved template. Mailchimp uploads the
images and rewrites the paths. Content blocks are marked `mc:edit`, so copy stays editable in
the visual editor while the layout stays put.

## Design

**Three grounds.** Sections sit on white, Light Gray `{PANEL}`, or a reversed LBA Blue band.
The blue band is the emphasis device and there is one per email, on whatever that send is
actually asking for — the honorees on 9/10, Session 1 on 9/14, René Redwood on the 9/14 René
edition, the honorees again on 9/18. Used more than that it stops being emphasis.

**Reversed palette.** Brand teal on LBA Blue measures 2.23:1 and fails outright, so kickers
and bullets on the blue band use `{R_KICK}`, a light tint of it, at 5.52:1. Body there is
`{R_BODY}` at 7.55:1 and headlines are white at 9.11:1. Buttons invert to a white field with
blue text.

**Display headlines** are 34px on 41px, dropping to 26px on phones — large enough to carry a
section on their own.

**Date badges** are filled chips, teal on light grounds and white on blue. Every event section
leads with one, so the deadline is the first thing the eye lands on rather than something
buried in a details block.

Series rows carry solid teal numerals; honoree awards sit in filled ribbons under each photo.

Per the LBA Brand Guidelines (08/31/26): LBA Blue `{BLUE}`, LBA Teal `{TEAL}`, Charcoal
`{CHAR}`, Medium Gray `{GRAY}`, Light Gray `{PANEL}`. Proxima Nova leads the font stack with
web-safe fallbacks — Outlook and Gmail ignore webfonts, so most readers see Helvetica or Arial.

Everything here is `<td>` background colours and solid fills, which Outlook renders. No
gradients, no background images, no CSS that degrades to an unreadable band.

## Before you send

- [ ] Every link click-tested from a test send. None are verifiable from the drafting
      environment, whose network policy blocks all of these hosts.
- [ ] **Google Drive sponsorship packet opens while signed out** (incognito test). Drive links
      default to restricted.
- [ ] Test send to yourself and one colleague; open it on a phone.
- [ ] Check the blue bands in Outlook specifically — reversed type is where a client with its
      own ideas about backgrounds would show up first.
- [ ] Confirm the schedule matches the send time above — the copy is dated.
"""


if __name__ == "__main__":
    for slug, spec in CAMPAIGNS.items():
        z, n, hrefs = build(slug, spec)
        print(f"{slug}: {os.path.relpath(z, HERE)}  ({n:,} chars, {len(hrefs)} links)")
    missing = [n for n, v in (("LUMA_SUMMIT", LUMA_SUMMIT), ("LUMA_DAY2", LUMA_DAY2)) if v is None]
    if missing:
        print(f"\n  note: {', '.join(missing)} unset. Those buttons fall back to the Tech Week"
              f"\n        page with a label that only promises a schedule, not registration.")
    if not AERO_HAS_IMG:
        print(f"\n  note: _assets/{AERO_IMG} is missing, so the 9/17 aerospace send was"
              f"\n        built as live text only. Drop the flyer in at that path and"
              f"\n        re-run to place it at the top of that email.")
