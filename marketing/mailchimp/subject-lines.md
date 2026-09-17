# Subject Lines & Preview Text — Sept 2026 Sends

Six sends, each with the subject currently baked into its template plus alternates for A/B
testing. Values here are pulled from `build.py`; change them there and update this file, so
the two can't drift.

**Two rules these follow.** Subject and preview text never repeat each other — the preview
carries what the subject had no room for. And subjects aim at or under ~45 characters, which
is roughly what an iPhone shows in portrait; anything longer gets cut mid-thought. The 9/10
roundup is the one send that breaks this, deliberately — see its note.

**One caution on the churn number.** Mailchimp's read on this account is 42.5% list churn
against a 13.3% peer median. That argues against curiosity-gap subjects that overpromise —
people unsubscribe when the email doesn't match what the subject implied. Every recommendation
below says plainly what's inside.

---

## Thu 9/10 — the roundup

**Current**

> **Subject:** Long Beach Tech Week, the 2026 LBA honorees, and today at 4 PM `62`
> **Preview:** Tech Week runs Sept 28 – Oct 1, sponsorship opportunities are open, and contracting readiness is this afternoon.

The hardest of the four to write, because seven sections have no single hook. At 62 characters
this will truncate on a phone; it is written so the first clause — *Long Beach Tech Week* —
still carries the email on its own when the rest is cut. If you would rather it fit whole, the
first alternate below is the closest short version.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Meet the 2026 LBA honorees | 26 | Curiosity — fits whole |
| Sponsorship opportunities are open for Long Beach Tech Week | 59 | Single ask |
| Put your organization at the center of our innovation ecosystem | 63 | Benefit — flyer headline |

The honorees subject will likely win on opens and lose on clicks — the honorees sit third in
the email, so anyone opening for them scrolls past two other asks first.

---

## Mon 9/14 — Session 1 last call

**Current**

> **Subject:** Tomorrow at 10 AM: Purpose, People, and AI `42`
> **Preview:** Ninety minutes on Zoom with René Redwood. Session 1 of three, and there's still room.

One deadline, one action, and the subject states both the timing and the substance. The
preview adds the facilitator, the format, and a soft availability cue.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Last call — Session 1 is tomorrow morning | 41 | Urgency |
| 90 minutes tomorrow to sharpen your business | 44 | Benefit |
| Starts tomorrow: Building an AI-Ready Business | 46 | Specific — may truncate |

---

## Mon 9/14 — Session 1, the René edition

**Current**

> **Subject:** Tomorrow at 10 AM with René Redwood `35`
> **Preview:** Session 1 of Building an AI-Ready Trusted Business starts tomorrow morning on Zoom, and there is still room.

An alternative to the last-call send above, for the same Monday slot. That one leads on the
deadline; this one leads on the person — *who* you get for ninety minutes rather than *when*.
Her name is the whole hook, which is why it sits in the subject while the preview carries the
session title.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| René Redwood is on Zoom tomorrow at 10 AM | 41 | Immediacy |
| Ninety minutes tomorrow with René Redwood | 41 | Benefit |
| Tomorrow: Purpose, People, and AI | 33 | Substance, no name |

If you A/B one thing this month, make it these two sends against each other: same offer, same
list, same morning, with the only variable being deadline framing versus facilitator framing.
What you learn transfers directly to Sessions 2 and 3.

---

## Thu 9/17 — aerospace invite (select list)

Both 9/17 sends go out the same evening. This one is scoped to a hand-picked list and
the Tech Week send below goes to everyone, so the only people who get two emails are the
leaders on both.

**Current**

> **Subject:** Invitation: Winning the Aerospace Talent War `44`
> **Preview:** Wednesday, September 23 at 5:30 PM at The Modern in Long Beach. Bestselling author Devin Hughes headlines.

Not an LBA event — Bryson hosts it, and the first line of the email says so. Written for a
hand-picked list of regional leaders rather than the full audience, so the subject can open
with the word *Invitation* without overpromising. Keep it off the main list: a partner event
is exactly the kind of unrelated ask that drives unsubscribes on a list already churning at
42.5%.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Wed, Sept 23: Winning the Aerospace Talent War | 46 | Date-led — may truncate |
| Devin Hughes on aerospace talent, Sept 23 | 41 | Speaker-led |
| An invitation we're passing along | 33 | Personal, vague on purpose |

---

## Thu 9/17 — Tech Week signups

**Current**

> **Subject:** Register today for Long Beach Tech Week `39`
> **Preview:** Four days with the founders, investors, and leaders building the region's tech economy. Register today.

Vivian's pass set the voice here: *Register today* in the subject, the preview and the opening
line, and one button label, "Register for Long Beach Tech Week", everywhere Tech Week is the
ask. It carries no countdown anywhere, deliberately: this send was drafted for a Monday and moved to a Thursday, and a
subject line that counts days is the kind of thing that ships wrong after a re-date. Every
date in it is absolute. The preview names who else will be there, which is the real reason
anyone clears four days.

Sponsorship still appears, but last and short. Two asks in one email split the click.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Long Beach Tech Week opens Sept 28th | 36 | Date-led |
| Four days, Sept 28th to Oct 1st, in Long Beach | 46 | Logistics — may truncate |
| Your seat at Long Beach Tech Week | 33 | Possessive |

---

## Fri 9/18 — Tech Week sponsorship

**Current**

> **Subject:** Long Beach Tech Week: sponsorships are open `43`
> **Preview:** Sept 28 – Oct 1. Sponsors join founders, investors, and civic leaders — and sit in the room for the Summit.

Different audience from the other three: organizations deciding on spend, not owners deciding
on a morning. The countdown creates the deadline, and the preview names who else is in the
room, which is the actual argument for sponsoring.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Put your brand at Long Beach Tech Week | 38 | Benefit |
| Sponsor Long Beach Tech Week 2026 | 33 | Plain label |
| Meet the 2026 Summit honorees | 29 | Curiosity |

*Sponsor Long Beach Tech Week 2026* is a label rather than a reason. It works if this list
already knows Tech Week well; the countdown version works better if they don't.

---

## Applying these in Mailchimp

Each template already carries its preview text as a hidden preheader in the HTML. Mailchimp
also offers its own preview text field, and **when both are set, some clients show them
back to back.** Pick one:

- **Leave Mailchimp's field blank** — the HTML preheader is used. Simplest, and it's already
  written.
- **Set Mailchimp's field** — it takes precedence. Use this if you pick a preview line
  different from the one baked into the template.

If you choose different preview text than what's in a template, say which and I'll update the
HTML so the two can't drift apart.

Preview text currently baked into each template:

| Send | Preheader in the HTML |
|---|---|
| 9/10 | Tech Week runs Sept 28 – Oct 1, sponsorship opportunities are open, and contracting readiness is this afternoon. |
| 9/14 | Ninety minutes on Zoom with René Redwood. Session 1 of three, and there's still room. |
| 9/14 (René) | Session 1 of Building an AI-Ready Trusted Business starts tomorrow morning on Zoom, and there is still room. |
| 9/17 (aerospace) | Wednesday, September 23 at 5:30 PM at The Modern in Long Beach. Bestselling author Devin Hughes headlines. |
| 9/17 (Tech Week) | Four days with the founders, investors, and leaders building the region's tech economy. Register today. |
| 9/18 | Sept 28th – Oct 1st. Sponsors join founders, investors, and civic leaders — and sit in the room for the Summit. |
