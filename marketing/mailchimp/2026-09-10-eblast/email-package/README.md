# LBA E-Blast — 9/10/26 — Mailchimp Package

Everything needed to build the campaign. Two ways to load it, described below.

```
email.html              paste-ready / zip-ready email
images/
  lba-logo.png          220px display  (440px asset, official lockup from the brand guidelines)
  hero-ai-series.jpg    600px display  (1200px asset)
  contracting-session2.jpg  600px display (530px asset — see Known issue)
  techweek-2026.jpg     600px display  (781px asset)
README.md               this file
```

---

## Option A — Import the zip as a template (recommended)

Mailchimp uploads the images for you and rewrites the paths.

1. **Content → Email templates → Create Template → Code your own → Import Zip**
2. Upload `lba-eblast-2026-09-10.zip`
3. **Campaigns → Create → Email → Template → Saved templates**, pick it

The content blocks are marked with `mc:edit`, so the intro, each section, both bios, and
the series table stay editable in Mailchimp's visual editor after import. Everything else
(structure, spacing, colors) is locked, which is what keeps the layout from drifting.

## Option B — Paste in code

1. **Campaigns → Create → Email → Code your own → Paste in code**
2. Paste all of `email.html`
3. Upload the four files in `images/` to **Content Studio**, then repoint each `src`
   to the Mailchimp URL. Relative paths like `images/hero-ai-series.jpg` will not resolve
   in a sent email — this step is required if you go this route.

Option A avoids step 3 entirely.

---

## Campaign settings

| Field | Value |
|---|---|
| Subject | Upcoming Opportunities & LB Tech Week 2026 |
| Preview text | Already in the HTML as a hidden preheader. Mailchimp will also offer its own field — either leave it blank or paste the same line. |
| Send | Thursday, September 10, 2026, 8:00 AM PT |
| From | Long Beach Accelerator / info@lbaccelerator.org |

Subject line alternates are in `../draft.md`.

**The 8:00 AM PT send time is load-bearing.** The contracting section says "join us today
at 4:00 PM." Any other send date makes that line wrong.

---

## Palette — per LBA Brand Guidelines (08/31/26)

| Brand token | Hex | Used here |
|---|---|---|
| LBA Blue | `#204396` | Headlines, subheads, footer background, primary CTAs |
| LBA Teal | `#008C8C` | Eyebrow labels, bullets, card borders, header rule, links, secondary CTAs |
| White | `#FFFFFF` | Content background, reverse type |
| Charcoal | `#333333` | Body copy |
| Light Gray | `#F2F4F5` | Card panels, page background |
| Medium Gray | `#6B7280` | Bios and captions |

Two hairline tints (`#E3E6E9` rules, `#DCE0E4` card dividers) and two footer type tints
(`#D7DEF0`, `#AEB9D8`) are derived from the neutrals; the guidelines don't specify values
for those roles.

**CTA hierarchy** follows the guidelines' three button styles. Event registrations — the two
primary asks — use Primary CTA (LBA Blue background, white text). The sponsorship packet and
advising intake use Secondary CTA (LBA Teal background, white text). The Outline CTA style
isn't used; a bordered button renders inconsistently across email clients.

**Typography.** The stack is `'Proxima Nova','Helvetica Neue',Helvetica,Arial,sans-serif`.
Proxima Nova is a licensed font with no free web-host, and Outlook and Gmail ignore webfonts
regardless, so most recipients will see Helvetica or Arial. Readers on machines with Proxima
Nova installed get the real face. This is the correct approach for email — there's no way to
guarantee a custom font in an inbox.

**One accessibility note.** LBA Teal on white measures 4.09:1, just under the 4.5:1 WCAG AA
threshold for normal-size text. It's fine on the buttons (large text) but the 12px uppercase
eyebrow labels sit below AA. It's your brand's own value so I've used it as specified —
switching those small labels to LBA Blue (9.11:1) would clear AA if you'd rather.

**Program artwork keeps its own colors.** The AI series banner is purple and Tech Week is navy
and gold; those are the approved flyers sitting inside brand-consistent chrome.

## What's in the code

- 600px fixed-width, table-based layout with inline CSS — renders in Outlook, Gmail, and Apple Mail
- Hidden preheader text so the inbox preview isn't scraped from the intro paragraph
- Alt text on all four images, written to carry the same information if images are blocked
- Bulletproof buttons (background on the `<td>`, padding on the `<a>`) so the whole
  button stays clickable when images are off; square corners in Outlook, rounded elsewhere
- Media queries stack padding and go full-width buttons under 620px
- `*|UNSUB|*`, `*|UPDATE_PROFILE|*`, and `*|LIST:ADDRESSLINE|*` merge tags in the footer.
  Mailchimp rejects a campaign without an unsubscribe tag, so leave these in.

Rendered and checked in Chromium at 700px and 390px. Full height is about 5,065px desktop
and 5,685px mobile.

---

## Known issue: contracting flyer resolution

`contracting-session2.jpg` is 530px wide but displays at 600px, so it upscales about 1.13x.
It reads fine on desktop and will look slightly soft on a high-density phone screen. It was
recovered from the e-blast PDF, which is the highest-resolution copy available here.

**If you have the original export** (Canva, Illustrator, wherever the flyer was made), drop a
1200px-wide version in as a straight replacement — same filename, no code change needed.
The other three images are all at or above their display size.

---

## Before you send

- [ ] **Google Drive sponsorship packet opens while signed out.** Drive links default to
      restricted. Test in a private window — if it's restricted, every recipient hits a
      permission wall on the main sponsorship CTA.
- [ ] All five links click-tested from a test send. None were verifiable from the drafting
      environment, whose network policy blocks all four hosts.
- [ ] AI Series Sessions 2 and 3: the series table currently points at
      `lbaccelerator.org/events`. Swap in direct registration links if per-session
      registration is required.
- [ ] Test send to yourself and one colleague; open on a phone.
- [ ] Confirm the send is scheduled for 8:00 AM PT on 9/10.

---

## Links used

| Placement | Destination |
|---|---|
| Register for Session 1 | `hub.catalyzerapp.com/public/events/purpose-people-and-ai-building-the-foundation-of-a-4705-133` |
| Sessions 2 and 3 | `lbaccelerator.org/events` |
| Register Now (contracting) | `hub.catalyzerapp.com/public/events/session-2-preparing-to-pursue-the-work-evaluate-op-4705-67` |
| View the Sponsorship Packet | `drive.google.com/file/d/1brJxClWdJ9efsuH7RnPNsjyxDq5224CC/view` |
| longbeachtechweek.com | `longbeachtechweek.com` |
| Complete the Intake Form | `hub.catalyzerapp.com/public/form/46c9cb88-0c9a-4eac-9346-f53f61f511d6` |

## Image sources

All graphics were extracted from the supplied source files — no stock or generated imagery.
The logo is the official LBA Accelerator lockup pulled from the brand guidelines PDF, flattened
onto white so it can't invert in a dark-mode client.
The hero is cropped from the series banner to the title-and-facilitator portion; the three
session cards were dropped from the image because they're unreadable at phone width and the
HTML table below covers the same information in selectable, screen-reader-friendly text.
