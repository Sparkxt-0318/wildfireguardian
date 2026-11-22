"""PROTOCOL 2.2-2.3 first pass: keyword classes for each unique workbook observation.
Usage: python3 -I classify.py data/observations_dedup.csv data/classes_pass1.csv
Order of rules (first match wins): ROAD_PASSABLE, ROAD_CLOSED, ROAD_BLOCKED_OTHER, OTHER (not-yet / distant / residual /
embers or smoke only), FIRE_ARRIVAL, OTHER. The rule that fired is written next to each label."""
import csv, re, sys

ROADW = r"(?:road|roadway|rd|street|st|lane|ln|drive|dr|way|skyway|highway|hwy|pavement|lanes|split|intersection|[A-Z][\w']+ (?:rd|ln|dr|way|st)\.?)"
NAMED = r"(?:[A-Z][\w']+(?: [A-Z][\w']+)? (?:Rd|Ln|Dr|Way|St|Ave|Cir|Ct)\b|Skyway|Hwy \d+|Highway|Lunt|Coutolenc|Hoffman|Concow)"
RULES = [
    ("ROAD_PASSABLE", "passage", re.compile(
        r"(?<!im)passable|(?<!not )(?<!cannot )(?<!can't )(?<!unable to )\b(?:drove|drive|driving|drives|travel(?:ed|ing)?) (?:out )?(?:through|thru)\b|"
        r"(?<!cannot )(?<!can't )(?<!not )\bgood enough to get through|\b(?:got|made it) (?:through|out)\b|\bable to (?:get through|pass)\b|\b(?:make|made|makes) passage\b|"
        r"traffic (?:is )?(?:flowing|moving)|full speed|evacuated through|intermittently passable", re.I)),
    ("ROAD_CLOSED", "fire_across_or_on_road", re.compile(
        r"(?:fire|flames?|spots?|spotted|spotting|burning|front|run|crown|it)\b.{0,40}\b(?:across|over|crossing|crossed|crosses|jumped(?: over| to| the)?)\s+(?:the\s+)?(?:" + ROADW + r"|" + NAMED + r")|"
        r"(?:fire|flames?|burning|spots?|spot fires?|torching|involved|everything).{0,40}\bboth sides?\b|\bboth sides?\b.{0,30}(?:fire|burning|flames?|involved)|"
        r"\bboth sides?(?: of)?(?: the)? (?:" + ROADW + r"|" + NAMED + r")|"
        r"blocked by fire|blocking (?:the )?(?:" + ROADW + r"|" + NAMED + r")|(?:road|roadway|traffic).{0,25}blocked by (?:fire|burning)|"
        r"burning vehicles? in (?:the )?(?:road|roadway)|vehicles? (?:in|on) (?:the )?(?:road|roadway).{0,20}(?:on fire|burning)|blocked by burning|"
        r"(?:cannot|can't|unable to|too \w+ to) (?:pass|get through|access)|impassable|inaccessible due to fire|stopped by fire|trapped by fire|"
        r"burned over \b(?:" + ROADW + r"|" + NAMED + r")|burned over at|engulfed in fire|blow ?torching the road|wall of fire on|"
        r"fire (?:blocking|across) (?:the )?(?:" + ROADW + r"|" + NAMED + r")|flames horizontal over|flames (?:fully or partially )?blocking|"
        r"(?:hitting|impacting|overtaking|crossing) (?:the )?(?:roadway|road\b)|fire (?:is )?overtaking (?:vehicles|traffic|line of traffic)|"
        r"impacting line of traffic|skyway fully involved|split is fully involved|everything on fire (?:on )?(?:skyway|pentz|clark)", re.I)),
    ("ROAD_BLOCKED_OTHER", "blocked_not_fire", re.compile(
        r"\bblocked\b|\bblocking\b|gridlock|road closed|closed road|turn(?:ed)? around|cannot get out", re.I)),
    ("OTHER", "not_yet_distant_residual_or_ember_smoke", re.compile(
        r"not (?:here|there) yet|about to|approaching|threaten|toward|towards|heading|can see|could see|see (?:fire|flames|smoke)|\bglow\b|"
        r"\bhear\b|already (?:burned|destroyed|consumed)|burned (?:to|down)|destroyed|past peak(?!.{0,30}active)|fire (?:has )?passed|"
        r"^(?:hot )?embers?\b(?!.*\b(?:fire|flames?|burning)\b)|^(?:heavy )?(?:smoke|ember)", re.I)),
    ("FIRE_ARRIVAL", "fire_present", re.compile(
        r"\bfire\b|flames?|burning|\bburn\b|\bspots?\b|spotting|torch|ignit|involved|engulf|crown|on fire|catch(?:es|ing)? fire|caught fire", re.I)),
]
# the OTHER rule must not swallow a present-fire statement such as "fire coming into X" ... "fire on both sides": those are
# caught earlier by ROAD_CLOSED. "toward" with an explicit present-fire marker stays FIRE_ARRIVAL:
PRESENT = re.compile(r"\b(?:spot fires? (?:on|in|at)|fire (?:in|on|at) (?!the canyon)|is burning|are burning|burning (?:on|in|at)|on fire|fully involved|structures? (?:burning|involved))", re.I)


def classify(text, fire_type):
    for label, rule, rx in RULES:
        if rx.search(text):
            if label == "OTHER" and PRESENT.search(text):
                return "FIRE_ARRIVAL", "fire_present_despite_toward"
            return label, rule
    return "OTHER", "no_rule"


if __name__ == "__main__":
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    for r in rows:
        r["class_pass1"], r["rule_pass1"] = classify(r["text"], r["fire_type"])
    with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["obs_id", "time", "lat", "lon", "fire_type", "class_pass1", "rule_pass1", "text"], extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    from collections import Counter
    print(Counter(r["class_pass1"] for r in rows))
