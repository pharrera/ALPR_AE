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

FONT = "'Proxima Nova','Helvetica Neue',Helvetica,Arial,sans-serif"
BODY = "font-size:16px;line-height:27px"
SMALL = "font-size:15px;line-height:25px"


def ink(ground):
    """Colour roles for a given section ground."""
    if ground == "blue":
        return dict(bg=BLUE, kick=R_KICK, head=WHITE, body=R_BODY, strong=WHITE,
                    mark=R_KICK, muted=R_MUTED, card=WHITE, card_ink=CHAR,
                    link=WHITE, btn_bg=WHITE, btn_ink=BLUE, hair="#4763A9")
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


FOOT = f"""  <tr>
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
                    &copy; *|CURRENT_YEAR|* Long Beach Accelerator Inc.<br />
                    All rights reserved.<br />
                    You are receiving this email because you opted in via our website.
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
        out += f'  <tr><td style="font-size:0;line-height:0;height:4px;background-color:{BLUE};">&nbsp;</td></tr>\n'
    return out


def r_image(src, alt):
    return (f'        <tr><td align="center" style="font-size:0;line-height:0;">'
            f'<img src="images/{src}" width="600" alt="{alt}" style="width:100%;max-width:600px;height:auto;display:block;" />'
            f'</td></tr>\n')


def r_text(body, g, edit=None, pad="36px 40px 0 40px"):
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px"{e} style="padding:{pad};font-family:{FONT};{BODY};color:{g["body"]};">\n'
            f'{body}\n        </td></tr>\n')


def r_pad(px=36):
    return f'        <tr><td style="font-size:0;line-height:0;height:{px}px;">&nbsp;</td></tr>\n'


def r_button(label, href, g, invert=False):
    bg = g["btn_bg"] if not invert else TEAL
    fg = g["btn_ink"] if not invert else WHITE
    return (f'        <tr><td align="center" class="px btn" style="padding:28px 40px 0 40px;">\n'
            f'          <table role="presentation" border="0" cellpadding="0" cellspacing="0">\n'
            f'            <tr><td align="center" bgcolor="{bg}" style="border-radius:4px;">\n'
            f'              <a href="{href}" target="_blank" style="display:inline-block;padding:17px 40px;font-family:{FONT};font-size:16px;line-height:20px;font-weight:bold;letter-spacing:0.3px;color:{fg};text-decoration:none;border-radius:4px;">{label}</a>\n'
            f'            </td></tr>\n          </table>\n        </td></tr>\n')


def r_card(inner, g, edit=None):
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px" style="padding:28px 40px 0 40px;">\n'
            f'          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{g["card"]};border-left:5px solid {TEAL};">\n'
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


def details(date_, time_, loc, indent=12, bare=False):
    pad = " " * indent
    style = "" if bare else f' style="margin-top:20px;border-top:1px solid {PANEL_EDGE};"'
    cell = "padding:0;" if bare else "padding:18px 0 0 0;"
    return (f'{pad}<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"{style}>'
            f'<tr><td style="{cell}{SMALL};color:{CHAR};">'
            f'<strong style="color:{BLUE};">Date:</strong> {date_}<br />'
            f'<strong style="color:{BLUE};">Time:</strong> {time_}<br />'
            f'<strong style="color:{BLUE};">Location:</strong> {loc}</td></tr></table>')


def series_table(g):
    rows = [("1", "Purpose, People, and AI: Building the Foundation of a Trusted Business", "Tue, Sept 15, 2026", "10:00 &ndash; 11:30 AM PT"),
            ("2", "Good for Business: Investing in People and AI as Workforce Capacity", "Wed, Sept 23, 2026", "11:00 AM &ndash; 1:00 PM PT"),
            ("3", "Authority Positioning and Strategic Visibility to Yield Market Trust", "Thu, Oct 8, 2026", "12:00 &ndash; 2:00 PM PT")]
    out = ""
    for i, (n, t, d, tm) in enumerate(rows):
        border = "" if i == len(rows) - 1 else f"border-bottom:1px solid {RULE};"
        out += (f'        <tr>'
                f'<td width="52" valign="top" bgcolor="{TEAL}" style="width:52px;background-color:{TEAL};text-align:center;font-size:20px;line-height:24px;color:#FFFFFF;font-weight:bold;padding:18px 0;">{n}</td>'
                f'<td style="padding:18px 18px 18px 16px;font-size:14px;line-height:22px;color:{CHAR};{border}">'
                f'<strong style="color:{BLUE};font-size:15px;">{t}</strong><br />{d} &nbsp;&middot;&nbsp; {tm}</td></tr>\n')
    return (f'      <p style="margin:0 0 6px 0;font-size:12px;line-height:16px;letter-spacing:1.8px;text-transform:uppercase;color:{g["kick"]};font-weight:bold;">The full series</p>\n'
            f'      <p style="margin:0 0 18px 0;font-size:18px;line-height:27px;color:{g["strong"]};font-weight:bold;">Mark your calendars for Rene Redwood&rsquo;s three-part series.</p>\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{WHITE};border:1px solid {RULE};">\n{out}      </table>\n'
            f'      <p style="margin:14px 0 0 0;font-size:14px;line-height:22px;color:{g["muted"]};">All sessions via Zoom. '
            f'Register for Sessions 2 and 3 at <a href="https://lbaccelerator.org/events" target="_blank" style="color:{g["link"]};">lbaccelerator.org/events</a>.</p>')


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
PACK = "https://drive.google.com/file/d/1brJxClWdJ9efsuH7RnPNsjyxDq5224CC/view"
TW   = "https://longbeachtechweek.com"
FORM = "https://hub.catalyzerapp.com/public/form/46c9cb88-0c9a-4eac-9346-f53f61f511d6"
EVT  = "https://lbaccelerator.org/events"
LUM  = "https://www.lumen21.com/"

RENE = ("Rene Redwood is a recognized leader in advancing equity, inclusive workplace culture, and strategic "
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

HERO_ALT = ("Building an AI-Ready Trusted Business: a three-part learning journey for small business owners, "
            "facilitated by Rene Redwood. Hosted by the Long Beach Accelerator.")
CONTRACT_ALT = ("Contracting and Procurement Readiness Series, Session 2: Preparing to Pursue the Work. "
                "Thursday, September 10, 4:00 to 5:30 PM PT, online via Zoom, featuring LBA Business Adviser Ronda Jackson.")
TW_ALT = ("Long Beach Tech Week 2026 Sponsorship Opportunities, hosted by the Long Beach Accelerator, "
          "September 28 to October 1, 2026.")

W, T, B = ink("white"), ink("tint"), ink("blue")

CAMPAIGNS = {}

# ============================ THURSDAY, SEPT 10 ==============================
# Copy sourced from the 2026 LBTW / LBA Summit sponsorship flyer (090126).
CAMPAIGNS["2026-09-10"] = dict(
    title="Long Beach Tech Week 2026 & What's Ahead",
    subject="Long Beach Tech Week, the 2026 LBA honorees, and today at 4 PM",
    alts=["Put your organization at the center of our innovation ecosystem",
          "Meet the 2026 LBA honorees",
          "Sponsorship opportunities are open for Long Beach Tech Week"],
    preheader="Tech Week runs Sept 28 - Oct 1, sponsorship opportunities are open, and contracting readiness is this afternoon.",
    send="Thursday, September 10, 2026, 8:00 AM PT",
    images=["lba-logo.png", "techweek-2026.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "contracting-session2.jpg",
            "hero-ai-title.jpg", "hero-ai-rene.jpg",
            "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        # 1 — LONG BEACH TECH WEEK
        section([
            r_image("techweek-2026.jpg", TW_ALT),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Put Your Organization at the Center of Our Innovation Ecosystem", W),
                badge("Sept 28 &ndash; Oct 1, 2026 &middot; Long Beach, CA", W),
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
                p("Sponsorships are available at several levels, each carrying recognition across Tech Week and at the Summit:", T),
            ]), T, edit="sponsorship"),
            r_text(f'      Benefits include presenting recognition, speaking opportunities in the 2026&ndash;2027 LBA forum, access to the Founders Roundtable, Summit registrations, and placement across LBA communications. See the <a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">full sponsorship opportunities</a> for what each level carries.',
                   T, edit="packet_line", pad="24px 40px 0 40px"),
            r_button("View Sponsorship Opportunities", PACK, T),
            r_pad(38),
        ], ground="tint"),

        # 3 — HONOREES
        section([
            r_text("\n".join([
                kicker("Celebrate the 2026 Class", B),
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
                badge("Thu, Oct 1 &middot; 11:00 AM &ndash; 6:00 PM", W),
                p("<strong style=\"color:#204396;\">Hyatt Regency Long Beach &middot; Beacon Ballroom</strong>", W),
                p("The Summit closes out Long Beach Tech Week. The <strong style=\"color:#204396;\">LBA Visionary Investors Panel</strong>, our signature afternoon forum, is a conversation with visionary investors on the global economy and emerging technology &mdash; including a special preview of LA2028 Olympics opportunities.", W, 0),
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
                lead("It's not too late to join us.", T),
                p('Session 2 of our Contracting &amp; Procurement Readiness Series runs this afternoon: <em>Preparing to Pursue the Work, Evaluate Opportunities, Respond Strategically, and Prepare to Perform.</em>', T),
                label("In this session, you will:", T),
                bullets(["Evaluate opportunities and respond strategically",
                         "Understand key requirements, capacity, pricing, and teaming considerations",
                         "Prepare to perform successfully and build toward future opportunities"], T),
            ]), T, edit="contracting"),
            r_card(details("Thursday, September 10, 2026", "4:00 &ndash; 5:30 PM PT", "Online via Zoom", indent=12, bare=True), T),
            r_button("Register Now", S2C, T),
            r_text(bio("the facilitator", RONDA, T), T, edit="ronda", pad="26px 40px 0 40px"),
            r_pad(36),
        ], ground="tint"),

        # 6 — RENE REDWOOD: AI-READY SERIES (banner split vertically to stay legible)
        section([
            r_image("hero-ai-title.jpg", HERO_ALT),
            r_image("hero-ai-rene.jpg", "Facilitated by Rene Redwood, a recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results."),
            r_text("\n".join([
                kicker("A New Three-Part Learning Series", W),
                display("Building an AI-Ready Trusted Business", W),
                badge("Starts Tue, Sept 15 &middot; 10:00 AM PT", W),
                p("Join us for a new three-part learning series facilitated by <strong style=\"color:#204396;\">Rene Redwood</strong> and designed to help small business owners strengthen how they operate, compete, and grow.", W),
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
            r_text(series_table(W), W, edit="series"),
            r_pad(36),
        ]),

        # 7 — BUSINESS ADVISORY
        section([
            r_text("\n".join([
                kicker("Business Advisory Services", T),
                display("Business Advisory Intake Form", T),
                p("We provide no-cost, one-on-one business advising for emerging technology companies and innovation-driven small businesses. Whether you're preparing for growth, exploring debt or equity financing, integrating AI into your operations, pursuing contract opportunities, or developing a long-term business strategy, our experienced advisors are here to help.", T),
                p(f'Complete our <a href="{FORM}" target="_blank" style="color:{BLUE};text-decoration:underline;">business advisory intake form</a> to get matched with the advisor best suited to your goals.', T, 0),
            ]), T, edit="advising"),
            r_button("Register for Business Advisor Services", FORM, T, invert=True),
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
    preheader="Ninety minutes on Zoom with Rene Redwood. Session 1 of three, and there's still room.",
    send="Monday, September 14, 2026, 8:00 AM PT",
    images=["lba-logo.png", "hero-ai-title.jpg", "hero-ai-rene.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([
            r_image("hero-ai-title.jpg", HERO_ALT),
            r_image("hero-ai-rene.jpg", "Facilitated by Rene Redwood, a recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results."),
            r_text("\n".join([
                kicker("Starts Tomorrow", W),
                display("Building an AI-Ready Trusted Business", W),
                badge("Tue, Sept 15 &middot; 10:00 &ndash; 11:30 AM PT", W),
                lead("Ninety minutes on Zoom with Rene Redwood, built around your business rather than a slide deck.", W),
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
            r_text(series_table(W), W, edit="series"),
            r_pad(36),
        ]),

        section([
            r_text(f'      <p style="margin:0;{SMALL};color:{CHAR};"><strong style="color:{BLUE};">Also ahead:</strong> '
                   f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Long Beach Tech Week</a> runs September 28 &ndash; October 1, and '
                   f'<a href="{PACK}" target="_blank" style="color:{BLUE};text-decoration:underline;">sponsorships are open</a>.</p>',
                   T, edit="ps"),
            r_pad(36),
        ], ground="tint"),
    ],
)

# ============================ FRIDAY, SEPT 18 ================================
CAMPAIGNS["2026-09-18"] = dict(
    title="Sponsor Long Beach Tech Week 2026",
    subject="Ten days to Tech Week — sponsorships are open",
    alts=["Put your brand at the center of LB Tech Week",
          "Sponsor Long Beach Tech Week 2026",
          "Meet the 2026 Summit honorees"],
    preheader="Sept 28 - Oct 1. Sponsors join founders, investors, and civic leaders - and sit in the room for the Summit.",
    send="Friday, September 18, 2026, 8:00 AM PT",
    images=["lba-logo.png", "techweek-2026.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([
            r_image("techweek-2026.jpg", TW_ALT),
            r_text("\n".join([
                kicker("Long Beach Tech Week 2026", W),
                display("Put Your Organization at the Center of Long Beach's Innovation Ecosystem", W),
                badge("Sept 28 &ndash; Oct 1 &middot; Long Beach, CA", W),
                lead("Tech Week is ten days out, and sponsorships are open.", W),
                p(f'<a href="{TW}" target="_blank" style="color:{BLUE};text-decoration:underline;">Tech Week 2026</a> draws founders, investors, business leaders, tech experts, entrepreneurs, educators, creatives, and civic leaders for a multi-day experience showcasing the people, ideas, and industries shaping our region\'s future.', W),
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
                p("The Summit closes out Tech Week on <strong style=\"color:#FFFFFF;\">Thursday, October 1</strong> at the <strong style=\"color:#FFFFFF;\">Hyatt Regency Long Beach</strong>. Sponsors sit in the room as we recognize four leaders shaping the region's innovation economy.", B, 0),
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


def build(slug, spec):
    out = os.path.join(HERE, f"{slug}-eblast", "email-package")
    imgs = os.path.join(out, "images")
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    os.makedirs(imgs, exist_ok=True)
    html = head_html(spec["title"], spec["preheader"]) + "".join(spec["sections"]) + FOOT
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
actually asking for — the contents list and honorees on 9/10, Session 1 on 9/14, honorees on
9/18. Used more than that it stops being emphasis.

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
