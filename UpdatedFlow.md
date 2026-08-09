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
three numbered steps wrapped around the question, so the receipt reads as the order you do things
in and each department states its own activity on the paper. The department identity moves to the
bottom, leaving the top of the receipt to the questionnaire itself.

| # | Element | Type | Change |
|---|---|---|---|
| 1 | 8mm top margin | — | — |
| 2 | Department seal | image, 288px | — |
| 3 | **DATA COLLECTION QUESTIONNAIRE** | bold 28 | **renamed** from APPROVED DIALOGUE (fits one line at 493px) |
| 4 | `Form 2-0002` | reg 18 | **priority removed**; form number stays |
| 5 | `- - - -` rule | — | — |
| 6 | `(1) Ask this question.` | reg 20, left-aligned | **new** |
| 7 | **The question** | bold 40, wrapped at 14 chars | — |
| 8 | `(2) Listen to their response.` | reg 20, left-aligned | **new** |
| 9 | `(3)` department activity | reg 20, left-aligned, hanging indent | **new** |
| — | *(second raster starts)* | | |
| 10 | `____` rule | — | — |
| 11 | Open field for data entry | image | the department's worksheet |
| 12 | `- - - -` rule | — | **new** |
| 13 | **BUREAU OF AMBIENT BELONGING** | bold 20 | **moved** from the top |
| 14 | *"Maintaining the Conditions for Togetherness"* | reg 16 | **moved** from the top |

Steps 1 and 2 are the same on every receipt. Step 3 is the department's activity, and it is the
last thing read before the open field:

```
(1) Ask this question.

     WHAT'S A PLACE
     WHERE YOU FELT
    LIKE YOU BELONGED
     IMMEDIATELY, NO
    EFFORT REQUIRED?

(2) Listen to their response.
(3) Draw a line that represents the respondent's
    journey of belonging. If desired, connect your
    line to another line on the board.
```

### Activity by department

| Department | Step 3 |
|---|---|
| Bureau of Ambient Belonging | Draw a line that represents the respondent's journey of belonging. If desired, connect your line to another line on the board. |
| Department of Polite Indifference | Quote a highlight of your conversation, then put your receipt in the quad on the chart that feels representative of the respondent's answer. |
| Office of Acceptable Proximity | Write a haiku inspired by the respondent's story (3 lines with 5, 7, and 5 syllables). |
| Administration for Minimal Engagement | Summarize the respondent's reason for minimally engaging in a single word. |
| Division of Conditional Invitations | Design an event invitation based on your conversation, and mark your projected attendance. |
| Commission on Deferred Enthusiasm | Draw facial expressions representing the respondent's expected and actual emotions about the situation. |

The Bureau of Apathy is the test department and has no activity.

These strings belong in `assets/departments.yaml` as a new `activity:` key beside `name`,
`tagline`, and `form` — that is already where `_compose_parts` reads department metadata
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
