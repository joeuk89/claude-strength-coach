<!-- coach:note
schema_version = 1
id = "fixture-dose"
topic = "Fixture dose"
question = "How many hard sets per muscle does the fixture program aim for?"
written = 2026-09-01
review_by = 2028-03-01
confidence = "moderate"
applies_to = ["volume"]
tags = ["fixture"]

[[sources]]
id = "fixture-meta-2024"
citation = "Fixture A, Fixture B. A synthetic meta-analysis used only by the coach test suite. Test Data J. 2024;1:1-10."
url = "https://doi.org/10.0000/fixture-meta-2024"
type = "meta-analysis"
year = 2024

[[sources]]
id = "fixture-rct-2025"
citation = "Fixture C. A synthetic trial used only by the coach test suite. Test Data J. 2025;2:11-20."
url = "https://doi.org/10.0000/fixture-rct-2025"
type = "rct"
year = 2025

[[claims]]
n = 1
text = "The fixture program aims for 10 hard sets per muscle per week."
basis = "evidence"
sources = ["fixture-meta-2024"]
status = "current"

[[claims]]
n = 2
text = "The fixture program caps one session at 6 hard sets per muscle."
basis = "evidence"
sources = ["fixture-rct-2025"]
status = "current"
-->
<!-- coach:begin research fixture-dose -->

**Template note** · written 2026-09-01 · review by 2028-03-01 · confidence moderate · areas volume · tags fixture

| # | Claim | Basis | Sources | Status |
| --- | --- | --- | --- | --- |
| 1 | The fixture program aims for 10 hard sets per muscle per week. | evidence | fixture-meta-2024 | current |
| 2 | The fixture program caps one session at 6 hard sets per muscle. | evidence | fixture-rct-2025 | current |

| Source | Citation | Type | Year |
| --- | --- | --- | --- |
| fixture-meta-2024 | [Fixture A, Fixture B. A synthetic meta-analysis used only by the coach test suite. Test Data J. 2024;1:1-10.](<https://doi.org/10.0000/fixture-meta-2024>) | meta-analysis | 2024 |
| fixture-rct-2025 | [Fixture C. A synthetic trial used only by the coach test suite. Test Data J. 2025;2:11-20.](<https://doi.org/10.0000/fixture-rct-2025>) | rct | 2025 |

<!-- coach:end research fixture-dose -->

## Answer

A synthetic note for the coach test suite. It holds two current claims.

## Evidence

Claim 1 rests on the synthetic meta-analysis; claim 2 on the synthetic trial.

## Applying it

Nothing: this note exists only to exercise the research commands.

## Open questions

None.
