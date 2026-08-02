# Training Workspace

The active record of an athlete's training and nutrition, coached through
skills that plan in this repo and log in external apps (Hevy, MacroFactor).

## Language

**Coach's brief**:
The narrative presentation of a proposed training week, given to the
athlete for approval before anything is written: week focus, what's
changing and why, then per-session tables.
_Avoid_: summary, proposal, plan preview

**Weekly overlay**:
The per-exercise prescription for the current week, recorded in the newest
check-in's "The week ahead" section — the effective prescription adherence
is judged against.
_Avoid_: weekly plan, week's targets

**Approval gate**:
The rule that presenting proposed content (a coach's brief, a recipe
card) and writing it (to Hevy, repo files, or Notion) never happen in
the same turn — the athlete must reply first.
_Avoid_: confirmation step, sign-off

**Recipe bank**:
The athlete's set of approved recipe cards in `nutrition/menu/`, plus
its index — what `/meal-plan` selects from.
_Avoid_: food bank, menu (ambiguous with the directory name)

**Pantry**:
What's actually in the house — perishables, partial packs, staple
states — recorded in `nutrition/pantry.md`. Distinct from the recipe
bank: the bank is what the athlete can make; the pantry is what they
have.
_Avoid_: food bank, stock
