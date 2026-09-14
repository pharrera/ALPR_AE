# Subject Lines & Preview Text — Sept 2026 Sends

Four sends, each with the subject currently baked into its template plus alternates for A/B
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

## Tue 9/15 — day-of, René Redwood

**Current**

> **Subject:** Today at 10 AM with René Redwood `32`
> **Preview:** Session 1 of Building an AI-Ready Trusted Business starts this morning on Zoom, and there is still room.

This send follows 9/14 by a day, so the subject cannot repeat it. It changes the angle from
the deadline to the person: *who* you get for ninety minutes, not *when*. Her name is the
whole hook, which is why it sits in the subject and the preview carries the session title.

Send it early — 7:30 AM PT in the template — so it lands well before the 10:00 start.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| René Redwood is on Zoom at 10 AM | 32 | Immediacy |
| Starting this morning: Session 1 with René | 42 | Urgency |
| Today: Purpose, People, and AI | 30 | Substance, no name |

If you A/B one send this month, make it this one against 9/14: same offer, same list, one day
apart, with the only variable being deadline framing versus facilitator framing. What you
learn transfers directly to Sessions 2 and 3.

---

## Fri 9/18 — Tech Week sponsorship

**Current**

> **Subject:** Ten days to Tech Week — sponsorships are open `45`
> **Preview:** Sept 28 – Oct 1. Sponsors join founders, investors, and civic leaders — and sit in the room for the Summit.

Different audience from the other three: organizations deciding on spend, not owners deciding
on a morning. The countdown creates the deadline, and the preview names who else is in the
room, which is the actual argument for sponsoring.

**Alternates**

| Subject | Len | Angle |
|---|---|---|
| Put your brand at the center of LB Tech Week | 44 | Benefit |
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
| 9/15 | Session 1 of Building an AI-Ready Trusted Business starts this morning on Zoom, and there is still room. |
| 9/18 | Sept 28 – Oct 1. Sponsors join founders, investors, and civic leaders — and sit in the room for the Summit. |
