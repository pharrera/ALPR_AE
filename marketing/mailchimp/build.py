#!/usr/bin/env python3
"""Build LBA Mailchimp e-blasts from shared brand chrome.

Each campaign is a spec in CAMPAIGNS: a preheader plus a list of sections. The
header, footer, palette, type scale and responsive rules live here once, so
every send renders identically and a design change is a one-line edit.

Run:  python3 build.py
"""
import os, re, shutil, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "_assets")

# --- LBA Brand Guidelines, 08/31/26 -----------------------------------------
BLUE, TEAL = "#204396", "#008C8C"
CHAR, GRAY = "#333333", "#6B7280"
PANEL = "#F2F4F5"
RULE, PANEL_EDGE = "#E3E6E9", "#DCE0E4"
WHITE = "#FFFFFF"
FONT = "'Proxima Nova','Helvetica Neue',Helvetica,Arial,sans-serif"
LINK = f'style="color:{BLUE};text-decoration:underline;"'

# Type scale. Body leading is 27 rather than 26 — at a 520px measure that is
# roughly 68 characters a line, and the extra point keeps it from packing.
BODY = "font-size:16px;line-height:27px"
SMALL = "font-size:15px;line-height:25px"


def head(title, preheader):
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
  body{{margin:0!important;padding:0!important;width:100%!important;background-color:#E6EAEE;}}
  a{{color:{BLUE};}}
  .lba-h1{{font-size:27px!important;line-height:34px!important;}}
  @media screen and (max-width:620px){{
    .wrap{{width:100%!important;}}
    .px{{padding-left:24px!important;padding-right:24px!important;}}
    .lba-h1{{font-size:23px!important;line-height:30px!important;}}
    .lba-h2{{font-size:19px!important;line-height:26px!important;}}
    .btn a{{display:block!important;}}
    .fstack{{display:block!important;width:100%!important;max-width:100%!important;text-align:center!important;padding:0 0 20px 0!important;}}
    .fstack img{{margin:0 auto!important;}}
    .fcenter table{{margin:0 auto!important;}}
    .hcell{{display:block!important;width:100%!important;max-width:100%!important;padding:0 0 26px 0!important;text-align:center!important;}}
    .hcell img{{margin:0 auto!important;}}
    .gut{{display:none!important;}}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:#E6EAEE;">

<!-- Preview text: shows in the inbox beside the subject line. -->
<div style="display:none;font-size:1px;color:#E6EAEE;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">
  {preheader}
  {'&#847;&zwnj;&nbsp;' * 20}
</div>

<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#E6EAEE;">
<tr><td align="center" style="padding:26px 10px;">

<table role="presentation" class="wrap" border="0" cellpadding="0" cellspacing="0" width="600" style="width:600px;max-width:600px;background-color:{WHITE};">

  <tr>
    <td align="center" class="px" style="padding:28px 32px 22px 32px;background-color:{WHITE};">
      <img src="images/lba-logo.png" width="220" alt="LBA Accelerator" style="width:220px;max-width:220px;height:auto;display:block;" />
    </td>
  </tr>
  <tr><td style="font-size:0;line-height:0;height:4px;background-color:{TEAL};">&nbsp;</td></tr>
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
                  <img src="images/lba-logo.png" width="200" alt="LBA Accelerator" style="width:200px;max-width:200px;height:auto;display:block;" />
                </td>
                <td class="fstack" align="right" valign="top" mc:edit="footer_legal" style="font-family:{FONT};font-size:13px;line-height:22px;color:{GRAY};text-align:right;">
                  <p style="margin:0 0 14px 0;">
                    &copy; *|CURRENT_YEAR|* Long Beach Accelerator Inc.<br />
                    All rights reserved.<br />
                    You are receiving this email because you opted in via our website.
                  </p>
                  <p style="margin:0 0 14px 0;">
                    Our mailing address is:<br />
                    Long Beach Accelerator Inc.<br />
                    245 E. 3rd St<br />
                    Long Beach, CA 90802
                  </p>
                  <p style="margin:0 0 14px 0;"><a href="*|LIST:ADDRESS_VCARD|*" style="color:{BLUE};text-decoration:underline;">Add us to your address book</a></p>
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
# Every section is one tinted or white band. Alternating the ground is what
# separates sections in a long email; hairline rules cannot carry that weight.

def section(rows, tint=False):
    bg = PANEL if tint else WHITE
    return (f'  <tr>\n    <td style="background-color:{bg};">\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n'
            + "".join(rows) +
            f'      </table>\n    </td>\n  </tr>\n')


def r_image(src, alt):
    return (f'        <tr><td align="center" style="font-size:0;line-height:0;">'
            f'<img src="images/{src}" width="600" alt="{alt}" style="width:100%;max-width:600px;height:auto;display:block;" />'
            f'</td></tr>\n')


def r_text(body, edit=None, pad="34px 40px 0 40px"):
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px"{e} style="padding:{pad};font-family:{FONT};{BODY};color:{CHAR};">\n'
            f'{body}\n        </td></tr>\n')


def r_pad(px=34):
    return f'        <tr><td style="font-size:0;line-height:0;height:{px}px;">&nbsp;</td></tr>\n'


def r_button(label, href, color=None):
    c = color or BLUE
    return (f'        <tr><td align="center" class="px btn" style="padding:26px 40px 0 40px;">\n'
            f'          <table role="presentation" border="0" cellpadding="0" cellspacing="0">\n'
            f'            <tr><td align="center" bgcolor="{c}" style="border-radius:4px;">\n'
            f'              <a href="{href}" target="_blank" style="display:inline-block;padding:16px 38px;font-family:{FONT};font-size:16px;line-height:20px;font-weight:bold;color:#FFFFFF;text-decoration:none;border-radius:4px;">{label}</a>\n'
            f'            </td></tr>\n          </table>\n        </td></tr>\n')


def r_card(inner, edit=None, on_tint=False):
    """A bordered card. Sits white on a tinted band, tinted on a white one."""
    bg = WHITE if on_tint else PANEL
    e = f' mc:edit="{edit}"' if edit else ""
    return (f'        <tr><td class="px" style="padding:26px 40px 0 40px;">\n'
            f'          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{bg};border-left:4px solid {TEAL};">\n'
            f'            <tr><td{e} style="padding:26px 28px;font-family:{FONT};{SMALL};color:{CHAR};">\n'
            f'{inner}\n            </td></tr>\n          </table>\n        </td></tr>\n')


# --- content pieces ----------------------------------------------------------

def kicker(t):
    """Short teal rule over an uppercase label — marks where a section starts."""
    return (f'      <table role="presentation" border="0" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="44" style="width:44px;height:3px;background-color:{TEAL};font-size:0;line-height:0;">&nbsp;</td>'
            f'</tr></table>\n'
            f'      <p style="margin:16px 0 8px 0;font-size:12px;line-height:16px;letter-spacing:1.6px;'
            f'text-transform:uppercase;color:{TEAL};font-weight:bold;">{t}</p>')


def h1(t):
    return (f'      <h1 class="lba-h1" style="margin:0 0 16px 0;font-family:{FONT};font-size:27px;'
            f'line-height:34px;color:{BLUE};font-weight:bold;">{t}</h1>')


def h2(t):
    return (f'      <h2 class="lba-h2" style="margin:0 0 12px 0;font-size:20px;line-height:28px;'
            f'color:{BLUE};font-weight:bold;">{t}</h2>')


def p(t, mb=16):
    return f'      <p style="margin:0 0 {mb}px 0;">{t}</p>'


def lead(t, mb=16):
    """A slightly larger opening line."""
    return f'      <p style="margin:0 0 {mb}px 0;font-size:18px;line-height:29px;color:{CHAR};">{t}</p>'


def bullets(items, indent=6):
    pad = " " * indent
    rows = ""
    for i, it in enumerate(items):
        gap = "0" if i == len(items) - 1 else "0 0 10px 0"
        rows += (f'{pad}  <tr><td width="18" valign="top" style="padding:{gap};color:{TEAL};{SMALL};">&bull;</td>'
                 f'<td style="padding:{gap};{SMALL};color:{CHAR};">{it}</td></tr>\n')
    return f'{pad}<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">\n{rows}{pad}</table>'


def label(t, indent=6):
    return " " * indent + f'<p style="margin:0 0 10px 0;font-weight:bold;color:{BLUE};">{t}</p>'


def details(date_, time_, loc, indent=12):
    pad = " " * indent
    return (f'{pad}<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" '
            f'style="margin-top:18px;border-top:1px solid {PANEL_EDGE};"><tr><td style="padding:16px 0 0 0;{SMALL};color:{CHAR};">'
            f'<strong style="color:{BLUE};">Date:</strong> {date_}<br />'
            f'<strong style="color:{BLUE};">Time:</strong> {time_}<br />'
            f'<strong style="color:{BLUE};">Location:</strong> {loc}</td></tr></table>')


def series_table():
    rows = [("1", "Purpose, People, and AI: Building the Foundation of a Trusted Business", "Tue, Sept 15, 2026", "10:00 &ndash; 11:30 AM PT"),
            ("2", "Good for Business: Investing in People and AI as Workforce Capacity", "Wed, Sept 23, 2026", "11:00 AM &ndash; 1:00 PM PT"),
            ("3", "Authority Positioning and Strategic Visibility to Yield Market Trust", "Thu, Oct 8, 2026", "12:00 &ndash; 2:00 PM PT")]
    out = ""
    for i, (n, t, d, tm) in enumerate(rows):
        border = "" if i == len(rows) - 1 else f"border-bottom:1px solid {RULE};"
        out += (f'        <tr><td width="40" valign="top" style="padding:16px 0 16px 16px;font-size:15px;line-height:22px;color:{TEAL};font-weight:bold;">{n}</td>'
                f'<td style="padding:16px 16px 16px 4px;font-size:14px;line-height:22px;color:{CHAR};{border}">'
                f'<strong style="color:{BLUE};">{t}</strong><br />{d} &nbsp;&middot;&nbsp; {tm}</td></tr>\n')
    return (f'      <p style="margin:0 0 14px 0;font-size:15px;line-height:22px;color:{BLUE};font-weight:bold;">The full series</p>\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{WHITE};border:1px solid {RULE};">\n{out}      </table>\n'
            f'      <p style="margin:12px 0 0 0;font-size:14px;line-height:22px;color:{GRAY};">All sessions via Zoom. '
            f'Register for Sessions 2 and 3 at <a href="https://lbaccelerator.org/events" target="_blank" style="color:{BLUE};">lbaccelerator.org/events</a>.</p>')


def bio(name, text):
    return (f'      <p style="margin:0;font-size:14px;line-height:23px;color:{GRAY};">'
            f'<strong style="color:{BLUE};">About {name}.</strong> {text}</p>')


def contents(items):
    """An orientation list for a long roundup — what is in here, in order."""
    rows = ""
    for i, (t, meta) in enumerate(items):
        gap = "0" if i == len(items) - 1 else "0 0 12px 0"
        rows += (f'        <tr><td width="26" valign="top" style="padding:{gap};font-size:14px;line-height:22px;color:{TEAL};font-weight:bold;">{i+1}</td>'
                 f'<td style="padding:{gap};font-size:14px;line-height:22px;color:{CHAR};">'
                 f'<strong style="color:{BLUE};">{t}</strong><br /><span style="color:{GRAY};">{meta}</span></td></tr>\n')
    return (f'      <p style="margin:0 0 14px 0;font-size:12px;line-height:16px;letter-spacing:1.6px;'
            f'text-transform:uppercase;color:{TEAL};font-weight:bold;">In this email</p>\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">\n{rows}      </table>')


HONOREES = [("honoree-hacegaba.jpg", "2026 LBA Visionary of the Year", "Dr. Noel Hacegaba", "Chief Executive Officer<br />Port of Long Beach"),
            ("honoree-marshall.jpg", "2026 LBA Trailblazer of the Year", "Carrie Marshall", "Chief Executive Officer<br />Rebel Space"),
            ("honoree-lee.jpg", "2026 LBA Investor of the Year", "Joshua Lee", "Managing Partner<br />Gumshoe Ventures"),
            ("honoree-glass.jpg", "2026 LBA Founder of the Year", "Ethan Glass", "Chief Executive Officer<br />OCRA")]


def r_honorees():
    def cell(img, award, name, role):
        alt = f"{name}, {role.replace('<br />', ', ')}, {award}"
        return (f'              <td class="hcell" width="250" valign="top" style="width:250px;">\n'
                f'                <img src="images/{img}" width="250" alt="{alt}" style="width:100%;max-width:250px;height:auto;display:block;" />\n'
                f'                <p style="margin:14px 0 5px 0;font-family:{FONT};font-size:11px;line-height:15px;letter-spacing:1.3px;text-transform:uppercase;color:{TEAL};font-weight:bold;">{award}</p>\n'
                f'                <p style="margin:0 0 3px 0;font-family:{FONT};font-size:17px;line-height:24px;color:{BLUE};font-weight:bold;">{name}</p>\n'
                f'                <p style="margin:0;font-family:{FONT};font-size:14px;line-height:22px;color:{GRAY};">{role}</p>\n'
                f'              </td>')
    gut = '              <td class="gut" width="20" style="width:20px;font-size:0;line-height:0;">&nbsp;</td>'
    a, b, c, d = [cell(*h) for h in HONOREES]
    sp = '            <tr><td colspan="3" height="30" style="height:30px;font-size:0;line-height:0;">&nbsp;</td></tr>'
    return (f'        <tr><td class="px" style="padding:20px 40px 0 40px;">\n'
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

HERO_ALT = ("Building an AI-Ready Trusted Business: a three-part learning journey for small business owners, "
            "facilitated by Rene Redwood. Hosted by the Long Beach Accelerator.")
CONTRACT_ALT = ("Contracting and Procurement Readiness Series, Session 2: Preparing to Pursue the Work. "
                "Thursday, September 10, 4:00 to 5:30 PM PT, online via Zoom, featuring LBA Business Adviser Ronda Jackson.")
TW_ALT = ("Long Beach Tech Week 2026 Sponsorship Packet, hosted by the Long Beach Accelerator, "
          "September 28 to October 1, 2026.")

TW_BULLETS = ["Brand visibility throughout Long Beach Tech Week",
              "Recognition and engagement with founders, investors, and regional leaders",
              "Opportunities to participate in select programs, forums, and the 2026 Investors &amp; Founders Summit"]


CAMPAIGNS = {}

# ============================ THURSDAY, SEPT 10 ==============================
CAMPAIGNS["2026-09-10"] = dict(
    title="Upcoming Opportunities & LB Tech Week 2026",
    subject="Today at 4 PM, a new AI series, and Tech Week",
    alts=["Contracting starts at 4 PM — plus what's next",
          "Upcoming Opportunities & LB Tech Week 2026",
          "Meet the 2026 Summit honorees"],
    preheader="Contracting readiness is this afternoon. A three-part AI series starts 9/15, and Tech Week sponsorships are open.",
    send="Thursday, September 10, 2026, 8:00 AM PT",
    images=["lba-logo.png", "hero-ai-series.jpg", "contracting-session2.jpg", "techweek-2026.jpg",
            "honoree-hacegaba.jpg", "honoree-marshall.jpg", "honoree-lee.jpg", "honoree-glass.jpg",
            "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([r_text("\n".join([
            lead("There's a lot happening at the Long Beach Accelerator."),
            p("From building an AI-ready, trusted business and preparing for contracting opportunities to Long Beach Tech Week, we're connecting business owners and entrepreneurs with the tools, expertise, and opportunities they need to compete, grow, and thrive.", 0),
        ]), edit="intro"), r_pad(30)]),

        section([r_text(contents([
            ("Building an AI-Ready Trusted Business", "Three-part series &middot; starts Tue, Sept 15"),
            ("Contracting &amp; Procurement Readiness", "Session 2 &middot; today, 4:00 PM PT"),
            ("Long Beach Tech Week 2026", "Sept 28 &ndash; Oct 1 &middot; sponsorships open"),
            ("2026 Summit Honorees", "Announced &middot; Summit is Oct 1"),
            ("A New Tech Center", "Opening later this month"),
            ("No-Cost Business Advising", "Open year-round"),
        ]), edit="contents"), r_pad(32)], tint=True),

        section([
            r_image("hero-ai-series.jpg", HERO_ALT),
            r_text("\n".join([
                kicker("A New Three-Part Learning Series"),
                h1("Building an AI-Ready Trusted Business"),
                p("Join us for a new three-part learning series facilitated by <strong>Rene Redwood</strong> and designed to help small business owners strengthen how they operate, compete, and grow. The series begins <strong>Tuesday, September 15, 2026</strong>."),
                p("Across three sessions, participants will explore how purpose, people, leadership, AI, and strategic visibility can work together to build a stronger, more trusted business.", 0),
            ]), edit="ai_intro"),
            r_card("\n".join([
                f'              <p style="margin:0 0 6px 0;font-size:12px;line-height:16px;letter-spacing:1.6px;text-transform:uppercase;color:{TEAL};font-weight:bold;">Start with Session 1</p>',
                "            " + h2("Purpose, People, and AI: Building the Foundation of a Trusted Business").strip(),
                '            <p style="margin:0 0 16px 0;">What makes your business valuable, distinct, and worthy of trust? In this session, business owners will connect their personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how their company operates and grows.</p>',
                label("In this session, you will:", indent=12),
                bullets(S1_BULLETS, indent=12),
                details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Via Zoom"),
            ]), edit="session1"),
            r_button("Register for Session&nbsp;1", S1),
            r_text(series_table(), edit="series"),
            r_text(bio("the facilitator", RENE), edit="rene", pad="24px 40px 0 40px"),
            r_pad(34),
        ]),

        section([
            r_image("contracting-session2.jpg", CONTRACT_ALT),
            r_text("\n".join([
                kicker("Contracting &amp; Procurement Readiness"),
                h1("Prepare. Pursue. Perform."),
                f'      <p style="margin:0 0 16px 0;font-size:18px;line-height:29px;color:{TEAL};font-weight:bold;">It\'s not too late to join us today.</p>',
                p(f'Join us <strong>today, Thursday, September 10, 2026 at 4:00 PM</strong> for Session 2 of our Contracting &amp; Procurement Readiness Series: <em>Preparing to Pursue the Work, Evaluate Opportunities, Respond Strategically, and Prepare to Perform.</em>'),
                label("In this session, you will:"),
                bullets(["Evaluate opportunities and respond strategically",
                         "Understand key requirements, capacity, pricing, and teaming considerations",
                         "Prepare to perform successfully and build toward future opportunities"]),
            ]), edit="contracting"),
            r_card(details("Thursday, September 10, 2026", "4:00 &ndash; 5:30 PM PT", "Online via Zoom", indent=12).replace('style="margin-top:18px;border-top:1px solid ' + PANEL_EDGE + ';"', 'style=""').replace('padding:16px 0 0 0;', 'padding:0;'), on_tint=True),
            r_button("Register Now", S2C),
            r_text(bio("the facilitator", RONDA), edit="ronda", pad="24px 40px 0 40px"),
            r_pad(34),
        ], tint=True),

        section([
            r_image("techweek-2026.jpg", TW_ALT),
            r_text("\n".join([
                kicker("September 28 &ndash; October 1, 2026 &nbsp;&middot;&nbsp; Long Beach, CA"),
                h1("Put Your Organization at the Center of Long Beach's Innovation Ecosystem"),
                p(f'<a href="{TW}" target="_blank" {LINK}>Long Beach Tech Week 2026</a> draws founders, investors, business leaders, tech experts, entrepreneurs, educators, creatives, and civic leaders for a multi-day experience showcasing the people, ideas, and industries shaping our region\'s future.'),
                p("Hosted by the Long Beach Accelerator, Tech Week offers organizations a unique opportunity to build visibility, strengthen relationships, and connect directly with Long Beach's growing innovation and entrepreneurial ecosystem."),
                label("Sponsorship opportunities are available at multiple levels, offering benefits such as:"),
                bullets(TW_BULLETS),
            ]), edit="techweek"),
            r_text(f'      Explore the <a href="{PACK}" target="_blank" {LINK}>Long Beach Tech Week 2026 Sponsorship Packet</a> and join us as a partner.',
                   edit="packet_line", pad="20px 40px 0 40px"),
            r_button("View the Sponsorship Packet", PACK),
            r_pad(34),
        ]),

        section([
            r_text("\n".join([
                kicker("3rd Annual Investors &amp; Founders Summit"),
                h1("Meet the 2026 Honorees"),
                p("The Summit closes out Tech Week on <strong>Thursday, October 1</strong> at the <strong>Hyatt Regency Long Beach</strong>. Join us as we recognize four leaders shaping the region's innovation economy.", 0),
            ]), edit="honorees_intro"),
            r_honorees(),
            r_pad(34),
        ], tint=True),

        section([
            r_text("\n".join([
                kicker("Opening Later This Month"),
                h1("A New Tech Center for Long Beach"),
                p("Our new tech center opens at the end of September, giving founders and small business owners a dedicated space to build, meet, and grow alongside the rest of the Long Beach innovation community."),
                p(f'We\'re partnering with <a href="{LUM}" target="_blank" {LINK}>Lumen 21</a> on the installation and IT infrastructure behind the space.', 0),
            ]), edit="techcenter"),
            r_pad(34),
        ]),

        section([
            r_text("\n".join([
                kicker("Business Advising Services"),
                h1("No-Cost Business Advising"),
                p("We provide no-cost, one-on-one business advising for emerging technology companies and innovation-driven small businesses. Whether you're preparing for growth, exploring debt or equity financing, integrating AI into your operations, pursuing contract opportunities, or developing a long-term business strategy, our experienced advisors are here to help."),
                p(f'Complete our <a href="{FORM}" target="_blank" {LINK}>Intake Form</a> to get matched with the advisor best suited to your goals and start building your customized path to growth.', 0),
            ]), edit="advising"),
            r_button("Complete the Intake Form", FORM, TEAL),
            r_pad(36),
        ], tint=True),
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
    images=["lba-logo.png", "hero-ai-series.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        section([
            r_image("hero-ai-series.jpg", HERO_ALT),
            r_text("\n".join([
                kicker("Starts Tomorrow"),
                h1("Building an AI-Ready Trusted Business"),
                lead("Session 1 begins tomorrow, Tuesday, September 15, at 10:00 AM PT."),
                p("Ninety minutes on Zoom with Rene Redwood, built around your business rather than a slide deck. If you have been meaning to sign up, this is the moment.", 0),
            ]), edit="intro"),
            r_pad(32),
        ]),

        section([
            r_text("\n".join([
                kicker("Session 1"),
                h1("Purpose, People, and AI"),
                p("What makes your business valuable, distinct, and worthy of trust? You will connect your personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how your company operates and grows."),
                label("You will leave able to:"),
                bullets(S1_BULLETS),
            ]), edit="session1"),
            r_card(details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Via Zoom", indent=12)
                   .replace(f'style="margin-top:18px;border-top:1px solid {PANEL_EDGE};"', 'style=""')
                   .replace('padding:16px 0 0 0;', 'padding:0;'), on_tint=True),
            r_button("Register for Session&nbsp;1", S1),
            r_pad(34),
        ], tint=True),

        section([
            r_text(series_table(), edit="series"),
            r_text(bio("the facilitator", RENE), edit="rene", pad="24px 40px 0 40px"),
            r_pad(34),
        ]),

        section([
            r_text(f'      <p style="margin:0;{SMALL};color:{CHAR};"><strong style="color:{BLUE};">Also ahead:</strong> '
                   f'<a href="{TW}" target="_blank" {LINK}>Long Beach Tech Week</a> runs September 28 &ndash; October 1, and '
                   f'<a href="{PACK}" target="_blank" {LINK}>sponsorships are open</a>.</p>',
                   edit="ps"),
            r_pad(34),
        ], tint=True),
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
                kicker("September 28 &ndash; October 1, 2026 &nbsp;&middot;&nbsp; Long Beach, CA"),
                h1("Put Your Organization at the Center of Long Beach's Innovation Ecosystem"),
                lead("Long Beach Tech Week is ten days out, and sponsorships are open."),
                p(f'<a href="{TW}" target="_blank" {LINK}>Tech Week 2026</a> draws founders, investors, business leaders, tech experts, entrepreneurs, educators, creatives, and civic leaders for a multi-day experience showcasing the people, ideas, and industries shaping our region\'s future.'),
                p("Hosted by the Long Beach Accelerator, it offers organizations a unique opportunity to build visibility, strengthen relationships, and connect directly with Long Beach's growing innovation and entrepreneurial ecosystem."),
                label("Sponsorship opportunities are available at multiple levels, offering benefits such as:"),
                bullets(TW_BULLETS),
            ]), edit="techweek"),
            r_text(f'      Explore the <a href="{PACK}" target="_blank" {LINK}>Long Beach Tech Week 2026 Sponsorship Packet</a> and join us as a partner.',
                   edit="packet_line", pad="20px 40px 0 40px"),
            r_button("View the Sponsorship Packet", PACK),
            r_pad(34),
        ]),

        section([
            r_text("\n".join([
                kicker("3rd Annual Investors &amp; Founders Summit"),
                h1("Meet the 2026 Honorees"),
                p("The Summit closes out Tech Week on <strong>Thursday, October 1</strong> at the <strong>Hyatt Regency Long Beach</strong>. Sponsors sit in the room as we recognize four leaders shaping the region's innovation economy.", 0),
            ]), edit="honorees_intro"),
            r_honorees(),
            r_pad(34),
        ], tint=True),

        section([
            r_text("\n".join([
                kicker("Opening Later This Month"),
                h1("A New Tech Center for Long Beach"),
                p("Our new tech center opens at the end of September, giving founders and small business owners a dedicated space to build, meet, and grow alongside the rest of the Long Beach innovation community."),
                p(f'We\'re partnering with <a href="{LUM}" target="_blank" {LINK}>Lumen 21</a> on the installation and IT infrastructure behind the space.', 0),
            ]), edit="techcenter"),
            r_pad(34),
        ]),

        section([
            r_text("\n".join([
                kicker("Still Open"),
                h1("Building an AI-Ready Trusted Business"),
                p(f'Session 2, <strong>Good for Business: Investing in People and AI as Workforce Capacity</strong>, runs <strong>Wednesday, September 23, 11:00 AM &ndash; 1:00 PM PT</strong> on Zoom. Session 3 follows on October 8. Register at <a href="{EVT}" target="_blank" {LINK}>lbaccelerator.org/events</a>.', 0),
            ]), edit="aiseries"),
            r_pad(34),
        ], tint=True),
    ],
)


def build(slug, spec):
    out = os.path.join(HERE, f"{slug}-eblast", "email-package")
    imgs = os.path.join(out, "images")
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    os.makedirs(imgs, exist_ok=True)

    html = head(spec["title"], spec["preheader"]) + "".join(spec["sections"]) + FOOT
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

Sections alternate between white and Light Gray `{PANEL}` grounds. In an email this long,
alternating the ground is what separates one section from the next — hairline rules cannot
carry that weight on their own, and readers scroll past them.

Each section opens with a short teal rule over an uppercase kicker, so the eye can find where
one topic ends and the next begins without reading.

Body type is 16px on 27px leading. At the 520px measure that is roughly 68 characters a line,
near the top of the comfortable range, and the extra leading keeps it from packing.

Per the LBA Brand Guidelines (08/31/26): LBA Blue `{BLUE}` for headlines, subheads and primary
CTAs; LBA Teal `{TEAL}` for kickers, bullets, rules and secondary CTAs; Charcoal `{CHAR}` body;
Medium Gray `{GRAY}` captions. Proxima Nova leads the font stack with web-safe fallbacks —
Outlook and Gmail ignore webfonts, so most readers see Helvetica or Arial.

## Before you send

- [ ] Every link click-tested from a test send. None are verifiable from the drafting
      environment, whose network policy blocks all of these hosts.
- [ ] **Google Drive sponsorship packet opens while signed out** (incognito test). Drive links
      default to restricted.
- [ ] Test send to yourself and one colleague; open it on a phone.
- [ ] Confirm the schedule matches the send time above — the copy is dated.
"""


if __name__ == "__main__":
    for slug, spec in CAMPAIGNS.items():
        z, n, hrefs = build(slug, spec)
        print(f"{slug}: {os.path.relpath(z, HERE)}  ({n:,} chars, {len(hrefs)} links)")
