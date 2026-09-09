#!/usr/bin/env python3
"""Build LBA Mailchimp e-blasts from shared brand chrome.

Each campaign is defined in CAMPAIGNS below as a preheader plus a list of body
sections. The header, footer, palette and responsive rules live here once, so
every send renders identically and a brand change is a one-line edit.

Run:  python3 build.py          # writes each campaign folder + zip
"""
import os, re, shutil, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "_assets")

# --- LBA Brand Guidelines, 08/31/26 -----------------------------------------
BLUE, TEAL = "#204396", "#008C8C"
CHAR, GRAY = "#333333", "#6B7280"
PANEL, PAGE = "#F2F4F5", "#F2F4F5"
RULE, PANEL_EDGE = "#E3E6E9", "#DCE0E4"
FOOT_A, FOOT_B = "#D7DEF0", "#AEB9D8"
FONT = "'Proxima Nova','Helvetica Neue',Helvetica,Arial,sans-serif"

LINK = f'style="color:{BLUE};text-decoration:underline;"'


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
  body{{margin:0!important;padding:0!important;width:100%!important;background-color:{PAGE};}}
  a{{color:{TEAL};}}
  .lba-h1{{font-size:26px!important;line-height:32px!important;}}
  @media screen and (max-width:620px){{
    .wrap{{width:100%!important;}}
    .px{{padding-left:20px!important;padding-right:20px!important;}}
    .lba-h1{{font-size:22px!important;line-height:28px!important;}}
    .lba-h2{{font-size:19px!important;line-height:25px!important;}}
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
<body style="margin:0;padding:0;background-color:{PAGE};">

<!-- Preview text: shows in the inbox beside the subject line. -->
<div style="display:none;font-size:1px;color:{PAGE};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">
  {preheader}
  {'&#847;&zwnj;&nbsp;' * 20}
</div>

<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:{PAGE};">
<tr><td align="center" style="padding:24px 10px;">

<table role="presentation" class="wrap" border="0" cellpadding="0" cellspacing="0" width="600" style="width:600px;max-width:600px;background-color:#FFFFFF;">

  <tr>
    <td align="center" class="px" style="padding:26px 32px 20px 32px;background-color:#FFFFFF;">
      <img src="images/lba-logo.png" width="220" alt="LBA Accelerator" style="width:220px;max-width:220px;height:auto;display:block;" />
    </td>
  </tr>
  <tr><td style="font-size:0;line-height:0;height:4px;background-color:{TEAL};">&nbsp;</td></tr>
"""


FOOT = f"""  <tr><td class="px" style="padding:34px 40px 0 40px;"><table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0"><tr><td style="border-top:2px solid {BLUE};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>

  <tr>
    <td class="px fcenter" style="padding:22px 40px 0 40px;">
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
    <td class="px" style="padding:24px 40px 36px 40px;">
      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
        <tr>
          <td class="fstack" width="230" valign="top" style="padding:6px 0 0 0;">
            <img src="images/lba-logo.png" width="200" alt="LBA Accelerator" style="width:200px;max-width:200px;height:auto;display:block;" />
          </td>
          <td class="fstack" align="right" valign="top" mc:edit="footer_legal" style="font-family:{FONT};font-size:13px;line-height:21px;color:{GRAY};text-align:right;">
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
</td></tr>
</table>
</body>
</html>
"""


# --- section helpers ---------------------------------------------------------

def image(src, alt):
    return f"""  <tr>
    <td align="center" style="padding:26px 0 0 0;">
      <img src="images/{src}" width="600" alt="{alt}" style="width:100%;max-width:600px;height:auto;display:block;" />
    </td>
  </tr>
"""

def text(body, edit=None, pad="26px 40px 0 40px"):
    e = f' mc:edit="{edit}"' if edit else ""
    return f"""  <tr>
    <td class="px"{e} style="padding:{pad};font-family:{FONT};font-size:16px;line-height:26px;color:{CHAR};">
{body}
    </td>
  </tr>
"""

def eyebrow(t):
    return f'      <p style="margin:0 0 6px 0;font-size:12px;line-height:16px;letter-spacing:1.5px;text-transform:uppercase;color:{TEAL};font-weight:bold;">{t}</p>'

def h1(t):
    return f'      <h1 class="lba-h1" style="margin:0 0 14px 0;font-family:{FONT};font-size:26px;line-height:32px;color:{BLUE};font-weight:bold;">{t}</h1>'

def para(t, mb=14):
    return f'      <p style="margin:0 0 {mb}px 0;">{t}</p>'

def bullets(items, color=None):
    c = color or TEAL
    rows = ""
    for i, it in enumerate(items):
        pad = "0" if i == len(items) - 1 else "0 0 6px 0"
        rows += (f'        <tr><td width="16" valign="top" style="padding:{pad};color:{c};font-size:15px;line-height:24px;">&bull;</td>'
                 f'<td style="padding:{pad};font-size:15px;line-height:24px;color:{CHAR};">{it}</td></tr>\n')
    return f'      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">\n{rows}      </table>'

def button(label, href, color=None):
    c = color or BLUE
    return f"""  <tr>
    <td align="center" class="px btn" style="padding:22px 40px 0 40px;">
      <table role="presentation" border="0" cellpadding="0" cellspacing="0">
        <tr><td align="center" bgcolor="{c}" style="border-radius:4px;">
          <a href="{href}" target="_blank" style="display:inline-block;padding:15px 34px;font-family:{FONT};font-size:16px;line-height:20px;font-weight:bold;color:#FFFFFF;text-decoration:none;border-radius:4px;">{label}</a>
        </td></tr>
      </table>
    </td>
  </tr>
"""

def panel(inner, edit=None):
    e = f' mc:edit="{edit}"' if edit else ""
    return f"""  <tr>
    <td class="px" style="padding:22px 40px 0 40px;">
      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{PANEL};border-left:4px solid {TEAL};">
        <tr><td{e} style="padding:22px 24px;font-family:{FONT};font-size:15px;line-height:24px;color:{CHAR};">
{inner}
        </td></tr>
      </table>
    </td>
  </tr>
"""

def details(date_, time_, loc):
    return (f'          <p style="margin:0;font-size:15px;line-height:24px;color:{CHAR};">'
            f'<strong style="color:{BLUE};">Date:</strong> {date_}<br />'
            f'<strong style="color:{BLUE};">Time:</strong> {time_}<br />'
            f'<strong style="color:{BLUE};">Location:</strong> {loc}</p>')

def rule(pad="28px 40px 0 40px"):
    return (f'  <tr><td class="px" style="padding:{pad};"><table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">'
            f'<tr><td style="border-top:1px solid {RULE};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>\n')

def series_table():
    rows = [("1", "Purpose, People, and AI: Building the Foundation of a Trusted Business", "Tue, Sept 15, 2026", "10:00 &ndash; 11:30 AM PT"),
            ("2", "Good for Business: Investing in People and AI as Workforce Capacity", "Wed, Sept 23, 2026", "11:00 AM &ndash; 1:00 PM PT"),
            ("3", "Authority Positioning and Strategic Visibility to Yield Market Trust", "Thu, Oct 8, 2026", "12:00 &ndash; 2:00 PM PT")]
    out = ""
    for i, (n, t, d, tm) in enumerate(rows):
        border = "" if i == len(rows) - 1 else f"border-bottom:1px solid {RULE};"
        out += (f'        <tr><td width="34" valign="top" style="padding:14px 0 14px 14px;font-size:14px;line-height:21px;color:{TEAL};font-weight:bold;">{n}</td>'
                f'<td style="padding:14px 14px 14px 4px;font-size:14px;line-height:21px;color:{CHAR};{border}">'
                f'<strong style="color:{BLUE};">{t}</strong><br />{d} &nbsp;&middot;&nbsp; {tm}</td></tr>\n')
    return (f'      <p style="margin:0 0 12px 0;font-size:15px;line-height:22px;color:{BLUE};font-weight:bold;">The full series</p>\n'
            f'      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="border:1px solid {RULE};">\n{out}      </table>\n'
            f'      <p style="margin:10px 0 0 0;font-size:14px;line-height:21px;color:{GRAY};">All sessions via Zoom. '
            f'Register for Sessions 2 and 3 at <a href="https://lbaccelerator.org/events" target="_blank" style="color:{BLUE};">lbaccelerator.org/events</a>.</p>')

HONOREES = [("honoree-hacegaba.jpg", "2026 LBA Visionary of the Year", "Dr. Noel Hacegaba", "Chief Executive Officer<br />Port of Long Beach"),
            ("honoree-marshall.jpg", "2026 LBA Trailblazer of the Year", "Carrie Marshall", "Chief Executive Officer<br />Rebel Space"),
            ("honoree-lee.jpg", "2026 LBA Investor of the Year", "Joshua Lee", "Managing Partner<br />Gumshoe Ventures"),
            ("honoree-glass.jpg", "2026 LBA Founder of the Year", "Ethan Glass", "Chief Executive Officer<br />OCRA")]

def honoree_grid():
    def cell(img, award, name, role):
        alt = f"{name}, {re.sub('<br />', ', ', role)}, {award}"
        return (f'            <td class="hcell" width="250" valign="top" style="width:250px;">\n'
                f'              <img src="images/{img}" width="250" alt="{alt}" style="width:100%;max-width:250px;height:auto;display:block;" />\n'
                f'              <p style="margin:12px 0 4px 0;font-family:{FONT};font-size:11px;line-height:15px;letter-spacing:1.2px;text-transform:uppercase;color:{TEAL};font-weight:bold;">{award}</p>\n'
                f'              <p style="margin:0 0 2px 0;font-family:{FONT};font-size:17px;line-height:23px;color:{BLUE};font-weight:bold;">{name}</p>\n'
                f'              <p style="margin:0;font-family:{FONT};font-size:14px;line-height:21px;color:{GRAY};">{role}</p>\n'
                f'            </td>')
    gut = f'            <td class="gut" width="20" style="width:20px;font-size:0;line-height:0;">&nbsp;</td>'
    a, b, c, d = [cell(*h) for h in HONOREES]
    spacer = '        <tr><td colspan="3" height="26" style="height:26px;font-size:0;line-height:0;">&nbsp;</td></tr>'
    return f"""  <tr>
    <td class="px" style="padding:14px 40px 0 40px;">
      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
        <tr>
{a}
{gut}
{b}
        </tr>
{spacer}
        <tr>
{c}
{gut}
{d}
        </tr>
      </table>
    </td>
  </tr>
"""


# --- links -------------------------------------------------------------------
S1   = "https://hub.catalyzerapp.com/public/events/purpose-people-and-ai-building-the-foundation-of-a-4705-133"
PACK = "https://drive.google.com/file/d/1brJxClWdJ9efsuH7RnPNsjyxDq5224CC/view"
TW   = "https://longbeachtechweek.com"
FORM = "https://hub.catalyzerapp.com/public/form/46c9cb88-0c9a-4eac-9346-f53f61f511d6"
EVT  = "https://lbaccelerator.org/events"
LUM  = "https://www.lumen21.com/"


# --- campaigns ---------------------------------------------------------------
CAMPAIGNS = {}

# ============================ MONDAY, SEPT 14 ================================
CAMPAIGNS["2026-09-14"] = dict(
    title="Session 1 starts tomorrow",
    subject="Tomorrow at 10 AM: Purpose, People, and AI",
    alts=["Starts tomorrow: Building an AI-Ready Trusted Business",
          "Last call — Session 1 is tomorrow morning",
          "One seat, one morning: start building a trusted business"],
    preheader="Session 1 of Building an AI-Ready Trusted Business starts tomorrow, Tuesday, at 10:00 AM PT.",
    send="Monday, September 14, 2026, 8:00 AM PT",
    images=["lba-logo.png", "hero-ai-series.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        image("hero-ai-series.jpg",
              "Building an AI-Ready Trusted Business: a three-part learning journey for small business owners, facilitated by Rene Redwood. Hosted by the Long Beach Accelerator."),
        text("\n".join([
            eyebrow("Starts Tomorrow"),
            h1("Building an AI-Ready Trusted Business"),
            para("Session 1 of Rene Redwood's three-part series begins <strong>tomorrow, Tuesday, September 15, at 10:00 AM PT</strong>. If you have been meaning to sign up, this is the moment."),
            para("Ninety minutes, on Zoom, built around your business rather than a slide deck.", 0),
        ]), edit="intro"),
        panel("\n".join([
            f'          <p style="margin:0 0 4px 0;font-size:12px;line-height:16px;letter-spacing:1.5px;text-transform:uppercase;color:{TEAL};font-weight:bold;">Session 1</p>',
            f'          <h2 class="lba-h2" style="margin:0 0 12px 0;font-size:20px;line-height:27px;color:{BLUE};font-weight:bold;">Purpose, People, and AI: Building the Foundation of a Trusted Business</h2>',
            '          <p style="margin:0 0 14px 0;">What makes your business valuable, distinct, and worthy of trust? You will connect your personal values and business mission to the leadership choices, people, systems, and responsible use of AI that shape how your company operates and grows.</p>',
            f'          <p style="margin:0 0 8px 0;font-weight:bold;color:{BLUE};">You will leave able to:</p>',
            bullets(["Clarify your business purpose and the value you create",
                     "Connect your values, mission, and leadership to daily decisions",
                     "Align your people, systems, and AI tools with your goals",
                     "Communicate your value clearly to build trust and confidence",
                     "Lay the foundation for a business that can grow beyond you"]).replace("      ", "          "),
            f'          <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top:16px;border-top:1px solid {PANEL_EDGE};"><tr><td style="padding:14px 0 0 0;">',
            details("Tuesday, September 15, 2026", "10:00 &ndash; 11:30 AM PT", "Via Zoom"),
            '          </td></tr></table>',
        ]), edit="session1"),
        button("Register for Session&nbsp;1", S1),
        text(series_table(), edit="series", pad="26px 40px 0 40px"),
        text(f'      <p style="margin:0;font-size:14px;line-height:22px;color:{GRAY};"><strong style="color:{BLUE};">About the facilitator.</strong> '
             'Rene Redwood is a recognized leader in advancing equity, inclusive workplace culture, and strategic initiatives that drive results. '
             'She has directed the Presidential Glass Ceiling Commission and served on the court-appointed Coca-Cola Task Force. Rene brings decades of '
             'experience helping organizations build trust, leverage human potential, and create a lasting advantage in the marketplace.</p>',
             edit="rene", pad="20px 40px 0 40px"),
        rule(),
        text(f'      <p style="margin:0;font-size:15px;line-height:24px;color:{GRAY};"><strong style="color:{BLUE};">Also ahead:</strong> '
             f'<a href="{TW}" target="_blank" {LINK}>Long Beach Tech Week</a> runs September 28 &ndash; October 1, and '
             f'<a href="{PACK}" target="_blank" {LINK}>sponsorships are open</a>.</p>',
             edit="ps", pad="24px 40px 0 40px"),
    ],
)

# ============================ FRIDAY, SEPT 18 ================================
CAMPAIGNS["2026-09-18"] = dict(
    title="Sponsor Long Beach Tech Week 2026",
    subject="Sponsor Long Beach Tech Week 2026",
    alts=["Ten days out: put your organization at the center of LB Tech Week",
          "Long Beach Tech Week 2026 — sponsorships are open",
          "Meet the 2026 Investors & Founders Summit honorees"],
    preheader="September 28 - October 1. Sponsorships are open, and the Summit honorees are set.",
    send="Friday, September 18, 2026, 8:00 AM PT",
    images=["lba-logo.png", "techweek-2026.jpg", "honoree-hacegaba.jpg", "honoree-marshall.jpg",
            "honoree-lee.jpg", "honoree-glass.jpg", "icon-linkedin.png", "icon-email.png", "icon-web.png"],
    sections=[
        image("techweek-2026.jpg",
              "Long Beach Tech Week 2026 Sponsorship Packet, hosted by the Long Beach Accelerator, September 28 to October 1, 2026."),
        text("\n".join([
            eyebrow("September 28 &ndash; October 1, 2026 &nbsp;&middot;&nbsp; Long Beach, CA"),
            h1("Put Your Organization at the Center of Long Beach's Innovation Ecosystem"),
            para(f'<a href="{TW}" target="_blank" {LINK}>Long Beach Tech Week 2026</a> is ten days out. It draws founders, investors, business leaders, tech experts, entrepreneurs, educators, creatives, and civic leaders for a multi-day experience showcasing the people, ideas, and industries shaping our region\'s future.'),
            para("Hosted by the Long Beach Accelerator, Tech Week offers organizations a unique opportunity to build visibility, strengthen relationships, and connect directly with Long Beach's growing innovation and entrepreneurial ecosystem."),
            f'      <p style="margin:0 0 8px 0;font-weight:bold;color:{BLUE};">Sponsorship opportunities are available at multiple levels, offering benefits such as:</p>',
            bullets(["Brand visibility throughout Long Beach Tech Week",
                     "Recognition and engagement with founders, investors, and regional leaders",
                     "Opportunities to participate in select programs, forums, and the 2026 Investors &amp; Founders Summit"]),
        ]), edit="techweek"),
        text(f'      Explore the <a href="{PACK}" target="_blank" {LINK}>Long Beach Tech Week 2026 Sponsorship Packet</a> and join us as a partner.',
             edit="packet_line", pad="16px 40px 0 40px"),
        button("View the Sponsorship Packet", PACK),
        rule(),
        text("\n".join([
            eyebrow("3rd Annual Investors &amp; Founders Summit"),
            h1("Meet the 2026 Honorees"),
            para("The Summit closes out Tech Week on <strong>Thursday, October 1</strong> at the <strong>Hyatt Regency Long Beach</strong>. Sponsors sit in the room as we recognize four leaders shaping the region's innovation economy.", 0),
        ]), edit="honorees_intro"),
        honoree_grid(),
        rule(),
        text("\n".join([
            eyebrow("Opening Later This Month"),
            h1("A New Tech Center for Long Beach"),
            para("Our new tech center opens at the end of September, giving founders and small business owners a dedicated space to build, meet, and grow alongside the rest of the Long Beach innovation community."),
            para(f'We\'re partnering with <a href="{LUM}" target="_blank" {LINK}>Lumen 21</a> on the installation and IT infrastructure behind the space.', 0),
        ]), edit="techcenter"),
        rule(),
        text("\n".join([
            eyebrow("Still Open"),
            h1("Building an AI-Ready Trusted Business"),
            para(f'Session 2, <strong>Good for Business: Investing in People and AI as Workforce Capacity</strong>, runs <strong>Wednesday, September 23, 11:00 AM &ndash; 1:00 PM PT</strong> on Zoom. Session 3 follows on October 8. Register at <a href="{EVT}" target="_blank" {LINK}>lbaccelerator.org/events</a>.', 0),
        ]), edit="aiseries"),
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

    readme = readme_for(slug, spec)
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    zpath = os.path.join(HERE, f"{slug}-eblast", f"lba-eblast-{slug}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(out, "email.html"), "email.html")
        z.write(os.path.join(out, "README.md"), "README.md")
        for name in spec["images"]:
            z.write(os.path.join(imgs, name), f"images/{name}")

    # every href in the file, for the README link table and a broken-link check
    hrefs = re.findall(r'href="([^"]+)"', html)
    return zpath, len(html), hrefs


def readme_for(slug, spec):
    alts = "\n".join(f"- {a}" for a in spec["alts"])
    return f"""# LBA E-Blast — {slug} — Mailchimp Package

Generated by `marketing/mailchimp/build.py`. Edit the campaign spec there and re-run
rather than hand-editing `email.html`, so the chrome stays in sync across sends.

## Campaign settings

| Field | Value |
|---|---|
| Subject | {spec['subject']} |
| Preview text | Already in the HTML as a hidden preheader. |
| Send | {spec['send']} |
| From | Long Beach Accelerator / info@lbaccelerator.org |

Subject line alternates:

{alts}

## Load it into Mailchimp

**Content → Email templates → Create Template → Code your own → Import Zip**, upload
`lba-eblast-{slug}.zip`, then start a campaign from the saved template. Mailchimp uploads the
images and rewrites the paths. Content blocks are marked `mc:edit`, so copy stays editable in
the visual editor while the layout stays put.

## Brand

Per the LBA Brand Guidelines (08/31/26): LBA Blue `{BLUE}` for headlines, subheads and primary
CTAs; LBA Teal `{TEAL}` for eyebrows, bullets, rules and links; Charcoal `{CHAR}` body; Medium
Gray `{GRAY}` captions; Light Gray `{PANEL}` panels. Proxima Nova leads the font stack with
web-safe fallbacks — Outlook and Gmail ignore webfonts, so most readers see Helvetica or Arial.

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
