# Build Notes — 9/10/26 E-Blast

Companion to `draft.md`. Everything a builder needs to assemble the campaign in Mailchimp,
plus the open items that must be resolved before scheduling.

---

## 1. Link inventory

| Placement | Destination | Status |
|---|---|---|
| AI Series, Session 1 button | `hub.catalyzerapp.com/public/events/purpose-people-and-ai-building-the-foundation-of-a-4705-133` | Supplied |
| AI Series, Sessions 2 and 3 | `lbaccelerator.org/events` (catch-all) | **Open — see below** |
| Contracting, Session 2 button | `hub.catalyzerapp.com/public/events/session-2-preparing-to-pursue-the-work-evaluate-op-4705-67` | Supplied, confirmed |
| Tech Week, packet button | `drive.google.com/file/d/1brJxClWdJ9efsuH7RnPNsjyxDq5224CC/view` | Supplied — **check sharing** |
| Tech Week, inline text link | `longbeachtechweek.com` | Supplied |
| Advising, intake form button | `hub.catalyzerapp.com/public/form/46c9cb88-0c9a-4eac-9346-f53f61f511d6` | Supplied |

### Still open

- **AI Series Sessions 2 and 3 registration.** No direct URLs yet. The table currently points readers
  to `lbaccelerator.org/events` as a catch-all. Replace with direct links if per-session registration
  is required, or say plainly that Session 1 registration enrolls participants in all three.
- **Implementation Lab, Tue 9/15.** Still being worked out, so the block has been removed from the
  draft. If it firms up before send, add it to Section 2 as the natural next step after Session 2.
  Note the date collides with AI Series Session 1 (10:00–11:30 AM PT), so pick a non-conflicting time.

### Two link cautions

1. **The Google Drive packet must be shared publicly.** Drive links default to restricted access.
   If the sharing setting isn't "Anyone with the link," every recipient hits a permission wall.
   Open the link in a private/incognito window while signed out and confirm the packet loads.
2. **Links could not be verified from the drafting environment.** Its network policy blocks
   `drive.google.com`, `longbeachtechweek.com`, `hub.catalyzerapp.com`, and `lbaccelerator.org`
   outright, so every URL above is unverified and needs a human click-test in Mailchimp preview.

## 2. Decisions worth making (not blocking)

- **Session length mismatch.** Rene's overview document describes each session as 75 minutes of facilitation plus a 45-minute application block. The published flyers show 90 minutes (Session 1) and 120 minutes (Sessions 2 and 3). The draft uses the flyer times, which are what the public has already seen. Flag to Rene only if the internal agenda needs to change.
- **Session 1 label.** The original draft's details block read "Session 1: Building an AI-Ready Trusted Business," which is the *series* name, not the session name. Corrected to the real title, "Purpose, People, and AI: Building the Foundation of a Trusted Business."
- **Contracting Session 1 is past.** Session 1 of the contracting series ran Aug 26. The draft correctly doesn't market it, but if any of Session 1's materials are available on demand, a one-line "missed Session 1?" link would catch late arrivals.
- **Rene's bio.** The original draft gave Ronda Jackson a full bio and Rene Redwood only a name. The revision adds a matched short bio for parity. Trim the Glass Ceiling Commission / Coca-Cola Task Force credentials if the section runs long.

## 3. Image alt text

Mailchimp requires alt text on every image block. Use these verbatim.

| Image | Alt text |
|---|---|
| Series banner (3-session overview) | `Building an AI-Ready Trusted Business: a three-part learning series for small business owners, facilitated by Rene Redwood. Sessions on September 15, September 23, and October 8, 2026, via Zoom.` |
| Session 1 flyer | `Session 1: Purpose, People, and AI — Building the Foundation of a Trusted Business. Tuesday, September 15, 2026, 10:00 to 11:30 AM PT via Zoom, facilitated by Rene Redwood.` |
| Contracting Session 2 flyer | `Contracting and Procurement Readiness Series, Session 2: Preparing to Pursue the Work. Thursday, September 10, 4:00 to 5:30 PM PT, online via Zoom, featuring LBA Business Adviser Ronda Jackson.` |
| Tech Week banner | `Long Beach Tech Week 2026 Sponsorship Packet, hosted by the Long Beach Accelerator, September 28 to October 1, 2026.` |

If you use the Session 2 and Session 3 flyers for the AI series, mirror the Session 1 pattern:
title, date, time, format, facilitator.

## 4. Button copy

Keep buttons to two or three words and make every one link somewhere.

| Section | Button |
|---|---|
| AI series | `Register for Session 1` |
| Contracting | `Register Now` |
| Tech Week | `View the Sponsorship Packet` |
| Advising | `Complete the Intake Form` |

## 5. Copy edits made to the original draft

- Added **preview text** — the field was missing entirely, so inboxes would have pulled the first line of the intro.
- Fixed the **stacked modifiers** in the AI series opener ("a new three-part learning series starting on Tuesday... facilitated by Rene Redwood designed to help...") by splitting the date into its own sentence.
- Fixed the **Ronda Jackson sentence fragment** ("Facilitating the session, Ronda Jackson, a business adviser...") into two complete sentences.
- Corrected the **Session 1 label** (see §2).
- Added a **full-series date table** so readers see the three-session commitment up front rather than only Session 1.
- Added **"in this session, you will"** bullets to both event sections, pulled from the approved flyers.
- Added the **year** to the contracting session date line and **PT** to the time.
- Punctuated **"Prepare. Pursue. Perform."**
- Added a comma after **"to Long Beach Tech Week"** in the intro.
- Rebuilt the **Tech Week bullet list**, which had collapsed in the source document (the first bullet's text had separated from its marker).
- Added a short **Rene Redwood bio** for parity with Ronda's.

## 6. Pre-send QA checklist

- [ ] AI Series Sessions 2 and 3 registration resolved (§1, Still open)
- [ ] **Google Drive sponsorship packet opens while signed out** (incognito test)
- [ ] Every button click-tested in Mailchimp preview — none were verifiable from the drafting environment
- [ ] Alt text applied to all images
- [ ] Send time confirmed as **8:00 AM PT** — the "join us today at 4:00 PM" line only works on a morning send on 9/10
- [ ] Mobile preview checked; the series date table is the most likely block to break
- [ ] Test send to yourself and one colleague
- [ ] Verify Session 1 registration link resolves (it's a long URL and was line-wrapped in the source document)

## 7. Source materials

Everything in the draft traces back to these, all supplied by the requester:

- `9.10.26_EBlast_LBA.pdf` — the original draft
- `Series_Details__AIReady_Trusted_Biz_.docx` — session titles, dates, times, descriptions, CTAs
- `Overview_AI_Ready_Trsted_Business.docx` — full agendas and key takeaways
- `AIReady_Trsted_Biz_Marketing_Frames.docx` — approved marketing language
- `Contract__Procurement_Series.docx` — contracting series detail, Ronda Jackson bio, Implementation Lab dates
- `2026_Rene_Redwood_Bio_1.pdf` — Rene Redwood bio
- Event flyers for both series and the Tech Week sponsorship banner

**Dates verified.** Every date/day-of-week pair in the draft was checked against the 2026 calendar
(9/10 Thu, 9/15 Tue, 9/23 Wed, 10/8 Thu, 9/28–10/1 Mon–Thu, 8/26 Wed, 9/2 Wed). All correct.
