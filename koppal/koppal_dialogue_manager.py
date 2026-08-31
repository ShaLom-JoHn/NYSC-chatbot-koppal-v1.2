"""
dialogue_manager.py -- the branch 0-3 decision flow, plus the shared
lookup data + matching logic it runs on. No NYSC answer content lives
here (that's knowledge_base.csv) -- everything below is either lookup
data or the decision logic that consumes it. Formerly split across
this file and slots.py; folded together since slots.py had no
independent role and everything in it was only ever consumed here.
"""

import difflib
import random
import re
import koppal_chitchat as chitchat


# ============================================================
# LOOKUP DATA + MATCHING LOGIC (formerly slots.py)
# ============================================================

# ------------------------------------------------------------
# FUZZY MATCH HELPER -- shared by every list/dict below
# ------------------------------------------------------------
def fuzzy_match(value: str, candidates, cutoff: float = 0.6):
    """
    Return the closest match to `value` among `candidates` (a list of
    strings, or a dict whose keys are the candidates), above `cutoff`.
    Returns None if nothing clears the threshold.
    """
    value = value.strip().lower()
    pool = list(candidates.keys()) if isinstance(candidates, dict) else list(candidates)
    pool_lower = [c.lower() for c in pool]
    result = difflib.get_close_matches(value, pool_lower, n=1, cutoff=cutoff)
    if not result:
        return None
    idx = pool_lower.index(result[0])
    return pool[idx]


# ------------------------------------------------------------
# YES/NO -- shared across ~12 yes_no Conditional intents
# ------------------------------------------------------------
YES_NO_LIST = {
    "yes": ["yes", "yeah", "yep", "yup", "sure", "correct", "affirmative", "no wahala"],
    "no": ["no", "nope", "not really", "nah", "negative", "never"],
}


# ------------------------------------------------------------
# STATES -- 36 + FCT, used by logistics_travel_to_camp,
# state_secretariat_location
# ------------------------------------------------------------
STATES_LIST = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
    "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
    "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT",
]


# ------------------------------------------------------------
# INSTITUTION CODES -- from term_lookup's KB content (user-compiled,
# spot-checked LAG/FUTO against independent sources)
# ------------------------------------------------------------
INSTITUTION_CODES = {
    "IFE": "Obafemi Awolowo University (OAU)", "FCT": "University of Abuja (UNIABUJA)",
    "NUA": "Nnamdi Azikiwe University (UNIZIK)", "ABU": "Ahmadu Bello University",
    "UNN": "University of Nigeria, Nsukka", "LAG": "University of Lagos (UNILAG)",
    "IBD": "University of Ibadan (UI)", "BEN": "University of Benin (UNIBEN)",
    "ILR": "University of Ilorin (UNILORIN)", "LAS": "Lagos State University (LASU)",
    "BUK": "Bayero University Kano", "ADS": "Adekunle Ajasin University (AAUA)",
    "UCA": "University of Calabar (UNICAL)", "UJO": "University of Jos (UNIJOS)",
    "UPH": "University of Port Harcourt (UNIPORT)", "UNM": "University of Maiduguri (UNIMAID)",
    "UDU": "Usmanu Danfodiyo University (UDUS)", "FUTM": "Federal University of Technology Minna",
    "FUTA": "Federal University of Technology Akure", "FUTO": "Federal University of Technology Owerri",
    "UNA": "Federal University of Agriculture Abeokuta (FUNAAB)", "DEL": "Delta State University Abraka (DELSU)",
    "EBS": "Ebonyi State University (EBSU)", "YAB": "Yaba College of Technology",
    "KWP": "Kwara State Polytechnic", "FPI": "Federal Polytechnic Ilaro",
    "FPA": "Federal Polytechnic Ado-Ekiti", "FPN": "Federal Polytechnic Nekede",
    "FPO": "Federal Polytechnic Offa", "IMT": "Institute of Management and Technology Enugu",
    "KAP": "Kaduna Polytechnic", "MAP": "Moshood Abiola Polytechnic",
    "AUP": "Auchi Polytechnic",
    "FRN": "Foreign-Trained Graduates (category code, not a single institution)",
    "EXC": "Exemption (internal tracking category)", "REM": "Remobilization (internal tracking category)",
}


# ------------------------------------------------------------
# INSTITUTION NICKNAMES -- reverse lookup. INSTITUTION_CODES above is keyed by
# the NYSC code (IFE, LAG, NUA...), and lookup_term() only ever matches on KEYS,
# so a corps member who types the school's common nickname ("OAU", "UNILAG")
# matched nothing before this table existed -- the nicknames were only sitting
# inside the values. Keys here are what people actually type.
# ------------------------------------------------------------
INSTITUTION_NICKNAMES = {
    "OAU": "Obafemi Awolowo University (NYSC institution code: IFE)",
    "UNIABUJA": "University of Abuja (NYSC institution code: FCT)",
    "UNIZIK": "Nnamdi Azikiwe University (NYSC institution code: NUA)",
    "UI": "University of Ibadan (NYSC institution code: IBD)",
    "UNILAG": "University of Lagos (NYSC institution code: LAG)",
    "UNIBEN": "University of Benin (NYSC institution code: BEN)",
    "UNILORIN": "University of Ilorin (NYSC institution code: ILR)",
    "LASU": "Lagos State University (NYSC institution code: LAS)",
    "AAUA": "Adekunle Ajasin University (NYSC institution code: ADS)",
    "UNICAL": "University of Calabar (NYSC institution code: UCA)",
    "UNIJOS": "University of Jos (NYSC institution code: UJO)",
    "UNIPORT": "University of Port Harcourt (NYSC institution code: UPH)",
    "UNIMAID": "University of Maiduguri (NYSC institution code: UNM)",
    "UDUS": "Usmanu Danfodiyo University (NYSC institution code: UDU)",
    "FUNAAB": "Federal University of Agriculture Abeokuta (NYSC institution code: UNA)",
    "DELSU": "Delta State University Abraka (NYSC institution code: DEL)",
    "EBSU": "Ebonyi State University (NYSC institution code: EBS)",
    "YABATECH": "Yaba College of Technology (NYSC institution code: YAB)",
}

# Scheme-level terms that appear in almost every message sent to this bot. They are
# valid glossary entries, but they must never win over the term actually being asked
# about, so lookup_term() only falls back to them when nothing specific matched.
GENERIC_TERMS = {"NYSC"}


# ------------------------------------------------------------
# GLOSSARY -- from term_lookup's KB content
# ------------------------------------------------------------
GLOSSARY = {
    "PCM": "Prospective Corps Member (before you're mobilised)",
    "CDS": "Community Development Service (your weekly community project throughout service)",
    "SAED": "Skill Acquisition and Entrepreneurship Development (skills training NYSC runs)",
    "PPA": "Place of Primary Assignment (where you serve after camp)",
    "LGI": "Local Government Inspector (oversees corps members in your LGA, handles monthly clearance)",
    "Senate List": "your institution's official list of graduates submitted to NYSC, required before registration",
    "Green Card": "informal name for your NYSC identity card",
    "Batch/Stream": "the three yearly mobilisation batches (A, B, C), each split into Stream 1/2",
    "Revalidation": "reactivating your registration if deployed previously but didn't report to camp",
    "Ajuwaya": "camp slang from the military command 'As You Were', used informally to address corps members",
    "Exemption Certificate": "issued to those excused from service entirely (age, prior service)",
    "Exclusion Letter": "issued when NYSC determines you're not eligible to participate",
    "Concessional Posting": "requesting posting near your husband or based on a serious health condition",
    "Discharge Certificate": "same document as Certificate of National Service -- informal vs official name",
    "Corper": "informal Nigerian slang for a serving NYSC member",
    "Allowee": "informal slang for 'allowance', the monthly stipend paid to corps members",
    "State Code": "your official NYSC ID number issued after camp registration -- contains your state abbreviation, year/batch, and a unique serial number (distinct from your Call-Up Number)",
    "Call-Up Letter": "the document issued before camp informing a PCM of their deployment, orientation camp location, and reporting date",
    "PV": "Payment Voucher -- document Corps members sign before receiving their monthly allowance",
    "LGA": "Local Government Area -- the district-level unit your LGI oversees",
    "Domicile Letter": "a letter from a husband to NYSC requesting his wife's redeployment to his state of residence",
    "Decampment": "involuntary removal of a Prospective Corps Member from orientation camp, usually for a rules breach",
    "Ghost Corper": "a corps member who doesn't participate in service activities but still collects allowance -- risky and against NYSC rules",
    "Mami Market": "the market/shops inside orientation camp selling food, provisions, and services to corps members and camp officials",
    "Otondo": "camp slang (often used by soldiers) for new or mistake-making corps members -- the exact origin isn't clear",
    "CLO": "Corps/Community Liaison Officer -- links corps members with the host community",

    # ---- Scheme, mobilisation & exams ----
    "NYSC": "National Youth Service Corps -- the one-year national service scheme for Nigerian graduates",
    "JAMB": "Joint Admissions and Matriculation Board -- runs the UTME; NYSC checks your admission was JAMB-regularised",
    "WAEC": "West African Examinations Council -- the SSCE/O'level exam body",
    "NECO": "National Examinations Council -- Nigerian O'level/SSCE body, an alternative to WAEC",
    "NABTEB": "National Business and Technical Examinations Board -- technical/vocational O'level exams",
    "GCE": "General Certificate of Education -- O'level exam, e.g. WAEC GCE for private candidates",
    "UTME": "Unified Tertiary Matriculation Examination -- JAMB's tertiary entrance exam",
    "CBT": "Computer-Based Test -- the electronic exam format, e.g. for the UTME",
    "CAPS": "Central Admissions Processing System -- JAMB's portal where admission is offered and accepted",
    "MOBREG": "Mobilisation Registration -- the online pre-mobilisation registration on the NYSC portal",
    "POP": "Passing Out Parade -- the closing ceremony ending your service year, where you receive your certificate",

    # ---- Documents, results & IDs ----
    "SOR": "Statement of Result -- interim proof of results before the certificate is issued",
    "FSLC": "First School Leaving Certificate -- primary-school completion certificate",
    "NIN": "National Identification Number -- your 11-digit national ID from NIMC",
    "CNS": "Certificate of National Service -- the official name for your discharge/NYSC certificate",
    "Call-Up Number": "the unique ID number on your call-up letter (distinct from your State Code)",
    "Medical Certificate of Fitness": "health clearance required before camp admission",

    # ---- Finance & banking ----
    "BVN": "Bank Verification Number -- your unique banking ID, used to open your NYSC allowance account",
    "RRR": "Remita Retrieval Reference -- the code generated when you pay NYSC/school fees via Remita",
    "CBN": "Central Bank of Nigeria -- the national banking regulator",
    "Allawee": "spelling variant of Allowee -- the monthly allowance paid to corps members",

    # ---- Qualifications & regulators ----
    "HND": "Higher National Diploma -- polytechnic degree, mobilised the same as a first degree",
    "ND": "National Diploma -- lower polytechnic qualification, not NYSC-eligible on its own",
    "NOUN": "National Open University of Nigeria -- distance-learning university whose graduates are mobilised",
    "NUC": "National Universities Commission -- regulates Nigerian universities",
    "MDCN": "Medical and Dental Council of Nigeria -- licenses doctors and dentists",
    "PCN": "Pharmacists Council of Nigeria -- licenses pharmacists",
    "FRSC": "Federal Road Safety Corps -- road-safety agency, sometimes a PPA/CDS partner",
    "SAO": "Student Affairs Office -- your institution's office that handles NYSC mobilisation",
    "SIWES": "Students Industrial Work Experience Scheme -- undergraduate industrial training, not the same as NYSC",
    "ITF": "Industrial Training Fund -- the agency that coordinates SIWES",
    "LFN": "Laws of the Federation of Nigeria -- how Nigerian statutes are cited, e.g. NYSC Act, LFN 2004",
    "DSSC": "Direct Short Service Commission -- a military commission route",

    # ---- NYSC officials & structure ----
    "DG": "Director-General -- the national head of NYSC",
    "ZI": "Zonal Inspector -- NYSC officer overseeing a zone, above LGI level",
    "LI": "Local Government Inspector (same as LGI) -- monitors corps members in an LGA",
    "NDHQ": "NYSC National Directorate Headquarters -- the national head office in Abuja",

    # ---- Camp life & drill ----
    "Platoon": "the sub-group corps members are divided into during camp",
    "Book of Life": "the camp attendance register everyone signs before leaving",
    "Man O' War": "the drill instructors at camp (also just called 'soldiers')",
    "MOW": "Man O' War -- the drill instructors at camp",
    "Camp Commandant": "the highest-ranking officer in charge of an orientation camp",
    "CC": "Camp Commandant -- the highest-ranking officer in charge of an orientation camp",
    "OBS": "Orientation Broadcasting Service -- the in-camp radio/announcements station",
    "Family House": "camp accommodation for married corps members and their spouses",
    "Light-Out Hour": "the mandatory lights-off/sleep time in camp",
    "Double Up": "camp drill command meaning 'move/run faster'",
    "Corper Wee": "the camp call-and-response chant (call 'Corper Wee', response 'Waaa')",
    "Waaa": "the response part of the camp chant 'Corper Wee / Waaa'",

    # ---- Posting, PPA & CDS ----
    "Posting Letter": "the letter naming your PPA (also called the PPA Acceptance Letter once you formally accept it)",
    "PPA Acceptance Letter": "the letter that names your PPA and formally confirms you have accepted the posting",
    "Rejection Letter": "issued when a PPA declines to accept a corps member",
    "Redeployment": "a transfer request to serve in a different state",
    "Relocation": "moving your PPA within the same state",
    "HOC": "Head of Corpers -- represents corps members' welfare at a PPA",
    "CDS Card": "the card signed monthly at CDS, used as proof for clearance",
    "CDP": "Community Development Project -- the project your CDS group runs",
    "Exco": "the executive officers of your CDS group",
    "NGO": "Non-Governmental Organisation -- a type of PPA some corps members are posted to",

    # ---- Discipline & clearance ----
    "Clearance": "the monthly sign-off confirming you are actively serving, required to receive your allowance",
    "AWOL": "Absent Without Official Leave -- leaving your PPA/CDS without permission, a clearance/disciplinary offence",
    "Absconding": "leaving your PPA without authorisation (treated the same as AWOL)",
    "Remobilisation": "re-registering after absconding or failing to report to a PPA (distinct from Revalidation, which is after missing camp)",
    "Corps Disciplinary Committee": "the body that rules on corps members' misconduct",
    "State Coordinator's Certification": "the state coordinator's confirmation of completion, required to obtain your discharge certificate",
    "Journey Mercy": "a well-wish for safe travel (to camp or on redeployment)",

    # ---- Camp medical screening ----
    "PCV": "Packed Cell Volume -- a blood test done at camp to check for anaemia",
    "VDRL": "Venereal Disease Research Laboratory test -- a screening blood test done at camp",
    "HCV": "Hepatitis C Virus -- screened for in camp medical tests",
    "CSM": "Cerebrospinal Meningitis -- a disease sometimes screened or vaccinated against",

    # ---- Health insurance ----
    "NHIS": "National Health Insurance Scheme -- former name of Nigeria's health-insurance programme, now NHIA",
    "NHIA": "National Health Insurance Authority -- runs corps members' health insurance, formerly NHIS",

    # ---- NERD (2025/26 requirement) ----
    "NERD": "Nigeria Education Repository and Databank -- 2025/26 requirement to upload and verify your academic project/thesis; no NERD, no NYSC",
    "NDSC": "NERD Digital Service Centre -- an accredited centre that handles NERD registration/upload",

    # ---- Location code override (must precede the FCT institution code) ----
    "FCT": "Federal Capital Territory (Abuja and environs). As a call-up/institution code, FCT instead denotes University of Abuja (UNIABUJA)",
}


# ------------------------------------------------------------
# TERM LOOKUP -- extraction + dict lookup for term_lookup intent.
# Checks GLOSSARY first (general terms), then INSTITUTION_CODES
# (call-up number codes). Longest keys checked first so multi-word
# terms ("Senate List") aren't shadowed by shorter overlapping ones.
# Falls back to fuzzy_match per word/phrase if no exact hit.
# ------------------------------------------------------------
# ------------------------------------------------------------
# TERMS THE KB ALREADY ANSWERS PROPERLY (B9)
# The term pre-layer runs BEFORE classify, so it used to win every time -- and for
# these terms its one-line gloss is strictly worse than the intent's own
# chat_answer. "what is cds" returned "CDS = Community Development Service (your
# weekly community project throughout service)" while the same question phrased as
# "wetin be cds" missed the gate, reached the classifier, and got the real answer.
# So the gate DEFERS on anything listed here: one answering path keeps follow-ups,
# stress openers and the "see the full answer" link working, instead of a second
# path that quietly omits them.
# Terms NOT listed -- slang (Ajuwaya, Otondo, Ghost Corper), exam bodies (WAEC,
# JAMB, UTME), org roles (LGI, LGA, CLO, PV) and places (Mami Market) -- keep the
# gloss, because the KB has nothing better to show for them. PPA is deliberately
# absent too: every PPA intent is procedural (checking, changing, rejection), so
# there is no "what is a PPA" answer to defer to and the gloss IS the right reply.
# Values are the intent deferred to, kept for documentation and for any later change
# that wants to answer it directly; the gate itself only tests membership.
# EVERY entry was checked against the live classifier in both a bare ("cds") and a
# definitional ("what is cds") frame -- a term only belongs here if the classifier
# actually routes it, because a `low` result reaches the rephrase fallback and that is
# far worse than the gloss it replaced. Four candidates failed and deliberately keep
# the gloss: Decampment (low both ways), SOR (low, and misroutes to camp_kit),
# FSLC and Allowee (medium falling to low).
# ------------------------------------------------------------
TERM_KB_INTENT = {
    "CDS":                    "cds_general",
    "SAED":                   "saed_program",
    "Senate List":            "senate_list_status",
    "Green Card":             "green_card_printing",
    "Revalidation":           "revalidation",
    "Exemption Certificate":  "exemption_certificate",
    "Exclusion Letter":       "exclusion_letter_process",
    "Discharge Certificate":  "discharge_certificate",
    "POP":                    "pop_explainer",
    "Corper":                 "nysc_terminology_corper",
    # bare "state code" is high, "what is my state code" is medium -- medium still
    # answers in this engine, and it answers the RIGHT intent, so it stays
    "State Code":             "state_code_meaning",
    # this one legitimately splits by frame: bare "call-up letter" routes to
    # callup_letter_access (how to get it), "what is a call-up letter" to
    # callup_letter_meaning (what it is). Both are real answers; the gloss is neither.
    "Call-Up Letter":         "callup_letter_meaning",
}


def lookup_term(message: str):
    """
    Return {"term": key, "definition": value, "source": "glossary"|"institution_code"|
    "institution_nickname"} for the specific term/code found in `message`, or None if
    nothing matched.
    """
    msg = message.strip()

    TABLES = (
        ("glossary", GLOSSARY),
        ("institution_code", INSTITUTION_CODES),
        ("institution_nickname", INSTITUTION_NICKNAMES),
    )

    # Collect EVERY exact match across all tables, then choose, rather than
    # returning the first table's first hit. First-table-wins meant "NYSC" (a
    # glossary key present in almost every message a user sends this bot)
    # shadowed the term actually being asked about: "what does OAU mean in
    # NYSC?" answered "NYSC = National Youth Service Corps".
    hits = []
    for source_name, table in TABLES:
        for key in table:
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, msg, flags=re.IGNORECASE):
                hits.append((source_name, key))

    if hits:
        # Scheme-level terms are only the answer when nothing more specific matched.
        specific = [h for h in hits if h[1].upper() not in GENERIC_TERMS]
        pool = specific or hits
        # Longest key wins: a longer key is the more specific reading of the
        # same text ("UNILAG" over "LAG", "Otondo" over "NYSC").
        source_name, key = max(pool, key=lambda h: len(h[1]))
        table = dict(TABLES)[source_name]
        return {"term": key, "definition": table[key], "source": source_name}

    # No exact match -- try fuzzy match against each word/short phrase in the message
    words = re.findall(r"[A-Za-z/]+", msg)
    candidates_text = words + [msg]  # also try the whole message as one candidate
    for source_name, table in TABLES:
        for candidate in candidates_text:
            match = fuzzy_match(candidate, table, cutoff=0.75)
            if match:
                return {"term": match, "definition": table[match], "source": source_name}

    return None


# ------------------------------------------------------------
# Is this message a BARE term lookup? -- gate for the deterministic dict
# layer that runs BEFORE the classifier. term_lookup is a dictionary, not a
# trained class (it scores F1 0.00, ~1 example), so the classifier can't route
# to it: a bare "PPA" or "what does LGI mean" would otherwise misclassify and
# fall back. We intercept ONLY when the message is essentially just a known
# specific term -- optionally wrapped in "what is .. / .. meaning / .. in full"
# -- so a procedural question that merely mentions a term ("how do I change my
# PPA?") still goes to the classifier. Scheme-wide generics (NYSC) are left to
# the trained intents that cover them.
# ------------------------------------------------------------
_TERM_QUERY_FILLER = {
    "what", "whats", "what's", "is", "are", "the", "a", "an", "does", "do",
    "did", "mean", "means", "meaning", "of", "stand", "stands", "for", "in",
    "full", "define", "definition", "explain", "tell", "me", "about",
    # Pidgin definitional frames. Without these the gate was English-only, so
    # "wetin be ppa" missed it, reached the classifier, and came back with
    # ppa_change_request -- a procedural answer about changing your PPA, with its
    # own branch menu, to someone who asked what the letters mean. The gate exists
    # precisely because term_lookup is untrainable (F1 0.00, ~1 example), and that
    # applies to Pidgin phrasing as much as English. Terms the KB answers properly
    # are unaffected: TERM_KB_INTENT makes the gate defer on those regardless of
    # which language the question was asked in.
    "wetin", "wettin", "weting", "be", "na", "dey", "abeg", "sabi", "you", "una",
    "meanin", "how", "e", "im", "sef", "ehn", "abi", "so",
}


def looks_like_term_lookup(message: str):
    """
    Return the lookup_term() hit dict when `message` is essentially just a known
    specific term (a bare acronym, or a definitional "what is X" frame), else
    None. Used as a pre-classifier gate so dictionary terms are answered
    deterministically instead of being misrouted by the untrained classifier.
    """
    hit = lookup_term(message)
    if hit is None:
        return None
    # Leave scheme-wide generics (e.g. NYSC) to the trained intents.
    if hit["term"].upper() in GENERIC_TERMS:
        return None
    # Leave anything the KB answers properly to the trained intents too (B9).
    if hit["term"] in TERM_KB_INTENT:
        return None
    # Strip the matched term, then check nothing but definitional filler is left.
    # If real words remain ("change my", "rejected me"), it's a procedural
    # question that merely mentions the term -- let the classifier handle it.
    remainder = re.sub(r"\b" + re.escape(hit["term"]) + r"\b", " ", message, flags=re.IGNORECASE)
    leftover = [w for w in re.findall(r"[a-z0-9']+", remainder.lower()) if w not in _TERM_QUERY_FILLER]
    if leftover:
        return None
    return hit


# ------------------------------------------------------------
# BRANCH-SELECT OPTIONS -- per-intent, extracted from each intent's
# own follow_up_trigger in intent_summary_corrected.csv. Short option
# labels for fuzzy matching, not the full question text (that stays
# in the KB as follow_up_trigger, shown to the user as-is).
# ------------------------------------------------------------
# ------------------------------------------------------------
# SHARED synonym sets -- D6 scheme. Keys are the canonical branch
# identifiers the KB's follow_up_answer is written against (C1);
# synonyms are lowercase, matched as substrings of the (already
# lowered) message. ~6-10 real-reply variants per key, spanning
# standard / Nigerian-English / Pidgin -- not a thesaurus.
# ------------------------------------------------------------
_JUST_ME    = ["just me", "only me", "me alone", "my own", "i'm the only", "na me", "na me only", "only my own"]
_OTHERS_TOO = ["others too", "everyone", "all of us", "we all", "other people", "many of us", "my friends too", "e affect others", "general"]
_YES_DID    = ["yes", "i did", "i have", "already", "done", "i don", "e don happen"]
_NO_DIDNT   = ["no", "i didn't", "not yet", "haven't", "never", "i never"]

BRANCH_SELECT_OPTIONS = {
    "senate_list_status":      {"just_me": _JUST_ME, "others_too": _OTHERS_TOO},
    "callup_number_delay":     {"just_me": _JUST_ME, "whole_batch": _OTHERS_TOO + ["whole batch", "my set", "my batch"]},
    "allowance_payment_issue": {"just_me": _JUST_ME, "others_too": _OTHERS_TOO},

    # batch_stream_timing was a Statement whose single answer tried to serve 37
    # questions at once: the timetable, how assignment works, and how to find your
    # own. Split into three branches so the lead can actually answer the most
    # common question instead of opening with a timing lecture.
    "batch_stream_timing": {
        "timetable":    ["timetable", "time table", "dates", "date", "when is", "when does",
                         "when will", "calendar", "schedule", "starts", "begin", "pop date",
                         "pass out", "batch a", "batch b", "batch c"],
        "how_assigned": ["how assigned", "assigned", "assignment", "how am i", "how are",
                         "decided", "determined", "chosen", "grouped", "selected",
                         "senate list", "why am i", "criteria"],
        "find_mine":    ["find mine", "find my", "check mine", "check my", "know my",
                         "know mine", "my batch", "my stream", "which batch", "which stream",
                         "where do i see", "how do i check"]},

    "name_correction": {
        "spelling_order": ["spelling", "misspelt", "misspelled", "wrong spelling", "arrangement", "order", "rearrange", "swap", "surname first", "wrong order"],
        "add_remove":     ["add a name", "remove a name", "drop a name", "extra name", "missing name", "left out", "include a name"],
        "mismatch":       ["doesn't match", "not the same", "mismatch", "different from", "jamb", "waec", "documents don't match", "vary"]},

    "dob_discrepancy_correction": {
        "jamb_wrong":       ["jamb is wrong", "jamb has", "jamb dob", "jamb date", "utme", "jamb portal"],
        "records_wrong":    ["nysc wrong", "waec wrong", "certificate wrong", "waec date", "nysc portal", "senate list"],
        "nin_bvn_mismatch": ["nin", "bvn", "nin and bvn", "only my nin", "only my bvn", "bank record"]},

    "callup_letter_access": {
        "paid":     ["i paid", "i've paid", "payment made", "after paying", "i don pay", "paid already", "made payment"],
        "not_paid": ["didn't pay", "not paid", "haven't paid", "no payment", "i never pay", "yet to pay", "without paying"]},

    "remobilization_after_abandon": {
        "secretariat_acted": ["they acted", "secretariat did", "they responded", "action taken", "they helped", "resolved", "dem do something"],
        "no_action":         ["no action", "nothing happened", "they didn't", "no response", "ignored", "dem no do anything", "nothing was done"]},

    "green_card_printing": {
        "wont_print":  ["won't print", "not printing", "blank", "can't print", "empty", "no print", "refuse to print", "nothing shows"],
        "wrong_info":  ["wrong info", "wrong details", "wrong name", "wrong photo", "incorrect", "error on it", "wrong information"]},

    "registration_method_at_home": {
        "split_sessions":  ["split", "different sessions", "continue later", "pause", "another device", "log out and", "stop and continue", "over time"],
        "other_questions": ["something else", "different question", "specific platform", "simpleserver", "pay separately", "bank", "another way", "not about that", "site", "address", "where do i pay", "url", "link", "what page"]},

    "medical_fitness_report": {
        "camp_cert":        ["camp", "registration", "fitness certificate", "camp gate", "for camp", "medical fitness"],
        "redeployment_doc": ["redeployment", "relocation", "posting", "health ground", "concessional", "medical report", "change of state"],
        "dispute":          ["fake", "rejected my document", "dismissed", "said it's fake", "dispute", "won't accept", "called it fake"]},

    "jamb_number_issue": {
        "matric":  ["matric", "matriculation", "school number", "matric number"],
        "jamb_no": ["jamb number", "jamb reg", "utme number", "registration number", "jamb"]},

    "stream_assignment": {
        "deployed_skipped": ["deployed but", "didn't go", "posted but", "didn't attend", "skipped", "was deployed", "call up came but"],
        "never_processed":  ["never processed", "not processed", "nothing came", "no call up", "wasn't mobilized", "still waiting"]},

    "prior_registration_history": {
        "already_served":   ["already served", "completed service", "finished nysc", "exempted", "exemption", "excluded", "served before"],
        "mobilized_no_show": ["mobilized but", "never attended", "didn't go to camp", "posted but didn't", "skipped camp", "didn't report"],
        "other_scenarios":  ["something else", "different situation", "another scenario", "neither of those", "other question", "different case", "police", "military", "lab science", "internship"]},

    "graduation_date_correction": {
        "school_submitted": ["school submitted", "school sent", "school corrected", "they submitted", "school uploaded", "already sent"],
        "awaiting_school":  ["waiting on school", "school hasn't", "still waiting", "school delay", "no response from school", "yet to submit"]},

    "portal_account_access": {
        "password":   ["password", "can't login", "forgot password", "reset", "login", "passcode"],
        "email":      ["email", "e-mail", "mail", "wrong email", "change email"],
        "phone":      ["phone number", "phone", "wrong number", "change number", "gsm"],
        "data_error": ["data entry", "wrong details", "error in", "mistake in", "incorrect data", "typo"]},

    "waec_certificate_requirement": {
        "two_waec":  ["two waec", "double waec", "combine waec", "two sittings", "both waec"],
        "waec_neco": ["waec and neco", "waec with neco", "neco", "combine with neco", "waec plus neco"]},

    "biometric_capture": {
        "first_capture": ["first time", "capturing", "new capture", "initial", "haven't captured", "fresh capture"],
        "verify_fail":   ["verification", "not verifying", "failed", "mismatch", "won't verify", "fingerprint fail", "not matching"]},

    "statement_of_result_requirement": {
        "statement_of_result": ["statement of result", "sor", "result statement", "provisional result"],
        "notification_letter": ["notification", "attestation", "notification of result", "attestation letter", "letter"]},

    "portal_open_registration_window": {
        "is_open":    ["is it open", "registration open", "open yet", "still open", "closed", "window open", "when open"],
        "login_issue": ["can't login", "login", "portal not working", "won't load", "access the portal"]},

    "revalidation": {"yes_attended": _YES_DID + ["attended camp", "went to camp"], "no_attended": _NO_DIDNT + ["didn't attend camp", "never went"]},

    "exclusion_letter_process": {
        "collecting":  ["collect", "how to get", "receive my letter", "pick up", "obtain"],
        "contesting":  ["wrongly issued", "shouldn't have gotten", "contest", "dispute", "wrong exclusion", "appeal"]},

    "jamb_regularization": {
        "no_jamb_at_admission": ["no jamb number", "didn't have jamb", "no jamb at admission", "never had a jamb number"],
        "nd_to_hnd":            ["nd to hnd", "part-time", "full-time hnd", "ond to hnd", "part time to full time"]},

    "change_local_government": {
        "approved": ["approved", "it went through", "granted", "accepted", "successful"],
        "rejected": ["rejected", "declined", "denied", "not approved", "refused", "turned down"]},

    "ppa_ngo_service": {
        "specific_ngo": ["specific ngo", "particular ngo", "an ngo i", "this ngo", "named ngo", "i have an ngo"],
        "general":      ["general", "just asking", "in general", "generally", "any ngo", "just curious"]},

    "post_relocation_process": {
        "code_not_updated": ["state code", "ppa not updated", "not updated", "still showing old", "code hasn't changed", "not reflecting"],
        "other":            ["other", "different issue", "something else", "another problem"]},

    "logistics_arrival_timing": {
        "late":  ["late", "arriving late", "after the date", "reporting late", "miss the date", "come late", "behind"],
        "early": ["early", "before", "different date", "ahead", "come early", "earlier", "another day"]},

    "items_laptop_allowed": {
        "during_camp": ["during camp", "in camp", "for camp", "at camp", "camp period"],
        "after_camp":  ["after camp", "at ppa", "at work", "for work", "post camp", "place of work"]},

    "logistics_curfew_leaving": {
        "lights_out":      ["lights out", "curfew", "indoor", "night", "sleep time", "what time", "bedtime"],
        "leaving_grounds": ["leave camp", "go out", "exit camp", "pass out", "go home", "out of camp"]},

    "kit_replacement_lost_items": {
        "nysc_issued": ["nysc gave", "issued", "official", "they gave me", "kit item", "supplied"],
        "personal":    ["i bought", "my own", "personally", "bought myself", "my money", "personal one"]},

    "discharge_certificate": {
        "lost":  ["lost", "misplaced", "destroyed", "damaged", "spoilt", "burnt", "missing", "can't find"],
        "error": ["error", "mistake", "wrong", "incorrect", "wrong name", "wrong date"]},

    "exemption_certificate": {
        "qualifying": ["qualify", "am i eligible", "do i qualify", "over 30", "age", "eligible for exemption", "grounds"],
        "due":        ["already due", "how to collect", "get my exemption", "ready", "collect", "obtain certificate"]},

    "monthly_clearance": {
        "missed_late":    ["missed", "late", "didn't clear", "skipped clearance", "couldn't clear", "sick", "was ill", "i was sick"],
        "not_reflecting": ["not reflecting", "not showing", "absent", "cleared but", "not uploaded", "still showing absent", "not recorded"]},

    "clearance_logistics_general": {
        "process": ["how does", "process", "procedure", "how to clear", "steps", "how do i", "generally"],
        "problem": ["problem", "lost slip", "first corper", "clear elsewhere", "issue", "specific", "trouble"]},

    "clearance_ppa_wont_sign": {
        "resolved":   ["resolved", "sorted", "they signed", "settled", "fixed", "mediation worked", "yes resolved"],
        "unresolved": ["unresolved", "still won't", "not sorted", "refused", "still not signing", "not settled"]},

    "marital_family_accommodation": {
        "pregnant_nursing": ["pregnant", "nursing", "breastfeeding", "expecting", "baby", "with child", "nursing mother"],
        "near_husband":     ["near my husband", "husband's state", "join my husband", "married", "with my spouse", "close to husband", "not pregnant"]},

    "disciplinary_query": {
        "query_received": ["query", "query letter", "queried", "received a query", "given a query", "issued query"],
        "not_attending":  ["not attending", "won't attend", "skip camp", "not going", "avoid camp", "not attend at all"]},

    "allowance_amount": {
        "first_payment": ["first payment", "first allowee", "first alawee", "initial", "first month", "first stipend", "when first"],
        "monthly_cycle": ["monthly", "regular", "every month", "normal", "subsequent", "each month"]},

    "leave_travel_during_service": {
        "abroad":         ["abroad", "outside nigeria", "travel out of the country", "international travel"],
        "within_nigeria": ["within nigeria", "another state", "cross state", "travel within"],
        "wedding_event":  ["wedding", "event", "ceremony", "ceremony i need to attend"],
        "sick_leave":     ["sick", "ill", "illness", "unwell", "hospital", "sick leave", "medical leave"]},

    "posting_influence": {
        "state": ["which state", "state posting", "preferred state", "state of deployment", "get posted to", "state i want"],
        "ppa":   ["which ppa", "organisation", "organization", "specific ppa", "company", "place of assignment"]},

    "ppa_change_request": {
        "location_issue": [
            "far", "distance", "no accommodation", "not safe", "unsafe", "insecurity",
            "too far", "can't commute", "no housing", "i can't go", "it is far from my house",
            "far from my home", "it is distant", "there is no space", "there is no place"],
        "mistreatment": [
            "mistreat", "unofficial payment", "bribe", "abuse", "harassment",
            "asking for money", "extorting", "maltreat", "they're wicked", "they are wicked",
            "they harass", "they don't pay", "they cheat", "they're not good", "they are not good"],
        "prefer_different": [
            "prefer", "don't like", "want a different", "rather work", "not interested in",
            "wrong fit", "different type", "i want somewhere else", "i want another place",
            "it doesn't go with my course", "it doesn't match my course"],
        "different_state": [
            "different state", "another state", "change state", "move state", "relocate"]},

    # --- slot-type entries: NOT synonym-matched. handle_message checks for
    # "__slot__" before defaulting to branch_select (see the Conditional
    # setup block) and routes expected_type accordingly: "state" ->
    # expected_type="state" (against STATES_LIST); any "free_text_*" value
    # -> expected_type="free_text". _fill_slot_and_advance then special-cases
    # these three intents instead of running them through the generic
    # ->/|| branch parser, since their follow_up_answer is empty/unstructured.
    "state_secretariat_location": {"__slot__": "state"},
    "ppa_course_matching":        {"__slot__": "free_text_course"},
    # ppa_change_request removed from __slot__ -- it's a real branch_select
    # entry now (see above), since _fill_slot_and_advance had no free-text
    # special case for it and was falling through to dumping the raw,
    # unparsed follow_up_answer string on every reply.
}


# ------------------------------------------------------------
# STATE SECRETARIAT ADDRESSES -- per-state lookup for
# state_secretariat_location once the "state" slot is filled.
# Extracted from the KB's own answer text (nysc.gov.ng/secretariat.html),
# kept here as structured data so _fill_slot_and_advance can return just
# the one state's address instead of the full 37-entry dump. Keys match
# STATES_LIST exactly.
# ------------------------------------------------------------
STATE_SECRETARIAT_ADDRESSES = {
    "Abia": "St. Finbarr's Rd, PMB 7225, Umuahia",
    "Adamawa": "PMB 2252, Jimeta-Yola",
    "Akwa Ibom": "PMB 1087, Uyo",
    "Anambra": "12 Okpora St, PMB 4042, Amawbia, Awka",
    "Bauchi": "Turaki Abdu Rd, Fadamar Mada, PMB 85",
    "Bayelsa": "Block 7, Flat 1-4, Phase II, Civil Service/FRSC Rd, Yenagoa",
    "Benue": "Railway Bye-pass, PMB 2358, Makurdi",
    "Borno": "Kashim Ibrahim Rd, PMB 1124, Maiduguri",
    "Cross River": "KM5, Murtala Muhammed Way, Ikot Ansa, Calabar",
    "Delta": "Federal Secretariat, PMB 5004, Asaba",
    "Ebonyi": "17 Nkwerre St, GRA, Abakaliki",
    "Edo": "2 Red Cross Rd off Ikpokpan Rd, GRA, Benin City",
    "Ekiti": "KM2 Iyin Rd, PMB 5302, Ado-Ekiti",
    "Enugu": "2 Abakaliki Rd, GRA, PMB 1293, Enugu",
    "Gombe": "F.M.C/Ashaka Rd, PMB 036, Gombe",
    "Imo": "Mbano St, Aladinma Housing Estate, Owerri",
    "Jigawa": "Kigawa Rd, PMB 7049, Dutse",
    "Kaduna": "Unguwa Rimi, PMB 2201, Kaduna",
    "Kano": "Gwarzo Rd, PMB 3137, Kano",
    "Katsina": "Federal Secretariat Complex, PMB 2034, Katsina",
    "Kebbi": "4 Patrick Aziza Rd, PMB 1043, Birnin Kebbi",
    "Kogi": "Lokoja-Okene Rd, Lokongoma Phase 1, PMB 1046",
    "Kwara": "Ahmadu Bello Way, PMB 1512, Ilorin",
    "Lagos": "Old Census Office, Babs Animashaun St, Surulere",
    "Nasarawa": "26 Makurdi Rd, PMB 31, Lafia",
    "Niger": "Bosso Rd, PMB 83, Minna",
    "Ogun": "Mini Secretariat, Oke-Ilewo, Abeokuta",
    "Ondo": "Federal Govt Secretariat, PMB 718, Akure",
    "Osun": "New Ikirun Rd, PMB 4370, Oshogbo",
    "Oyo": "Mech. Drive, PMB 5500, Ibadan",
    "Plateau": "Old Miango Rd, PMB 2258, Jos",
    "Rivers": "40 Ikwerre Rd, Mile One, PMB 5210, Port Harcourt",
    "Sokoto": "Birnin Kebbi Rd, Sokoto",
    "Taraba": "118 Hammaruwa Way, PMB 1058, Jalingo",
    "Yobe": "Phase 1, PMB 1026, Damaturu",
    "Zamfara": "Sokoto Rd, Gada Biyu, PMB 1026, Gusau",
    "FCT": ("No. 6 Lasale St, off Shehu Shagari Way, Maitama, beside CBN "
            "Training Centre, Abuja. Note: this is the State/Zonal "
            "Secretariat for FCT corps members' own affairs -- the "
            "National Head Office (for escalations/national queries) is "
            "at a separate address, don't confuse the two."),
}


# ------------------------------------------------------------
# COURSE BUCKET REPLIES -- per-bucket PPA-tendency text for
# ppa_course_matching, keyed to COURSE_BUCKET_MAP's bucket names. Filled
# in once the user names their course; COURSE_BUCKET_MAP resolves the
# course to a bucket, this dict supplies the bucket's tendency text.
# Every reply keeps the KB's core caveat (course influences but doesn't
# guarantee outcome; 70%+ of ALL corps members end up in education
# regardless of field) so no bucket overstates certainty.
# ------------------------------------------------------------
COURSE_BUCKET_REPLIES = {
    "Engineering": (
        "Engineering grads often land technical/infrastructure PPAs -- "
        "construction, oil & gas, telecoms, manufacturing -- when one's "
        "available locally. But education postings are common too: "
        "engineering corps members regularly end up teaching Mathematics "
        "or Basic Science because of the nationwide teacher shortage."
    ),
    "Medical/Health Sciences": (
        "Medical/health-science courses (medicine, nursing, pharmacy, "
        "physiotherapy, etc.) are among the most reliably matched fields -- "
        "hospitals, health centres, and health-focused NGOs need this "
        "training directly, so a field-matched posting is fairly likely."
    ),
    "Education": (
        "Education courses are the most directly matched field there is -- "
        "schools are the default PPA type, and over 70% of ALL corps "
        "members (not just education grads) end up teaching regardless of "
        "their course, so this is about as close to a guaranteed match as "
        "it gets."
    ),
    "Sciences": (
        "Pure-science courses (biology, chemistry, physics, biochemistry, "
        "microbiology, maths, statistics, etc.) commonly end up posted to "
        "schools as subject teachers, driven by the teacher shortage. "
        "Lab/research-oriented PPAs exist but are less common than a "
        "teaching posting."
    ),
    "ICT/Computing": (
        "ICT/computing courses have a decent shot at tech-aligned PPAs -- "
        "banks, telecoms, tech firms, or an MDA's IT unit -- where one's "
        "available. In more rural postings, though, it's common to default "
        "to teaching computer studies or another subject."
    ),
    "Agriculture": (
        "Agriculture-related courses commonly go to agricultural extension "
        "offices, ADPs (Agricultural Development Programmes), or farms "
        "when one's available in the area, but plenty still end up in "
        "schools given the nationwide shortage."
    ),
    "Law": (
        "Law graduates are commonly posted to courts, law firms, "
        "ministries of justice, or legal aid organisations -- one of the "
        "more consistently field-matched courses."
    ),
    "Social Sciences/Management": (
        "Social-science/management courses (economics, accounting, "
        "business admin, mass comm, and similar) frequently go to banks, "
        "government ministries/parastatals, or corporate PPAs -- among "
        "the more consistently matched fields, though schools remain a "
        "common fallback."
    ),
    "Arts/Humanities": (
        "Arts/humanities courses (English, history, linguistics, and "
        "similar) are very commonly posted to schools as subject "
        "teachers -- one of the fields most affected by the nationwide "
        "teacher shortage."
    ),
    "Environmental/Built Environment": (
        "Architecture, estate management, urban planning, and similar "
        "courses often go to ministries of works/housing, planning "
        "authorities, or construction firms when available, though "
        "school postings still happen here too."
    ),
}


# ------------------------------------------------------------
# COMPOUND SUB-SLOTS -- for the 5 intents whose follow_up_trigger
# genuinely asks TWO things in one question. A flat entry in
# BRANCH_SELECT_OPTIONS can't capture both, so these get their own
# structure: a list of sub-slots, each independently checked against
# the user's message. If only some are filled, dialogue_manager.py
# asks specifically for what's missing rather than closing the
# question on a partial answer.
# ------------------------------------------------------------
# NOTE (C2): redeployment_general and relocation_documents_grounds were
# merged into relocation_general_process this pass (D2-01/D2-02) -- their
# entries are removed, not just left stale. relocation_general_process is
# rebuilt below to the survivor's ground x stage design (D2-01), replacing
# the old stage x reason design. Dropping the free_text `reason` sub-slot
# also fixes the CC-01-flagged greediness bug: a free_text slot matches
# ANY message and would have swallowed a reply meant for the other slot.
COMPOUND_SLOTS = {
    "relocation_general_process": [
        {"name": "ground", "expected_type": "branch_select",
         "options": {
             "health":   ["health", "sick", "illness", "medical", "ill", "not well", "hospital", "health ground"],
             "marital":  ["marriage", "married", "wedding", "spouse", "husband", "wife", "just married", "marital"],
             "security": ["security", "insecurity", "unsafe", "danger", "kidnap", "attack", "not safe", "crisis"]},
         "ask": "Which ground are you applying on, health, marital or security? Tell me which one "
                "and I'll give you what that route needs."},
        {"name": "stage", "expected_type": "branch_select",
         "options": {
             "in_camp":    ["in camp", "still in camp", "at camp", "during camp", "orientation camp"],
             "after_camp": ["after camp", "at ppa", "already posted", "at work", "left camp", "passed out"],
             "cancel":     ["cancel", "stop it", "withdraw", "reverse", "undo", "already applied", "cancel relocation"]},
         "ask": "And where are you in the process right now: still in camp, already at your PPA, "
                "or trying to cancel a relocation you already applied for?"},
    ],
    "foreign_graduate_verification": [
        {"name": "registered", "expected_type": "yes_no",
         "ask": "Have you completed your online registration yet?"},
        {"name": "docs_in_hand", "expected_type": "yes_no",
         "ask": "Do you have your original certificate, transcript, and Ministry Evaluation Letter in hand?"},
    ],
    "logistics_travel_to_camp": [
        {"name": "state", "expected_type": "state",
         "ask": "Which state's camp are you trying to reach?"},
        {"name": "info_type", "expected_type": "branch_select",
         "options": {
             "address":   ["address", "location", "where", "directions", "find it", "how to locate"],
             "transport": ["transport", "fare", "how to get there", "road", "bus", "how much", "which route"]},
         "ask": "Do you need the camp address, or how to get there and what the fare runs?"},
    ],
}


# ------------------------------------------------------------
# COURSE -> BROAD-FIELD BUCKET
# Verified against NUC-accredited programs, AFIT, Nile University
# course lists. See course_bucket_reference.py for full sourcing notes.
# ------------------------------------------------------------
COURSE_BUCKET_MAP = {
    "mechanical engineering": "Engineering", "electrical engineering": "Engineering",
    "electrical and electronics engineering": "Engineering", "civil engineering": "Engineering",
    "chemical engineering": "Engineering", "petroleum engineering": "Engineering",
    "petroleum and gas engineering": "Engineering", "mechatronics engineering": "Engineering",
    "aerospace engineering": "Engineering", "agricultural engineering": "Engineering",
    "metallurgical engineering": "Engineering", "metallurgical and materials engineering": "Engineering",
    "systems engineering": "Engineering", "industrial engineering": "Engineering",
    "computer engineering": "Engineering", "biomedical engineering": "Engineering",
    "telecommunication engineering": "Engineering", "automotive engineering": "Engineering",
    "nuclear engineering": "Engineering", "geomatics": "Engineering",

    "medicine": "Medical/Health Sciences", "mbbs": "Medical/Health Sciences",
    "nursing": "Medical/Health Sciences", "pharmacy": "Medical/Health Sciences",
    "physiotherapy": "Medical/Health Sciences", "medical laboratory science": "Medical/Health Sciences",
    "dentistry": "Medical/Health Sciences", "public health": "Medical/Health Sciences",
    "radiography": "Medical/Health Sciences", "optometry": "Medical/Health Sciences",
    "nutrition and dietetics": "Medical/Health Sciences",

    "education": "Education", "b.ed": "Education", "science education": "Education",
    "vocational education": "Education", "guidance and counselling": "Education",

    "biology": "Sciences", "chemistry": "Sciences", "physics": "Sciences",
    "geology": "Sciences", "biochemistry": "Sciences", "microbiology": "Sciences",
    "mathematics": "Sciences", "statistics": "Sciences", "zoology": "Sciences",
    "botany": "Sciences", "industrial chemistry": "Sciences",
    "human kinetics": "Sciences", "parasitology and entomology": "Sciences",
    "water sanitation and hygiene": "Sciences",

    "computer science": "ICT/Computing", "software engineering": "ICT/Computing",
    "information technology": "ICT/Computing", "cyber security": "ICT/Computing",
    "data science": "ICT/Computing", "information systems": "ICT/Computing",
    "artificial intelligence": "ICT/Computing", "telecommunication science": "ICT/Computing",

    "agriculture": "Agriculture", "agricultural economics": "Agriculture",
    "animal science": "Agriculture", "crop science": "Agriculture",
    "forestry": "Agriculture", "fisheries": "Agriculture", "soil science": "Agriculture",

    "law": "Law", "llb": "Law",

    "economics": "Social Sciences/Management", "accounting": "Social Sciences/Management",
    "business administration": "Social Sciences/Management", "banking and finance": "Social Sciences/Management",
    "mass communication": "Social Sciences/Management", "political science": "Social Sciences/Management",
    "public administration": "Social Sciences/Management", "sociology": "Social Sciences/Management",
    "psychology": "Social Sciences/Management", "international relations": "Social Sciences/Management",
    "marketing": "Social Sciences/Management", "insurance": "Social Sciences/Management",
    "islamic economics and finance": "Social Sciences/Management",
    "intelligence and security studies": "Social Sciences/Management",

    "english": "Arts/Humanities", "history": "Arts/Humanities", "linguistics": "Arts/Humanities",
    "philosophy": "Arts/Humanities", "theatre arts": "Arts/Humanities", "fine arts": "Arts/Humanities",
    "religious studies": "Arts/Humanities", "french": "Arts/Humanities", "music": "Arts/Humanities",

    "architecture": "Environmental/Built Environment", "estate management": "Environmental/Built Environment",
    "urban and regional planning": "Environmental/Built Environment", "building": "Environmental/Built Environment",
    "quantity surveying": "Environmental/Built Environment", "surveying and geoinformatics": "Environmental/Built Environment",
    "environmental management": "Environmental/Built Environment",
}


# ============================================================
# DECISION LOGIC (formerly dialogue_manager.py's own content)
# ============================================================

class ConversationState:
    def __init__(self):
        self.active_intent = None
        self.pending_question = None   # {"text": str, "expected_type": str, "options": [...]}
        self.pending_reminded = False  # has the open follow-up been re-surfaced once after a greeting? (step 2.5)
        self.compound_fills = None     # {sub_slot_name: value} while filling a COMPOUND_SLOTS intent
        self.stack = []                # pushed pending questions (interrupted topics)
        self.consecutive_low_confidence = 0  # tracks repeated low-confidence hits,
                                              # so a 2nd unrecognized message in a row
                                              # escalates to a firm out_of_scope reply
                                              # instead of asking "rephrase?" forever
        # Which intent actually produced the last answer. Distinct from active_intent,
        # which only tracks an intent with an OPEN follow-up. The front end needs this
        # to offer "see the full answer", since Chat now serves the short chat_answer
        # and the prose lives in Browse.
        self.last_answered_intent = None

    def clear(self):
        self.active_intent = None
        self.pending_question = None
        self.pending_reminded = False
        self.compound_fills = None
        self.stack = []
        self.consecutive_low_confidence = 0
        # Must be cleared too: it is what the front end shows as "still on X" and what
        # gates the "see the full answer" link. Leaving it set made a reset conversation
        # keep announcing the previous topic.
        self.last_answered_intent = None

    def drop_pending(self):
        # A dismissal ("never mind", "no worry, i've gotten that") gets the user
        # OUT of an open follow-up: clear the pending question, the interrupted
        # stack and any compound fills, but leave the rest of the conversation.
        # Distinct from clear(), which also wipes the low-confidence counter and
        # last_answered_intent.
        self.active_intent = None
        self.pending_question = None
        self.pending_reminded = False
        self.compound_fills = None
        self.stack = []

    def push_pending(self):
        if self.pending_question:
            self.stack.append((self.active_intent, self.pending_question, self.compound_fills))

    def pop_pending(self):
        if self.stack:
            self.active_intent, self.pending_question, self.compound_fills = self.stack.pop()
            return True
        self.active_intent, self.pending_question, self.compound_fills = None, None, None
        return False

    def set_pending(self, intent, question_text, expected_type, options=None):
        self.active_intent = intent
        self.pending_reminded = False   # a fresh follow-up hasn't been nudged yet
        self.compound_fills = None
        self.pending_question = {
            "text": question_text,
            "expected_type": expected_type,
            "options": options or [],
        }

    def set_pending_compound(self, intent):
        self.active_intent = intent
        self.pending_reminded = False   # a fresh follow-up hasn't been nudged yet
        self.compound_fills = {}
        # Ask the FIRST SUB-SLOT'S OWN QUESTION, not the KB's follow_up_trigger.
        #
        # This used to pass the trigger through, on the reasoning that it is the row's own
        # wording. The trigger asks for BOTH slots at once ("Which ground applies, health,
        # marital, or security, and are you still in camp, already at your PPA, or
        # cancelling?") while only the first sub-slot's choices can be rendered, so a user
        # answered one half, and then the second sub-slot's ask fired and asked the other half
        # AGAIN as a fresh question. Two defects from one line: an impractical flow, and the
        # same question asked twice. The sub-slot asks were always written for this sequence,
        # which is why the second one opens with "And where are you in the process right now" --
        # it was written to follow a single-slot question, not a two-slot one.
        #
        # Nothing downstream breaks, verified rather than assumed: koppal_api tags the last
        # bubble `ask` by comparing it to state.pending_question["text"], not to the KB field,
        # and both sides of that comparison come from here. Answering both slots in one message
        # still works, because _check_compound_slots tries every unfilled sub-slot either way.
        _apply_compound_sub_slot(self, COMPOUND_SLOTS[intent][0])


CORRECTION_INTERJECTIONS = ["wait", "scratch that", "actually", "no", "sorry", "forget that", "hold on"]
CORRECTION_VERBS = ["i meant", "let me correct that", "i mean"]
_ALL_CORRECTION_WORDS = set(CORRECTION_INTERJECTIONS) | set(CORRECTION_VERBS)

# Mid-sentence scan uses a NARROWER verb set than the start-of-message check.
# "i mean" is deliberately excluded here -- it's extremely common as pure
# filler mid-sentence ("I mean, this whole process is confusing"), not a
# correction. "i meant" (past tense) and "let me correct that" are rare
# enough outside actual corrections that scanning for them anywhere in the
# message is safe.
MID_SENTENCE_CORRECTION_VERBS = ["i meant", "let me correct that"]

# Fallback/confusion reply pools -- if handle_message's real answer came from
# one of these, it means the correction didn't actually resolve to anything,
# so we must NOT prepend "Got it -- ", that would sound like the bot
# understood and then immediately contradicted itself.
_UNRESOLVED_REPLY_POOLS = (
    chitchat.CHITCHAT_REPLIES.get("confusion_from_user", []),
    chitchat.FALLBACK_PENDING if hasattr(chitchat, "FALLBACK_PENDING") else [],
    chitchat.NOISE_FALLBACK if hasattr(chitchat, "NOISE_FALLBACK") else [],
    chitchat.CHITCHAT_REPLIES.get("out_of_scope", []),
)


def strip_correction_prefix(message: str):
    """
    Detect self-correction language ("wait, I meant...", "scratch that...",
    or mid-sentence "so I registered late, wait actually I meant on time")
    and strip it, leaving only the real content.

    Two stages, deliberately asymmetric:
    1. Strip leading interjections (stackable: "wait, actually, no, ...").
       This is noise-cleanup ONLY -- an interjection alone is NEVER
       sufficient evidence of a correction, since "no" and "actually" are
       extremely common as ordinary sentence openers too ("no, I haven't
       registered yet" is ordinary content, not a correction, and must
       not be stripped).
    2. Require an explicit correction VERB ("i meant" / "let me correct
       that") to actually confirm it's a correction, searched anywhere in
       what's left after interjection-stripping, taking the LAST
       occurrence so "I meant X, wait no I meant Y" correctly keeps Y.
       "i mean" (present tense) is deliberately excluded -- it's common
       filler ("I mean, this whole process is confusing"), not a
       correction, and including it produces false positives.
    Only returns was_correction=True when a verb was actually found.
    """
    original = message.strip()
    msg = original
    changed = True
    while changed:
        changed = False
        msg_lower = msg.lower()
        for interj in sorted(CORRECTION_INTERJECTIONS, key=len, reverse=True):
            if msg_lower.startswith(interj):
                remainder = msg[len(interj):].lstrip(",").strip()
                if remainder:
                    msg = remainder
                    changed = True
                break

    msg_lower = msg.lower()
    best_pos, best_verb = -1, None
    for verb in MID_SENTENCE_CORRECTION_VERBS:
        pos = msg_lower.rfind(verb)
        if pos > best_pos:
            best_pos, best_verb = pos, verb
    if best_pos != -1:
        remainder = msg[best_pos + len(best_verb):].lstrip(",").strip()
        if remainder and remainder.lower() not in _ALL_CORRECTION_WORDS:
            return True, remainder
    return False, original


def branch_label(key: str) -> str:
    """`stage:after_camp` -> `after camp`. Canonical branch keys are scaffolding: the slot
    prefix and the underscores are ours, not the user's, so nothing user-facing may show them.
    """
    return key.split(":")[-1].replace("_", " ")


def _resolve_tagged_choice(choice, state, kb_lookup_fn):
    """B10 -- resolve a CLICK rather than the text it would have typed.

    A chip used to send its bare canonical key as a message. That works only while the menu is
    open: once the follow-up resolved there was nothing to match it against, so `different state`
    went to the classifier, which has no idea what two words of branch label mean -- and answered
    with a fallback, or worse, with whatever those words happened to classify to. A click carries
    the menu it came from (the owning intent) plus its key, so the engine can answer it directly
    however long ago the menu closed. An intentional re-pick works; a stale click is harmless.

    Returns the branch text, or None when the tag doesn't name a real branch -- in which case the
    caller carries on as if the tag had never been sent.
    """
    intent = (choice or {}).get("intent")
    key = (choice or {}).get("key")
    if not intent or not key:
        return None
    row = kb_lookup_fn(intent)
    if not row:
        return None
    text = _parse_branches(row.get("follow_up_answer", "") or "").get(key)
    if not text:
        return None
    state.consecutive_low_confidence = 0
    state.last_answered_intent = intent
    return text.strip()


def handle_message(message: str, state: ConversationState, classify_fn, kb_lookup_fn,
                   choice=None, seed_lookup_fn=None, seed_direct_fn=None):
    """
    Public entry point. Strips a leading self-correction phrase (if any),
    then runs the real pipeline on the cleaned message, then prepends a
    short acknowledgment ONLY if the reply was a genuine answer, never on
    a fallback/confusion reply (that would read as the bot contradicting
    itself: "Got it -- can you rephrase that?").

    `choice` is the optional click tag {"intent": ..., "key": ...} described in
    _resolve_tagged_choice. Text-only callers (the CLI) never pass it.

    `seed_lookup_fn(message, intent) -> str or None` is the optional per-question answer
    lookup (koppal_seeds.py), injected the same way the classifier is so the engine never
    learns what a seed is. Omit it and behaviour is identical to before Phase 3.
    """
    was_correction, cleaned_message = strip_correction_prefix(message)
    reply = _handle_message_inner(cleaned_message, state, classify_fn, kb_lookup_fn, choice,
                                  seed_lookup_fn, seed_direct_fn)
    if was_correction and not any(reply in pool for pool in _UNRESOLVED_REPLY_POOLS):
        reply = f"Got it -- {reply}"
    return reply


def _handle_message_inner(message: str, state: ConversationState, classify_fn, kb_lookup_fn,
                          choice=None, seed_lookup_fn=None, seed_direct_fn=None):
    """
    classify_fn(message) -> (intent, confidence)   -- from nlu.py
    kb_lookup_fn(intent) -> KB row dict             -- from knowledge_base.csv
    choice                                          -- optional click tag, see handle_message
    seed_lookup_fn(message, intent) -> str or None   -- optional, from koppal_seeds.py
    seed_direct_fn(message) -> (intent, answer) or None -- optional, pre-classification match

    Returns a reply string. Mutates `state` in place.
    """

    # --- Step 0: start_over always checked first ---
    intent, confidence = classify_fn(message)
    if intent == "start_over" and confidence == "high":
        state.clear()
        return random.choice(chitchat.CHITCHAT_REPLIES["greeting"])

    # --- Step 0.5: dismissal of an open follow-up ("never mind", "no worry,
    # i have gotten that", "okay"). Checked before the pending-slot logic so a
    # dismissal always gets the user OUT, instead of being read as a slot answer
    # or dead-ending in noise/low-confidence with the chips still up. Broad set
    # (owner's call): plain acknowledgements count too. With nothing pending it
    # is just a friendly acknowledgement. ---
    if chitchat.is_dismissal(message):
        state.consecutive_low_confidence = 0
        state.last_answered_intent = None
        state.drop_pending()
        return random.choice(chitchat.DISMISSAL_ACK)

    # --- Step 0.75: a tagged click (B10). Only when the click did NOT come from the menu
    # that is open right now -- a live menu must keep running through Step 1, or a compound
    # intent would answer its first slot and silently skip the second. So this handles exactly
    # the broken cases: a re-pick after the menu resolved, and a stale click from an earlier
    # topic while a different follow-up is open. ---
    if choice and not (state.pending_question and state.active_intent == choice.get("intent")):
        tagged = _resolve_tagged_choice(choice, state, kb_lookup_fn)
        if tagged is not None:
            return tagged

    # --- Step 1: is there a pending question? Check it on EVERY message,
    # even if a value was already given -- this is what makes correction free.
    if state.pending_question:
        expected = state.pending_question["expected_type"]

        if expected == "compound":
            reply = _check_compound_slots(message, state, kb_lookup_fn)
            if reply is not None:
                return reply
            # nothing matched at all, falls through to step 3

        else:
            matched_value = _check_pending_slot(message, expected, state.pending_question["options"])

            if matched_value is not None:
                state.consecutive_low_confidence = 0
                return _fill_slot_and_advance(state, matched_value, kb_lookup_fn)

            # --- Step 2: no clean match -- try fuzzy match, single confirm ---
            fuzzy_result = _fuzzy_check_pending(message, expected, state.pending_question["options"])
            if fuzzy_result is not None:
                state.consecutive_low_confidence = 0
                # the confirm question is user-facing, so it shows the LABEL. It used to
                # interpolate the canonical key, which read back "Do you mean location_issue?"
                # -- the same internal-key leak B1/B2 removed from the compound path.
                return random.choice(chitchat.CONFIRM_MATCH).format(
                    match=branch_label(fuzzy_result))
            # falls through to step 3, pending question stays intact

    # --- Step 2.5: chitchat keyword pre-layer. Reached only when no pending
    # slot claimed this message (placement A -- pending slot wins). Formulaic
    # small talk is answered here, before the classifier, so it never competes
    # as an extra class. Re-show the pending question if one is still open.
    category = chitchat.detect_chitchat(message)
    if category is not None:
        state.consecutive_low_confidence = 0
        state.last_answered_intent = None   # chitchat answers nothing: no topic, no "more" link
        reply = chitchat.get_reply(category)
        if state.pending_question:
            # Re-surface the open follow-up, but only ONCE and worded as a natural
            # line -- not the raw question pasted onto every greeting (owner's call).
            # A second greeting just greets; the chips stay up either way.
            if not state.pending_reminded:
                reply += " " + random.choice(chitchat.PENDING_NUDGE).format(
                    pending_question=state.pending_question["text"])
                state.pending_reminded = True
        return reply

    # --- Step 2.75: term-lookup pre-layer. term_lookup is a dictionary, not a
    # trained class, so a bare "PPA" / "what does LGI mean" can't be routed by
    # the classifier -- answer it deterministically here, before classify.
    # Gated by looks_like_term_lookup, so "how do I change my PPA?" (a real
    # question that merely contains a term) still falls through to the
    # classifier below. Reached only when no pending slot claimed the message.
    term_hit = looks_like_term_lookup(message)
    if term_hit is not None:
        state.consecutive_low_confidence = 0
        # A term definition is self-contained -- there is no "more" worth showing
        # (term_lookup's KB "answer" is the whole raw glossary). None means the API
        # attaches no "see the full answer" link to this reply.
        state.last_answered_intent = None
        return f"{term_hit['term']} = {term_hit['definition']}"

    # --- Step 2.8: a near-exact per-question match OVERRIDES the classifier, it does not
    # short-circuit it. Same shape as the term-lookup pre-layer above: when the message
    # essentially IS a known question, an intent decision adds nothing, and waiting for one means
    # a question the classifier happens to be unsure about gets offered back as a guess instead of
    # answered. The floor for this is higher than the post-classification one, because here there
    # is no agreeing intent behind it.
    #
    # Overriding rather than returning matters. An earlier version returned the answer here, which
    # skipped the Conditional handling below, so no pending slot was set and a user who had just
    # said "because of security" was asked which ground applied on their very next message.
    # Reached only when no pending slot claimed the message, same as the term pre-layer. ---
    seeded, direct_hit = None, None
    if seed_direct_fn is not None:
        direct_hit = seed_direct_fn(message)

    if direct_hit is not None:
        intent, confidence = direct_hit[0], "high"
        seeded = (direct_hit[1], direct_hit[2])
    else:
        # --- Step 3: classify normally ---
        intent, confidence = classify_fn(message)

    if intent == "out_of_scope":
        state.consecutive_low_confidence = 0
        state.last_answered_intent = None
        return random.choice(chitchat.CHITCHAT_REPLIES.get("out_of_scope", ["I can't help with that."]))

    if intent == "noise":
        state.consecutive_low_confidence = 0
        state.last_answered_intent = None
        return random.choice(chitchat.NOISE_FALLBACK)

    if confidence == "low":
        # 2nd consecutive unrecognized message escalates to a firm out_of_scope
        # reply instead of asking "can you rephrase?" indefinitely. This is the
        # REAL fallback net -- it works on genuinely novel off-topic questions
        # the classifier never saw in training, unlike relying on out_of_scope
        # itself being predicted, which only covers phrasings close to its
        # (necessarily incomplete) training examples.
        state.consecutive_low_confidence += 1
        state.last_answered_intent = None
        if state.consecutive_low_confidence >= 2:
            state.consecutive_low_confidence = 0
            return random.choice(chitchat.CHITCHAT_REPLIES.get("out_of_scope", ["I can't help with that."]))
        if state.pending_question:
            return random.choice(chitchat.FALLBACK_PENDING).format(pending_question=state.pending_question["text"])
        return random.choice(chitchat.CHITCHAT_REPLIES.get("confusion_from_user", ["Can you rephrase that?"]))

    # high confidence from here
    state.consecutive_low_confidence = 0
    kb_row = kb_lookup_fn(intent)
    if kb_row is None:
        # Safety net: chitchat is caught by the pre-layer (step 2.5), and
        # out_of_scope / noise are handled above, so a high-confidence intent
        # should always have a KB row. If one somehow doesn't, fall back
        # cleanly rather than crash.
        state.last_answered_intent = None
        return random.choice(chitchat.CHITCHAT_REPLIES.get("out_of_scope", ["I can't help with that."]))

    # term_lookup is a dict lookup, not a self-contained block answer --
    # extract the specific term/code asked about instead of returning
    # the entire glossary + institution-code dump from the KB row.
    if intent == "term_lookup":
        match = lookup_term(message)
        if match is not None:
            answer = f"{match['term']} = {match['definition']}"
        else:
            answer = ("I've got definitions for NYSC terms and institution codes -- "
                      "which one did you want explained?")
    else:
        # Step 1 of _chat_body's resolution order, injected the same way classify_fn and
        # kb_lookup_fn are: a per-question answer for the specific question asked, or None.
        # None is the normal outcome and means "no seed was close enough", so the reply falls
        # through to chat_answer exactly as it did before Phase 3. The engine stays unaware of
        # seeds, similarity or floors; koppal_seeds.py owns all of that.
        if seeded is None and seed_lookup_fn is not None:
            seeded = seed_lookup_fn(message, intent)
        answer = seeded[0] if seeded else _chat_body(kb_row)
    seed_terminal = bool(seeded and seeded[1])
    state.last_answered_intent = intent
    if intent in chitchat.STRESS_FLAGGED_INTENTS:
        answer = random.choice(chitchat.EMPATHETIC_OPENERS) + " " + answer

    # A TERMINAL seed answers and stops. "No, that is not a ground" must not be followed by
    # "which ground applies, and what stage are you at", and the follow-up is the worse
    # non-sequitur of the two. Every other seed keeps its follow-up, because the follow-up is what
    # holds the pending slot: drop it and the ground the user just named is gone by the next turn.
    if kb_row.get("answer_type", "").lower() == "conditional" and not seed_terminal:
        # Skip the follow-up entirely when the user's own words already single out one
        # branch. "When is Batch C?" names the timetable branch, so asking "which do you
        # need: the timetable, how you got assigned, or how to find yours?" is a pointless
        # extra turn. Only attempted when nothing else is already pending, so the
        # interrupted-topic stack is never disturbed.
        if not state.pending_question and intent not in COMPOUND_SLOTS:
            prematched = _prematch_branch(message, BRANCH_SELECT_OPTIONS.get(intent, {}))
            if prematched:
                branch_text = _parse_branches(
                    kb_row.get("follow_up_answer", "")).get(prematched)
                if branch_text:
                    parts = [(answer or "").strip(), branch_text.strip()]
                    return "\n\n".join(p for p in parts if p)

        # The stack is for a DIFFERENT topic cutting in. Re-asking the intent that is already
        # in progress must not stack it behind itself: with `ground` still open, "relocatte"
        # again pushed relocation's own sub-slot, and resolving the fresh fill popped it back
        # as "Back to your earlier question: Which ground -- health, marital, or security?" --
        # a question the user had just answered. Same intent = restart the flow, not interrupt.
        if state.pending_question and state.active_intent != intent:
            state.push_pending()
        if intent in COMPOUND_SLOTS:
            state.set_pending_compound(intent)
            # The user's opening message often already answers part of it: "I want to
            # relocate on health grounds, still in camp". Asking "which ground, and what
            # stage?" after that is the same pointless extra turn _prematch_branch exists
            # to avoid for flat Conditionals. Compound intents were excluded from that
            # path, so they never got the equivalent.
            #
            # fuzzy=False is essential here, and _prematch_branch has the same rule. The
            # opening message is the QUESTION, not an answer, and questions look like branch
            # synonyms: "can I relocate" fuzzy-matches the `cancel` synonym "cancel
            # relocation" closely enough to silently fill the stage slot with `cancel`.
            filled = _check_compound_slots(message, state, kb_lookup_fn, fuzzy=False)
            if filled is not None:
                body = (answer or "").strip()
                return f"{body}\n\n{filled}" if body else filled
        else:
            options = BRANCH_SELECT_OPTIONS.get(intent, {})
            # Post-C3: every BRANCH_SELECT_OPTIONS entry is a
            # {canonical_key: [synonyms]} dict (D6) UNLESS it's one of the
            # three "__slot__" placeholder entries -- those aren't
            # branch_select at all, they're a single open slot (a state
            # name or free text). Check for that marker first; true yes_no
            # Conditionals still aren't routed through BRANCH_SELECT_OPTIONS
            # at all (they don't appear in this dict; see D6's note on
            # yes_no vs. yes/no-ish branch_select branches like `revalidation`).
            if "__slot__" in options:
                slot_kind = options["__slot__"]
                if slot_kind == "state":
                    expected_type = "state"
                    slot_options = STATES_LIST
                else:  # "free_text_course", "free_text_reason", or any future free_text_*
                    expected_type = "free_text"
                    slot_options = []
            else:
                expected_type = "branch_select"
                slot_options = options
            state.set_pending(intent, kb_row["follow_up_trigger"], expected_type, slot_options)
        # Body + trigger, separated by a blank line so the front end renders them as
        # separate bubbles.
        #
        # This replaces the earlier "Option A" design, which returned ONLY the trigger.
        # That meant the `answer` body of all 45 Conditional intents never reached Chat
        # at all -- roughly 66k characters of answer text, reachable only through Browse.
        # It also silently dropped content that matters: the anti-scam warnings in
        # posting_influence ("NYSC does not sell state postings... is a scammer") and
        # ppa_change_request ("don't pay anyone to speed up a reposting") live in those
        # bodies, and neither is repeated in any branch, so a chat user never saw them.
        #
        # `answer` already carries the empathetic opener for STRESS_FLAGGED_INTENTS,
        # so it is not re-added here.
        # Emit the question that is actually PENDING, not the KB field. For a flat Conditional
        # the two are the same string, set from this row by set_pending just above. For a
        # COMPOUND intent they are not: the pending question is the first sub-slot's own ask,
        # because the KB trigger asks about every slot at once.
        #
        # Emitting the KB field for a compound intent was the reported bug. It rendered a
        # two-slot question while only the first slot's options existed, the user answered one
        # half, and the second sub-slot then asked the other half again as a fresh turn. Reading
        # the pending question instead keeps one source of truth for what was asked, which also
        # keeps koppal_api's `ask` tagging correct, since that compares the last bubble against
        # state.pending_question["text"].
        pending = state.pending_question or {}
        trigger = (pending.get("text") or "").strip() or kb_row["follow_up_trigger"]
        body = (answer or "").strip()
        return f"{body}\n\n{trigger}" if body else trigger

    # Statement / Procedural -- self-contained, no new pending state.
    #
    # A stacked question is re-asked as its own bubble. Nothing else is appended.
    # Small talk used to be tacked onto every factual answer, which read as a
    # non-sequitur: "...collected at your LGA of service on final clearance."
    # followed by "Nothing much on my side -- what are you thinking about?".
    # Genuine chitchat is caught by the pre-layer before classification ever runs,
    # so this append only ever added noise to real answers.
    if state.pending_question:
        answer += "\n\n" + state.pending_question["text"]
    return answer


def _apply_compound_sub_slot(state, sub, question_text=None):
    """Point `pending_question` at the sub-slot being asked RIGHT NOW.

    `expected_type` stays "compound" because that is the key handle_message routes on, so the
    sub-slot's own type travels alongside it as `sub_expected_type`. Without this the compound
    path left `options` empty for the whole exchange, so a front end could render the question
    but none of its choices -- which is why relocation, the largest intent in the KB, asked a
    follow-up and then offered nothing to answer it with.
    """
    state.pending_question = {
        "text": sub["ask"] if question_text is None else question_text,
        "expected_type": "compound",
        "options": sub.get("options", {}) or [],
        "sub_slot": sub["name"],
        "sub_expected_type": sub["expected_type"],
    }


def _check_compound_slots(message: str, state: ConversationState, kb_lookup_fn, fuzzy=True):
    """
    Try to match the message against every still-unfilled sub-slot of
    the active compound intent. Fills whatever it can find (a single
    message may answer one or both sub-slots at once). If any sub-slot
    remains unfilled after this, ask specifically for it -- never close
    the question on a partial answer. Returns None if nothing at all
    matched, so the caller can fall through to normal classification.
    """
    sub_slots = COMPOUND_SLOTS[state.active_intent]
    found_anything = False

    asked = (state.pending_question or {}).get("sub_slot")

    for sub in sub_slots:
        if sub["name"] in state.compound_fills:
            continue  # already filled earlier in this exchange
        # A yes_no slot matches almost any affirmative, so it may only be filled by the
        # message that was actually asked for it. Without this guard one "yes" fills BOTH
        # slots of a yes_no x yes_no intent like foreign_graduate_verification, and the bot
        # answers a second question the user never actually answered. Same greediness the
        # dropped free_text `reason` slot had (see the COMPOUND_SLOTS note).
        if sub["expected_type"] == "yes_no" and asked is not None and sub["name"] != asked:
            continue
        value = _check_pending_slot(message, sub["expected_type"], sub.get("options", []))
        if value is None and fuzzy:
            value = _fuzzy_check_pending(message, sub["expected_type"], sub.get("options", []))
        if value is not None:
            state.compound_fills[sub["name"]] = value
            found_anything = True

    if not found_anything:
        return None

    missing = [sub for sub in sub_slots if sub["name"] not in state.compound_fills]
    if missing:
        # Move the pending question onto the slot actually being asked, so its choices are
        # available too. Previously this returned the next `ask` as text while leaving
        # pending_question describing the original combined trigger with no options.
        _apply_compound_sub_slot(state, missing[0])
        # Just ask the remaining slot. The old "Got it -- ground: marital." prefix leaked
        # raw internal slot keys (sub-slot name + canonical value) to the user and read as
        # the bot narrating its own state. The captured slot needs no echo; the next
        # question alone is the natural continuation. Covers every compound intent
        # (relocation_general_process, foreign_graduate_verification, logistics_travel_to_camp).
        return missing[0]["ask"]

    # all sub-slots filled -- resolve like a normal single-slot fill
    return _fill_slot_and_advance(state, state.compound_fills, kb_lookup_fn)


def _check_pending_slot(message: str, expected_type: str, options):
    """
    `options` for branch_select is now the D6 {canonical_key: [synonyms]}
    dict (was a flat label list). Returns the matched CANONICAL KEY, not a
    label -- that key is what selects the branch out of the KB's
    follow_up_answer at _fill_slot_and_advance / _parse_branches time.
    """
    msg = message.strip().lower()
    if expected_type == "yes_no":
        for val, variants in YES_NO_LIST.items():
            if msg in variants:
                return val
        return None
    if expected_type == "state":
        if msg.title() in STATES_LIST:
            return msg.title()
        return None
    if expected_type == "branch_select":
        # Longest-match-wins, not first-match-wins. First-match-wins broke on
        # negated phrases: "approved"'s synonym "approved" is a substring of
        # "rejected"'s synonym "not approved", so a message like "it was not
        # approved" matched "approved" first purely because that key happened
        # to be checked first in dict order. Picking the longest matching
        # synonym across ALL keys means the more specific phrase always wins.
        #
        # The canonical keys are added to the pool as well, because the UI sends
        # them verbatim: render_branch_buttons labels each button with its
        # canonical key and app.py feeds the clicked label back in as if it were
        # typed. Keys are only sometimes present in their own synonym list, so
        # without this a click on `not_paid` or `ppa` fell straight through to
        # classification and the branch was never served.
        pool = {s: key for key, syns in options.items() for s in syns}
        pool.update({key: key for key in options})
        hits = [s for s in pool if s in msg]
        if hits:
            return pool[max(hits, key=len)]
        return None
    if expected_type == "free_text":
        return message.strip()
    return None


def _fuzzy_check_pending(message: str, expected_type: str, options):
    if expected_type == "yes_no":
        return fuzzy_match(message, ["yes", "no"])
    if expected_type == "state":
        return fuzzy_match(message, STATES_LIST)
    if expected_type == "branch_select":
        pool = {s: key for key, syns in options.items() for s in syns}
        pool.update({key: key for key in options})
        hit = fuzzy_match(message, list(pool.keys()))
        return pool.get(hit) if hit else None
    return None


def _chat_body(kb_row) -> str:
    """The short reply Chat serves for an intent.

    Resolution order, most specific answer first. Only steps 3 and 4 have data today;
    steps 1 and 2 are handled by their own call sites (per-question retrieval, and the
    branch lookup in _fill_slot_and_advance / _prematch_branch). Keeping the order
    explicit here means per-question answers can be switched on by adding data rather
    than by restructuring:

        1. a per-question answer for the specific question asked      [not yet populated]
        2. the branch answer, when a branch was named or selected     [live]
        3. the intent's `chat_answer`                                 [rolling out]
        4. the prose `answer`, as a fallback while 3 is incomplete    [live]

    Step 4 is deliberately a fallback and not the destination: prose belongs in Browse.
    Once every intent has a chat_answer, step 4 should never fire, and kb_validate.py
    is what makes that enforceable.
    """
    chat = (kb_row.get("chat_answer") or "").strip()
    if chat:
        return chat
    return (kb_row.get("answer") or "").strip()


def _prematch_branch(message: str, options) -> str:
    """Return a branch key if the user's own words already single one out, else None.

    Two deliberate restrictions, because on this turn there is no question on the
    table and a loose match would answer something the user never asked:

    * exact substring only, no fuzzy matching (fuzzy stays for answering a question
      that has actually been put to the user);
    * the match must be UNAMBIGUOUS. If the message hits synonyms belonging to two
      different branches it is not a specific request, so fall through and ask.
      "When will I know my batch?" hits `when will` (timetable) and `know my`
      (find_mine), which is exactly the case that should still get the question.
    """
    if not options or "__slot__" in options:
        return None
    msg = message.lower().strip()
    matched = set()
    for key, syns in options.items():
        for candidate in list(syns) + [key]:
            if candidate in msg:
                matched.add(key)
                break
    return next(iter(matched)) if len(matched) == 1 else None


def _parse_branches(follow_up_answer: str) -> dict:
    """
    C1 normalized every branch fork to `key -> answer text || key -> answer
    text`. For a compound intent the keys are prefixed `slotname:key`
    (e.g. "ground:health -> ... || stage:in_camp -> ..."). Returns
    {key: answer_text} (compound keys kept exactly as written, e.g.
    "ground:health"). Falls back to an empty dict if the field isn't in
    this format (defensive -- shouldn't happen post-C1, but a malformed
    row shouldn't crash the bot).
    """
    if not follow_up_answer or "->" not in follow_up_answer:
        return {}
    branches = {}
    for chunk in follow_up_answer.split("||"):
        if "->" not in chunk:
            continue
        key, _, text = chunk.partition("->")
        branches[key.strip()] = text.strip()
    return branches


# Words that carry no course meaning. Users type "Department of Mechanical Engineering",
# "BSc Computer Science", "I studied Law" -- none of those extra words identify the field.
_COURSE_FILLER = {"department", "dept", "of", "the", "in", "my", "course", "studied", "study",
                  "studies", "bsc", "b", "sc", "msc", "m", "hnd", "nd", "degree", "and", "with"}


def _normalise_course(text):
    tokens = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()
    return [t for t in tokens if t not in _COURSE_FILLER]


def _resolve_course_bucket(text):
    """Course text -> broad-field bucket, tolerant of how people actually write it.

    Exact key first. Then token-prefix matching, because Nigerian students write "mech eng",
    "comp sci", "mass comm", "Elect/Elect" far more often than the full programme name, and
    an exact-key dict misses every one of those and falls through to the generic caveat.

    Ambiguity is resolved at the BUCKET level, not the course level. "eng" prefixes a dozen
    engineering courses, but they all bucket to Engineering and the bucket is the only thing
    the reply depends on, so that is not ambiguous. "eng" ALSO prefixes "english language",
    which buckets to Arts/Humanities, so two buckets are in play and it correctly refuses to
    guess rather than telling an English graduate about oil and gas.
    """
    exact = COURSE_BUCKET_MAP.get((text or "").strip().lower())
    if exact:
        return exact

    typed = [t for t in _normalise_course(text) if len(t) >= 2]
    if not typed:
        return None

    buckets = set()
    for course, bucket in COURSE_BUCKET_MAP.items():
        known = _normalise_course(course)
        if len(typed) == 1:
            # A single word can name the field rather than the programme, and the field word
            # is not always first: "engineering" is the SECOND token of "mechanical
            # engineering". So scan every position. This is also what makes "eng" correctly
            # refuse, since it prefixes both "engineering" and "english".
            if any(k.startswith(typed[0]) for k in known):
                buckets.add(bucket)
        elif len(typed) <= len(known) and all(k.startswith(t) for t, k in zip(typed, known)):
            buckets.add(bucket)
    return buckets.pop() if len(buckets) == 1 else None


def _fill_slot_and_advance(state: ConversationState, value, kb_lookup_fn):
    """
    THE FIX: previously this always returned kb_row["follow_up_answer"]
    (or the whole `answer`) in full, discarding which branch the user
    actually picked -- every scenario got dumped regardless of what was
    asked. Now it parses the branch-keyed follow_up_answer (C1 format) and
    returns ONLY the branch(es) matching `value`.

    `value` is either a single matched canonical key (flat Conditional), or
    a dict {sub_slot_name: key} for a resolved compound intent -- per
    CC-01's "pragmatic assembly": each filled slot's own sub-answer is
    served, independently, not a full cross-product answer.
    """
    kb_row = kb_lookup_fn(state.active_intent)

    # __slot__ intents (state_secretariat_location, ppa_course_matching):
    # their follow_up_answer is empty/unstructured in the KB, so the
    # generic ->/|| branch parser has nothing to parse. Resolve these two
    # from their own dedicated lookup tables instead, before falling
    # through to the generic path (which still handles ppa_change_request
    # and every true branch_select Conditional).
    if state.active_intent == "state_secretariat_location" and isinstance(value, str):
        address = STATE_SECRETARIAT_ADDRESSES.get(value)
        answer = f"{value} State Secretariat: {address}" if address else kb_row["answer"]
        if not state.pop_pending():
            pass
        if state.pending_question:
            answer += " Back to your earlier question: " + state.pending_question["text"]
        return answer

    if state.active_intent == "ppa_course_matching" and isinstance(value, str):
        bucket = _resolve_course_bucket(value)
        if bucket and bucket in COURSE_BUCKET_REPLIES:
            answer = COURSE_BUCKET_REPLIES[bucket]
        else:
            # Course not in the map -- don't guess, fall back to the KB's
            # general caveat-first answer rather than inventing a bucket.
            answer = ("I don't have a specific tendency mapped for that "
                      "course, but the general pattern holds: " + kb_row["answer"])
        if not state.pop_pending():
            pass
        if state.pending_question:
            answer += " Back to your earlier question: " + state.pending_question["text"]
        return answer

    branches = _parse_branches(kb_row.get("follow_up_answer", ""))

    if isinstance(value, dict):
        # Compound: assemble each filled sub-slot's own sub-answer, in the
        # order the slots were defined for this intent.
        sub_slots = COMPOUND_SLOTS.get(state.active_intent, [])
        parts = []
        for sub in sub_slots:
            slot_key = value.get(sub["name"])
            if slot_key is None:
                continue
            branch_key = f"{sub['name']}:{slot_key}"
            parts.append(branches.get(branch_key, ""))
        answer = "\n\n".join(p for p in parts if p) or kb_row["answer"]
    else:
        # Flat Conditional: value is the single matched canonical key.
        answer = branches.get(value)
        if answer is None:
            # Defensive fallback -- unparseable/legacy row, don't crash,
            # but this means C1 wasn't applied to this intent.
            answer = kb_row.get("follow_up_answer") or kb_row["answer"]

    if not state.pop_pending():
        pass  # nothing left on the stack, state already cleared by pop_pending
    if state.pending_question:
        answer += " Back to your earlier question: " + state.pending_question["text"]
    return answer
