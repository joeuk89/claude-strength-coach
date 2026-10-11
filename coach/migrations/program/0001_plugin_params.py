"""Program v1 to v2: slot constraints take the load-constraint shape (contract C23, C26).

Scheme, schedule and deload names are unchanged; v2 checks each one's
params against its plugin. A v1 constraint was free text that nothing can
enforce, so it is dropped and named in the report for the coach to rewrite.
"""

DOC = "program"
FROM = 1
TO = 2


def migrate(doc):
    for session in doc["sessions"]:
        for exercise in session["exercises"]:
            exercise["constraints"] = []
    return doc


def notes(before, after):
    found = []
    for session in before["sessions"]:
        for exercise in session["exercises"]:
            for text in exercise.get("constraints", []):
                found.append(f"data/program.json: {session['id']}/{exercise['exercise_id']} constraint \"{text}\" "
                             "was dropped; rewrite it as a load constraint (rpe_cap, no_added_load or load_cap)")
    return found
