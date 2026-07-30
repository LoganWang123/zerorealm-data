# ZeroRealm Operator Content Growth Design

## Goal

Turn the ZeroRealm public account and website into a focused acquisition channel for smart-cabinet operators and operating managers, while replacing generic generated media with credible retail-operations visuals.

## Audience and promise

The first audience is the owner or operating manager of a smart-cabinet business. Every public article must help that reader answer one operating question: what changed, whether it affects their cabinets, which number to inspect, and what small action is justified now.

The public promise is:

> 看懂一条行业变化，做对一个柜机经营动作。

CEO, device-maker, brand, and investor perspectives remain available to the long-term platform, but they are not co-equal sections in the cold-start public-account product.

## Content format

Each report contains one primary story and at most two supporting signals. The target length is 1,000–1,500 Chinese characters. The opening screen states the event, the affected operating metric, and the recommended next check.

The article separates:

1. Verified fact with a direct source URL.
2. Operating impact tied to inventory, sell-through, gross margin, replenishment, loss, or site efficiency.
3. One conditional action with a measurable stop rule.

Predictions are optional. Unsupported percentages, forced smart-cabinet connections, generic financing filler, and advice for four different personas are rejected.

## Distribution

Free publication and follower notification are separate explicit modes. The CLI must label free publication as non-notifying and expose a deliberate mass-notification mode. Mass notification requires an explicit command flag, uses an all-follower filter, and records the returned message identifier. Comments are enabled for followers on created drafts.

No automated test or default command may send a real notification.

## Quality gates

Before an article is written or published:

- Reject a headline that substantially repeats a recent published headline.
- Reject reuse of a previously published direct source URL.
- Require exactly one core operating story and no more than two supporting signals.
- Require a direct HTTP(S) source URL on every included signal.
- Require the core story to name at least one operating metric or decision.
- Keep the WeChat title within 30 Chinese characters where practical and ensure it does not promise unsupported AI behavior.

## Visual system

Daily covers use documentary retail imagery: real cabinets, products, replenishment, site operations, and inventory observation. They avoid generic AI people, neon beams, fake dashboards, embedded text, logos, and decorative technology metaphors.

The homepage poster and 15-second film show one coherent operator workflow:

1. Inspect a real cabinet and identify an inventory or assortment signal.
2. Review product and operating evidence without fake readable UI.
3. Adjust assortment or replenishment and return to the cabinet.

The website supplies the three explanatory labels outside the video, so generated footage never needs to render text.

## Website

The hero changes from a broad knowledge-platform statement to the operator promise. The media section explains the three-stage workflow and remains manual-play, non-looping, and accessible. The media manifest carries structured story-beat labels consumed by the component.

## Verification

- Python tests cover fuzzy headline deduplication, report quality validation, mass-notification payloads, comment settings, and new prompt contracts.
- Node tests cover the structured homepage story and accessible video props.
- Full Python, Node, lint, type-check, and production-build verification must pass.
- Generated images are visually inspected at full size.
- Video frames at the beginning, middle, and end must visibly progress through the three operator-workflow stages.

