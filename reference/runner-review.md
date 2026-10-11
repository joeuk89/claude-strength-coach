# Reviewing an outside running plan

Use this procedure only when the athlete already reports an outside running
plan or endurance event that matters to this decision. Otherwise skip it;
do not add fuelling questions to a non-runner's setup, goals or check-in.

1. Read `research/strength-for-running.md` and
   `research/endurance-fuelling.md`, including their Applying it sections.
   Check `python3 -m coach research status` and use
   `python3 -m coach research show <ref>` to inspect sources or a local
   supersession. Follow `reference/research-notes.md` for expired evidence
   or an athlete-specific question these notes do not answer.
2. Review how current lifting supports the stated running priority. Keep
   economy (rn:strength-for-running.1) separate from measured performance
   (rn:strength-for-running.2); explain uncertainty and use claim 3's scope
   rule (rn:strength-for-running.3). In run mode, respect the athlete's
   existing program and discuss structural changes only when requested.
3. Only when nutrition coaching is enabled, review fuelling relevance
   (rn:endurance-fuelling.1), before/during/after context
   (rn:endurance-fuelling.2) and practical tolerance
   (rn:endurance-fuelling.3). Reuse known duration, intensity, current
   strategy and outside advice; ask only what changes the decision. With
   nutrition declined or deferred, skip these questions unless the athlete
   asks to revisit it. Setup can leave this until its optional goals step.
4. At check-in, work from the Sunday reply and answers the athlete has
   already given; start no new interview. Record the relevant claim ids
   and uncertainty in the check-in record. Add any question to come back
   to with `python3 -m coach followups add`. When nothing relevant to
   running or fuelling changed that week, keep the previous review.

This is review-tier support: the athlete or outside plan owns running
progression. Coach-planned running remains deferred; these notes do not
generate planned activities, a race plan or new event storage. Routine
changes still follow the normal proposal and approval flow.

Keep existing calorie/protein targets and MacroFactor ownership. A
fuelling concern can prompt `/goals` to review the strategy or an explicit
nutrition override through its existing process. Never infer carbohydrate
numbers from an event label; a numeric proposal needs the note's evidence
population, duration/context and confidence checks before athlete review.
