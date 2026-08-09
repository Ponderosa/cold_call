# Cold Calls — What one call looks like, side to side

Two strangers pick up handsets on opposite sides of an easel. Either side can be the caller — whoever lifts first becomes Side A for that call. The roles are not fixed to a physical side.

Conversation length is unbounded; all other durations are fixed.

## Before the call

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| idle | on hook, silent | on hook, silent |

## Someone picks up

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| 0:00 | **LIFTS THE HANDSET**<br>hears: dial tone | on hook<br>hears: nothing |
| 0:02 | dial tone cuts off<br>hears: touch-tone dialing<br>dials a random famous number — Jenny's 867-5309, and friends | hears: nothing |

## Ringing

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| 0:04 | hears: ringback<br>brrr—brrr ... brrr—brrr<br>plays once, about 6 seconds | **>>> THE PRINTER BUZZES**<br>one buzz every 2 seconds<br>The handset does not ring. The receipt printer is the bell — it is what recruits a stranger who has not opted in yet. |

## On hold

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| 0:10 | ringback ends, hears: *"This call requires another participant to continue holding the line…"*<br>message loops under hold music until someone answers or the call times out | printer still buzzing, unanswered |
| later | hold loop stops | **LIFTS THE HANDSET** |

## Side B picks up

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| +0s | hears: *"Both participants are now present."* | hears: dial tone |
| +0s | (still playing, timed to land with Side B's dialing) | dial tone cuts off, hears: touch-tone dialing |

> Side B hears its own dial tone + dialing on pickup, mirroring what the caller heard when they first lifted the handset. At the same time, Side A hears "Both participants are now present" — the two cues run concurrently and are timed to roughly the same length.

## The briefing

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| +0s | hears, the same moment as Side B: *"Greetings from the Seattle Municipal Office of Social Climate. You've been contracted by one of our sub-agencies to investigate a particular aspect of the social phenomenon known as the Seattle Freeze. You will soon be connected to a fellow investigator and given a printed questionnaire. Read the question aloud to them, then document their response on your questionnaire using the writing instruments provided, before posting your form to the board with an adhesive seal."* | hears, the same moment as Side A: *(same line)* |

## Printing your questionnaire

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| +0s | hears: *"Printing your questionnaire now."* | hears, the same moment: *"Printing your questionnaire now."* |
| +0s | **the receipt prints**<br>a prompt from this side's department | **the receipt prints**<br>a different prompt, from the other department |

> Printing happens after the "printing your questionnaire" line, not the moment Side B picks up. Takes 5–15 seconds, silent apart from the printers themselves. What lands on the paper is laid out under [The receipt, top to bottom](#the-receipt-top-to-bottom).

## Connected audio

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| +0s | hears: *"One moment please, your call is being connected."* | hears, the same moment: *"One moment please, your call is being connected."* |

## Connected

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| +0s | voice -----------> <----------- earpiece<br>rain / city ambience mixed softly underneath | <----------- earpiece  voice -----------><br>rain / city ambience mixed softly underneath |

> They talk. They read each other their questionnaire prompts and document each other's responses using the writing instruments provided. It runs as long as they both stay on the handset. There is no time limit.

## Either side hangs up

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| — | **HANGS UP**<br>or the other side does — it works the same either way | still holding the handset<br>hears: a click, then a busy tone, looping until they hang up too |
| +1s | both on hook — ready for the next pair | both on hook — ready for the next pair |

## If nobody answers

| Time | Side A — the caller | Side B — the receiver |
|---|---|---|
| 0:04 | hears: ringback, once (~6s) | printer buzzing, unanswered |
| 0:10 | hold loop: message + hold music, up to 30 seconds | printer buzzing, unanswered |
| 0:40 | hold loop stops, hears: *"We're sorry. The number you have dialed is not in service. Please hang up and try again."* | still on hook |
| 0:46 | click, then busy tone until they hang up | — |

## The receipt, top to bottom

The single footer line — "Please interview and record the response of the other party" — becomes
a numbered procedure wrapped around the question, so the receipt reads as the order you do things
in and each department states its own activity on the paper. A notice above the steps sets the
tone; the fourth step, posting the form, sits below the field because that is when it happens.
The department signs the receipt off at the foot rather than heading it — the seal already names
the agency at the top — and only a short centred mark separates it from the thanks, a beat
rather than a break.

| # | Element | Type | Change |
|---|---|---|---|
| 1 | 8mm top margin | — | — |
| 2 | Department seal | image, 288px | — |
| 3 | **DATA COLLECTION QUESTIONNAIRE** | bold 28 | **renamed** from APPROVED DIALOGUE |
| 4 | `Form 2-0002` | reg 16 | **priority removed**; form number stays |
| 5 | Dashed rule | drawn, 2px | **drawn** rather than typed hyphens |
| 6 | Notice — "Please follow the procedure below. Failure to comply may result in `<consequence>`." | reg 16 | **new**, consequence per department |
| 7 | `(1) Ask the following question to the respondent:` | reg 18 | **new** |
| 8 | The question | 36, all caps, thinned strokes, balanced wrap at 22 chars | **resized** from bold 40/14 |
| 9 | `(2) Listen to their response.` | reg 18 | **new** |
| 10 | `(3)` department activity | reg 18, hanging indent | **new** |
| — | *(second raster starts — on the gap, so the printer's feed lands on whitespace)* | | |
| 11 | Bounded data-entry field, caption inside | drawn | **replaces** the pasted worksheet PNG |
| 12 | `(4) Post your form to the board with an adhesive seal.` | reg 18 | **new** |
| 13 | Dashed rule | drawn, 2px | **new** |
| 14 | **COMMISSION ON DEFERRED ENTHUSIASM** | bold 18 | **moved** to the foot |
| 15 | *"Excitement at an Appropriate Pace"* | reg 16 | **moved** to the foot |
| 16 | Short centred mark | drawn, 48px | **new** |
| 17 | `Thank you for performing your civic duties.` | reg 16 | **new** |

Four type sizes and no others: **16** for supporting detail (form number, tagline, notice,
field caption, sign-off), **18** for the steps, **28** for the banner, **36** for the question.
The question is set in caps and lighter than regular. Courier Prime ships regular and bold and
nothing else, so the weight comes off the strokes at render time: drawn at 3x, downscaled, and
thresholded dark enough that only the core of each stroke survives. `QUESTION_WEIGHT` in
`printer.py` is the dial — lower is thinner, and it wants a test print before going much below
60, since thin strokes can drop out on a thermal head.
Bold does the rest of the work — the department name is bold at the step size, because it
identifies the sender rather than heading the page.

The question carries no frame and no rule. Step 1 ends on a colon pointing straight at it and
the widest interval on the receipt sits above and below — that is what sets it apart. Its wrap
is balanced, tightened as far as it can go without costing a line, so no question ends on a
lone orphan word. At 40 with a 14-character wrap, the longest prompts became ten-line towers.

The instructions wrap greedily to fill their lines: the steps take the full 45-character
column, four of which go to the `(n) ` prefix, and the notice takes 51. Balancing them would only make every line
narrower, which reads as heavier wrapping, not lighter.

Four vertical intervals — 12 / 20 / 36 / 52px — and every gap is one of them. The widest sits
above and below the question, which is most of what makes it read as the one thing on the page.

Everything that is not centered starts on the same 40px margin: the notice, all four steps,
the rules, and the field frames. Rules are drawn to that margin rather than typed out of
hyphens, which is what makes them all the same length. There is no rule above the field — its
frame is the boundary, and a rule stacked on a box just reads as a second, lighter box.

Steps 1 through 3 sit above the field and step 4 below it. Steps 1, 2, and 4 are the same on every
receipt; step 3 is the department's activity:

```
Please follow the procedure below. Failure to
comply may result in prolonged social ambiguity.

(1) Ask the following question to the
    respondent:

    What's a place where
     you felt like you
    belonged immediately,
      no effort required?

(2) Listen to their response.
(3) Draw a line that represents the respondent's
    journey of belonging. If desired, connect your
    line to another line on the board.

    [ field ]

(4) Post your form to the board with an adhesive
    seal.
```

### Activity and field by department

Fields are drawn from primitives rather than pasted artwork, so every department shares one
stroke weight, one margin, and one caption style. Every field is bounded: a 3px frame to the
margins with its caption inside the top left, the way a form names its own boxes, and the
contents inset within. An open panel and three ruled lines then read as the same kind of
object. Curves are painted on a 3x canvas and scaled down — a 1-bit canvas cannot antialias,
and drawn circles staircase without it.

| Department | Step 3 | Field | Consequence |
|---|---|---|---|
| Bureau of Ambient Belonging | Draw a line that represents the respondent's journey of belonging. If desired, connect your line to another line on the board. | Open panel, START and END marks on the centerline | prolonged social ambiguity |
| Department of Polite Indifference | Quote a highlight of your conversation, then put your receipt in the quad on the chart that feels representative of the respondent's answer. | Open space between two large quotation marks, as the original artwork had it | an unsolicited introduction |
| Office of Acceptable Proximity | Write a haiku inspired by the respondent's story (3 lines with 5, 7, and 5 syllables). | Three rules named FIVE / SEVEN / FIVE beneath, as the original artwork had it | a recalculation of your permitted distance |
| Administration for Minimal Engagement | Summarize the respondent's reason for minimally engaging in a single word. | One rule named ONE WORD beneath, as the original artwork had it | expanded participation requirements |
| Division of Conditional Invitations | Design an event invitation based on your conversation, and mark your projected attendance. | Invite form as the original artwork had it: EVENT NAME rules, THUMBNAIL box, RSVP YES / MAYBE / NO | a commitment without conditions |
| Commission on Deferred Enthusiasm | Draw facial expressions representing the respondent's expected and actual emotions about the situation. | Two full-width circles stacked, EXPECTED then ACTUAL, named underneath | a review of your enthusiasm levels |

The Bureau of Apathy is the test department and has no activity or field.

The activity and consequence strings live in `assets/departments.yaml` as `activity:` and
`consequence:` keys beside `name`, `tagline`, and `form` — that is already where `_compose_parts` reads department metadata
from, so nothing about the step block needs hardcoding per department.

The form number is generated, not authored: the department's `form` prefix plus a dispatch
counter that increments once per call and is shared by both sides, so a pair of receipts from
the same call carry the same number. The counter starts at zero on service start, so numbers
repeat across restarts.

## Audio asset manifest

**Sound effects** (non-verbal)

| Clip | Used where | Status |
|---|---|---|
| Dial tone | Side A pickup; Side B pickup (mirrored) | existing |
| Touch-tone dialing (DTMF) | Side A dials; Side B dials (mirrored) | existing |
| Ringback, single ring (~6s) | Side A, start of Ringing | existing |
| Printer buzzer | Side B's printer, every 2s while unanswered | existing (hardware buzzer, not a WAV) |
| Hold music bed | Underneath the looping hold message | raw track: `sources/hold_music_source.wav`; playable asset: `hold_loop.wav` |
| Hangup click | Whichever side is still on the line | existing |
| Busy tone | Looping, after hangup click | existing |
| Rain / city ambience | Mixed softly under live conversation | existing |

**Narration clips** (spoken)

| Line | Used where | Status |
|---|---|---|
| "This call requires another participant to continue holding the line." | Side A, looped under hold music while waiting | narration: `hold_message.wav`; playable asset: `hold_loop.wav` |
| "We're sorry. The number you have dialed is not in service. Please hang up and try again." | Side A, if nobody answers within the hold window | existing |
| "Both participants are now present." | Side A only, while Side B hears its dial tone + dialing | `both_present.wav` (padded to 4.1s to cover dial tone + DTMF) |
| The briefing (Office of Social Climate line, full text above) | Both sides, simultaneously | `briefing.wav` (27.9s) |
| "Printing your questionnaire now." | Both sides, simultaneously | `printing_questionnaire.wav` |
| "One moment please, your call is being connected." | Both sides, simultaneously | existing |

Everything in this manifest now exists in `assets/audio/`. The narration is Piper TTS
(en_US-amy-medium) via `scripts/gen_narration.py`. None of it is wired into `session.py` yet.

**The hold state needs one file, not two.** The music bed and the hold message have been
compiled into a single composite asset, `hold_loop.wav` — a 40-second loop with the message
laid over the music three times at even spacing, the bed ducking under each pass. Play it on
repeat for the whole hold state and it does everything the On hold row above describes; there
is no second stream to start, stop, or keep in sync. The two ingredients stay in the repo
(`hold_message.wav` and `sources/hold_music_source.wav`) so `scripts/mix_hold_loop.py` can
rebake the composite if the wording or the music changes.
