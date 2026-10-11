<!-- coach:note
schema_version = 1
id = "resting-hr"
topic = "Resting heart rate as a fatigue and illness signal"
question = "Is a rise in resting heart rate above the athlete's own baseline worth flagging, and how should the baseline, threshold and minimum data be set?"
written = 2026-10-11
review_by = 2027-10-11
confidence = "low"
applies_to = ["deload", "return_to_training"]
tags = ["resting-hr", "wearables", "illness"]

[[sources]]
id = "bosquet-2008"
citation = "Bosquet L, Merkari S, Arvisais D, Aubert AE. Is heart rate a convenient tool to monitor over-reaching? A systematic review of the literature. Br J Sports Med. 2008;42(9):709-714."
url = "https://doi.org/10.1136/bjsm.2007.042200"
type = "meta-analysis"
year = 2008

[[sources]]
id = "meeusen-2013"
citation = "Meeusen R, Duclos M, Foster C, et al. Prevention, diagnosis, and treatment of the overtraining syndrome: joint consensus statement of the European College of Sport Science and the American College of Sports Medicine. Med Sci Sports Exerc. 2013;45(1):186-205."
url = "https://doi.org/10.1249/MSS.0b013e318279a10a"
type = "consensus"
year = 2013

[[sources]]
id = "nuuttila-2024"
citation = "Nuuttila OP, Uusitalo A, Kokkonen VP, Weerarathna N, Kyröläinen H. Monitoring fatigue state with heart rate-based and subjective methods during intensified training in recreational runners. Eur J Sport Sci. 2024;24(7):857-869."
url = "https://doi.org/10.1002/ejsc.12115"
type = "observational"
year = 2024

[[sources]]
id = "buchheit-2014"
citation = "Buchheit M. Monitoring training status with HR measures: do all roads lead to Rome? Front Physiol. 2014;5:73."
url = "https://doi.org/10.3389/fphys.2014.00073"
type = "narrative-review"
year = 2014

[[sources]]
id = "quer-2020"
citation = "Quer G, Gouda P, Galarnyk M, Topol EJ, Steinhubl SR. Inter- and intraindividual variability in daily resting heart rate and its associations with age, sex, sleep, BMI, and time of year: retrospective, longitudinal cohort study of 92,457 adults. PLoS One. 2020;15(2):e0227709."
url = "https://doi.org/10.1371/journal.pone.0227709"
type = "observational"
year = 2020

[[sources]]
id = "radin-2020"
citation = "Radin JM, Wineinger NE, Topol EJ, Steinhubl SR. Harnessing wearable device data to improve state-level real-time surveillance of influenza-like illness in the USA: a population-based study. Lancet Digit Health. 2020;2(2):e85-e93."
url = "https://doi.org/10.1016/S2589-7500(19)30222-5"
type = "observational"
year = 2020

[[sources]]
id = "mishra-2020"
citation = "Mishra T, Wang M, Metwally AA, et al. Pre-symptomatic detection of COVID-19 from smartwatch data. Nat Biomed Eng. 2020;4(12):1208-1220."
url = "https://doi.org/10.1038/s41551-020-00640-6"
type = "observational"
year = 2020

[[sources]]
id = "alavi-2022"
citation = "Alavi A, Bogu GK, Wang M, et al. Real-time alerting system for COVID-19 and other stress events using wearable data. Nat Med. 2022;28(1):175-184."
url = "https://doi.org/10.1038/s41591-021-01593-2"
type = "observational"
year = 2022

[[sources]]
id = "pietila-2018"
citation = "Pietilä J, Helander E, Korhonen I, Myllymäki T, Kujala UM, Lindholm H. Acute effect of alcohol intake on cardiovascular autonomic regulation during the first hours of sleep in a large real-world sample of Finnish employees: observational study. JMIR Ment Health. 2018;5(1):e23."
url = "https://doi.org/10.2196/mental.9519"
type = "observational"
year = 2018

[[sources]]
id = "plews-2014"
citation = "Plews DJ, Laursen PB, Le Meur Y, Hausswirth C, Kilding AE, Buchheit M. Monitoring training with heart rate-variability: how much compliance is needed for valid assessment? Int J Sports Physiol Perform. 2014;9(5):783-790."
url = "https://doi.org/10.1123/ijspp.2013-0455"
type = "observational"
year = 2014

[[sources]]
id = "bent-2020"
citation = "Bent B, Goldstein BA, Kibbe WA, Dunn JP. Investigating sources of inaccuracy in wearable optical heart rate sensors. NPJ Digit Med. 2020;3:18."
url = "https://doi.org/10.1038/s41746-020-0226-6"
type = "observational"
year = 2020

[[claims]]
n = 1
text = "A rise in resting heart rate above the athlete's own baseline is a weak sign of accumulated fatigue: overload of up to 2 weeks raises it by about 4.5 bpm on average, longer overload leaves it unchanged, and the change often sits within day-to-day noise."
basis = "evidence"
sources = ["bosquet-2008", "meeusen-2013", "nuuttila-2024"]
status = "current"

[[claims]]
n = 2
text = "An oncoming respiratory infection often raises resting heart rate above the athlete's baseline, a median of 3 days before symptoms in one prospective smartwatch study, but stress, alcohol, travel, intense exercise and vaccination raise it too."
basis = "evidence"
sources = ["alavi-2022", "mishra-2020", "radin-2020"]
status = "current"

[[claims]]
n = 3
text = "Resting heart rate is a less sensitive fatigue signal than heart rate variability measured at rest, with a signal-to-noise ratio of about 1.3 against 3 for a vagal HRV index."
basis = "evidence"
sources = ["buchheit-2014"]
status = "current"

[[claims]]
n = 4
text = "Alcohol raises heart rate in the first hours of sleep by about 1.4, 4.0 and 8.7 bpm after low, moderate and high intake, and resting heart rate also rises with stress, travel and hard training the day before, and differs with sleep length."
basis = "evidence"
sources = ["pietila-2018", "alavi-2022", "quer-2020", "buchheit-2014"]
status = "current"

[[claims]]
n = 5
text = "A single day's resting heart rate is too noisy to act on: the within-person day-to-day SD is about 3 bpm, and heart rate measures track performance only when averaged over at least 3 to 4 days."
basis = "evidence"
sources = ["quer-2020", "buchheit-2014", "radin-2020"]
status = "current"

[[claims]]
n = 6
text = "Compare the mean of the last 7 days, never a single morning, with a baseline: the mean of the daily readings in the 60 days before that window, recomputed each week."
basis = "heuristic"
sources = ["quer-2020", "radin-2020", "alavi-2022"]
status = "current"

[[claims]]
n = 7
text = "Flag when the 7-day mean is above the baseline by at least 3 bpm, or by one SD of the baseline's daily readings when that is larger."
basis = "heuristic"
sources = ["quer-2020", "alavi-2022", "bosquet-2008", "radin-2020"]
status = "current"

[[claims]]
n = 8
text = "Skip the flag, with a reason, when fewer than 5 of the 7 days in the window have a reading."
basis = "heuristic"
sources = ["plews-2014", "buchheit-2014", "radin-2020"]
status = "current"

[[claims]]
n = 9
text = "Skip the flag, with a reason, while fewer than 60 days of history precede the window or fewer than 40 of those 60 days have a reading."
basis = "heuristic"
sources = ["radin-2020"]
status = "current"

[[claims]]
n = 10
text = "Take the baseline and the window from one device's daily resting heart rate, and restart the 60-day baseline after a change of device, because each maker computes resting heart rate its own way."
basis = "heuristic"
sources = ["quer-2020", "bent-2020"]
status = "current"

[[claims]]
n = 11
text = "The flag prompts the coach to ask about illness symptoms, sleep, alcohol, heat, travel and stress, and it never counts as a deload fatigue trigger."
basis = "heuristic"
sources = ["bosquet-2008", "meeusen-2013", "alavi-2022"]
status = "current"
-->
<!-- coach:begin research resting-hr -->

**Template note** · written 2026-10-11 · review by 2027-10-11 · confidence low · areas deload, return_to_training · tags resting-hr, wearables, illness

| # | Claim | Basis | Sources | Status |
| --- | --- | --- | --- | --- |
| 1 | A rise in resting heart rate above the athlete's own baseline is a weak sign of accumulated fatigue: overload of up to 2 weeks raises it by about 4.5 bpm on average, longer overload leaves it unchanged, and the change often sits within day-to-day noise. | evidence | bosquet-2008, meeusen-2013, nuuttila-2024 | current |
| 2 | An oncoming respiratory infection often raises resting heart rate above the athlete's baseline, a median of 3 days before symptoms in one prospective smartwatch study, but stress, alcohol, travel, intense exercise and vaccination raise it too. | evidence | alavi-2022, mishra-2020, radin-2020 | current |
| 3 | Resting heart rate is a less sensitive fatigue signal than heart rate variability measured at rest, with a signal-to-noise ratio of about 1.3 against 3 for a vagal HRV index. | evidence | buchheit-2014 | current |
| 4 | Alcohol raises heart rate in the first hours of sleep by about 1.4, 4.0 and 8.7 bpm after low, moderate and high intake, and resting heart rate also rises with stress, travel and hard training the day before, and differs with sleep length. | evidence | pietila-2018, alavi-2022, quer-2020, buchheit-2014 | current |
| 5 | A single day's resting heart rate is too noisy to act on: the within-person day-to-day SD is about 3 bpm, and heart rate measures track performance only when averaged over at least 3 to 4 days. | evidence | quer-2020, buchheit-2014, radin-2020 | current |
| 6 | Compare the mean of the last 7 days, never a single morning, with a baseline: the mean of the daily readings in the 60 days before that window, recomputed each week. | heuristic | quer-2020, radin-2020, alavi-2022 | current |
| 7 | Flag when the 7-day mean is above the baseline by at least 3 bpm, or by one SD of the baseline's daily readings when that is larger. | heuristic | quer-2020, alavi-2022, bosquet-2008, radin-2020 | current |
| 8 | Skip the flag, with a reason, when fewer than 5 of the 7 days in the window have a reading. | heuristic | plews-2014, buchheit-2014, radin-2020 | current |
| 9 | Skip the flag, with a reason, while fewer than 60 days of history precede the window or fewer than 40 of those 60 days have a reading. | heuristic | radin-2020 | current |
| 10 | Take the baseline and the window from one device's daily resting heart rate, and restart the 60-day baseline after a change of device, because each maker computes resting heart rate its own way. | heuristic | quer-2020, bent-2020 | current |
| 11 | The flag prompts the coach to ask about illness symptoms, sleep, alcohol, heat, travel and stress, and it never counts as a deload fatigue trigger. | heuristic | bosquet-2008, meeusen-2013, alavi-2022 | current |

| Source | Citation | Type | Year |
| --- | --- | --- | --- |
| bosquet-2008 | [Bosquet L, Merkari S, Arvisais D, Aubert AE. Is heart rate a convenient tool to monitor over-reaching? A systematic review of the literature. Br J Sports Med. 2008;42(9):709-714.](<https://doi.org/10.1136/bjsm.2007.042200>) | meta-analysis | 2008 |
| meeusen-2013 | [Meeusen R, Duclos M, Foster C, et al. Prevention, diagnosis, and treatment of the overtraining syndrome: joint consensus statement of the European College of Sport Science and the American College of Sports Medicine. Med Sci Sports Exerc. 2013;45(1):186-205.](<https://doi.org/10.1249/MSS.0b013e318279a10a>) | consensus | 2013 |
| nuuttila-2024 | [Nuuttila OP, Uusitalo A, Kokkonen VP, Weerarathna N, Kyröläinen H. Monitoring fatigue state with heart rate-based and subjective methods during intensified training in recreational runners. Eur J Sport Sci. 2024;24(7):857-869.](<https://doi.org/10.1002/ejsc.12115>) | observational | 2024 |
| buchheit-2014 | [Buchheit M. Monitoring training status with HR measures: do all roads lead to Rome? Front Physiol. 2014;5:73.](<https://doi.org/10.3389/fphys.2014.00073>) | narrative-review | 2014 |
| quer-2020 | [Quer G, Gouda P, Galarnyk M, Topol EJ, Steinhubl SR. Inter- and intraindividual variability in daily resting heart rate and its associations with age, sex, sleep, BMI, and time of year: retrospective, longitudinal cohort study of 92,457 adults. PLoS One. 2020;15(2):e0227709.](<https://doi.org/10.1371/journal.pone.0227709>) | observational | 2020 |
| radin-2020 | [Radin JM, Wineinger NE, Topol EJ, Steinhubl SR. Harnessing wearable device data to improve state-level real-time surveillance of influenza-like illness in the USA: a population-based study. Lancet Digit Health. 2020;2(2):e85-e93.](<https://doi.org/10.1016/S2589-7500(19)30222-5>) | observational | 2020 |
| mishra-2020 | [Mishra T, Wang M, Metwally AA, et al. Pre-symptomatic detection of COVID-19 from smartwatch data. Nat Biomed Eng. 2020;4(12):1208-1220.](<https://doi.org/10.1038/s41551-020-00640-6>) | observational | 2020 |
| alavi-2022 | [Alavi A, Bogu GK, Wang M, et al. Real-time alerting system for COVID-19 and other stress events using wearable data. Nat Med. 2022;28(1):175-184.](<https://doi.org/10.1038/s41591-021-01593-2>) | observational | 2022 |
| pietila-2018 | [Pietilä J, Helander E, Korhonen I, Myllymäki T, Kujala UM, Lindholm H. Acute effect of alcohol intake on cardiovascular autonomic regulation during the first hours of sleep in a large real-world sample of Finnish employees: observational study. JMIR Ment Health. 2018;5(1):e23.](<https://doi.org/10.2196/mental.9519>) | observational | 2018 |
| plews-2014 | [Plews DJ, Laursen PB, Le Meur Y, Hausswirth C, Kilding AE, Buchheit M. Monitoring training with heart rate-variability: how much compliance is needed for valid assessment? Int J Sports Physiol Perform. 2014;9(5):783-790.](<https://doi.org/10.1123/ijspp.2013-0455>) | observational | 2014 |
| bent-2020 | [Bent B, Goldstein BA, Kibbe WA, Dunn JP. Investigating sources of inaccuracy in wearable optical heart rate sensors. NPJ Digit Med. 2020;3:18.](<https://doi.org/10.1038/s41746-020-0226-6>) | observational | 2020 |

<!-- coach:end research resting-hr -->

## Answer

A week of resting heart rate sitting above the athlete's own baseline is
worth a look, but it is a weak and non-specific signal: it picks up
oncoming illness better than training fatigue, and many everyday things
raise it. Compare a 7-day mean with the previous 60 days, never a single
morning, and flag a rise of at least 3 bpm or one baseline SD, whichever is
larger. Confidence is low: no study tests these numbers in lifters.

## Evidence

**Claim 1.** Bosquet et al. (2008) pooled overload studies in competitive
athletes. Interventions of up to 2 weeks gave "a moderate increase" in
resting HR (SMD 0.55), which the ECSS/ACSM consensus (Meeusen et al. 2013)
reports as about +4.5 bpm; longer interventions left resting values
unchanged. The authors conclude that "the small to moderate amplitude of
these alterations limits their clinical usefulness, as expected
differences may fall within the day-to-day variability of these markers".
The consensus statement adds that "changes of resting heart rate are not
consistently found in athletes experiencing OTS" (overtraining
syndrome), and one overtrained athlete it describes had a lower resting
HR, not a higher one. In
recreational runners, Nuuttila et al. (2024) saw nocturnal HR rise by
3.2 % in those who overreached and fall by 2.8 % in those who adapted over
a 2-week overload, so the direction does carry some information, but the
change is a few beats per minute at most.

**Claim 2.** Radin et al. (2020) found that the share of Fitbit users with
a raised weekly resting HR tracked state influenza rates. Mishra et al.
(2020) found heart rate, step or sleep changes in 81 % of 32 COVID-19
cases, and 63 % could have been flagged before symptoms from resting-HR
rises over the individual baseline. In a prospective cohort of 3,318
people, Alavi et al. (2022) alerted on 80 % of infections, with signals a
median of 3 days before symptoms. Their participants reported that
stress, intense exercise, alcohol, travel, altitude and vaccination also
set the alerts off, at a lower rate.

**Claim 3.** Buchheit (2014) reviews HR measures for monitoring and cites
a signal-to-noise ratio of 3 for a vagal HRV index against 1.3 for supine
resting HR. He still recommends collecting resting HR and rMSSD together,
as they are cheap and the HRV advantage is slight in correlations with
performance. HRV flags are out of scope for this note.

**Claim 4.** Pietilä et al. (2018) compared 4,098 adults' nights with and
without alcohol: sleeping HR in the first 3 hours rose by 1.4, 4.0 and
8.7 bpm with low (≤0.25 g/kg), moderate and high (>0.75 g/kg) intake.
Quer et al. (2020) found the lowest resting HR in people sleeping
7–7.5 h, with higher values on both sides; this compares people, not
nights. Alavi et al. (2022) list stress, intense exercise, alcohol and
travel among non-infection alert triggers. Buchheit (2014) notes that
heart rate measures respond to the environment and to the previous day's
training, which must be known to read a change.

**Claim 5.** Across 92,457 adults, Quer et al. (2020) measured an average
within-person SD of daily resting HR of 3.03 bpm, with a median weekly
fluctuation of about 3 bpm; 20 % had at least one week with a range of
10 bpm or more. Buchheit (2014) reports that HR measures related to
performance only when averaged over at least 3–4 days.

**Claim 6.** A coaching rule. Radin et al. (2020) worked with weekly
means, and a 7-day window matches the weekly check-in. Published
baselines range from a streaming
median that settles after about 7 nights (Alavi et al. 2022), to a
28-day sliding window (Alavi et al.'s CuSum method), to each person's
whole 2-year record (Radin et al. 2020, who required 60 days of wear).
No study compares baseline lengths. 60 days spans a full training block
with its light week, so one hard or sick week moves the baseline little,
while a rolling window still follows the population's seasonal swing of
about 2 bpm across the year (Quer et al. 2020).

**Claim 7.** A coaching rule, tuned to raise few false flags. 3 bpm is
the typical within-person day-to-day SD and the median weekly
fluctuation (Quer et al. 2020), and Alavi et al. (2022) used +3 bpm for a
warning and +4 bpm on successive nights for an alert. A 7-day mean that
high means the whole week ran a full day's SD above normal, which noise
alone rarely produces. The one-SD alternative raises the line for the
athletes whose readings swing widely. Radin et al. (2020) flagged weekly
means only 0.5 SD above the mean, but they wanted population trends, not
individual alerts. The cost of this line: the few-per-cent rise seen in
overreached runners (claim 1) will often stay under it.

**Claim 8.** A coaching rule. Plews et al. (2014) found that a weekly HRV
mean needs at least 3 randomly chosen valid days to match the full
week, and Radin et al. (2020) dropped user-weeks with fewer than 4
resting-HR readings. Requiring 5 is stricter than either, so that one
outlier night, such as an evening of drinking, weighs less in the
mean: one night 8.7 bpm high still adds about 1.7 bpm to a 5-day mean.

**Claim 9.** A coaching rule. 60 days of history is the baseline's
length (claim 6), and Radin et al. (2020) also required 60 days of wear
before using a person's data. 40 of 60 days keeps the baseline to the
same share of days with readings as the window (about two thirds).

**Claim 10.** A coaching rule. Quer et al. (2020) note that Fitbit
computes resting HR with a proprietary formula, mostly from sleep, and
that it varies with whether the watch is worn overnight. Bent et al.
(2020) found consumer wearables reasonably accurate at rest but different
from each other. Mixing devices would put the gap between two algorithms
into the comparison.

**Claim 11.** A coaching rule. Bosquet et al. (2008) and the ECSS/ACSM
consensus both say HR changes need other signs and symptoms to mean
anything, and claim 2 shows that infection and lifestyle explain many
rises. Heat is listed from coaching practice: no source checked here
gives a number for it.

## Applying it

These are the numbers for the planned resting-HR trend flag. The flag
itself is not built yet.

| Parameter | Value | Claim |
| --- | --- | --- |
| Window | mean of the last 7 days | 6 |
| Baseline | mean of the 60 days before the window, recomputed weekly | 6 |
| Threshold | +3 bpm, or +1 SD of the baseline's daily readings if larger | 7 |
| Window minimum | 5 of 7 days with a reading | 8 |
| Baseline minimum | 60 days of history, 40 of 60 days with a reading | 9 |
| Source | one device; a new device restarts the baseline | 10 |

- When the flag fires, ask about symptoms first. If the athlete is ill,
  the illness return rule applies (rn:detraining-return.4).
- Read the flag alongside the deload fatigue triggers in `/check-in`; it
  never counts as one (claim 11).
- A quiet flag doesn't mean the athlete is recovered (claims 1 and 3).

## Open questions

- No study tests resting HR as a fatigue signal in lifters doing
  resistance training: the overload studies are in endurance athletes.
- Whether 3 bpm or one SD is the right line. A real 60-day series from an
  athlete's watch should be checked for how often it would fire.
- Caffeine: no source checked here measures its effect on overnight
  resting HR.
- Whether the baseline should use the median instead of the mean, so a
  sick week inside it can't lift it.
