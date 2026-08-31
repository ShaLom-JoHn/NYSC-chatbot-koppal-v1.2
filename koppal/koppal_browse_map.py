"""Browse presentation map: a human title for every intent, and chapters inside
the large categories.

WHY THIS FILE EXISTS
Browse used to label every topic line with `intent.replace("_", " ")`, so users
were shown internal keys: "items laptop allowed", "kit footwear extra pair",
"logistics arrival timing". The same computed label appeared on the shelf, the
category page and the full-answer page, which is why the intent names felt
redundant everywhere -- it was one missing layer surfacing in three places.

THE CONTRACT (same as MILESTONES in koppal_api.py)
This is presentation ONLY:
  * the KB's own `category` and `intent` columns are never rewritten;
  * nothing here reaches the classifier or changes an answer;
  * an intent missing from TITLES still renders -- it falls back to the old
    intent-name-with-spaces label, so a new KB row is never invisible;
  * an intent missing from CHAPTERS lands in a trailing "More in this category"
    group rather than disappearing.
So this file can be edited freely without touching the engine or the data.

Chapter names are written in sentence case here; the UI is free to display them
uppercase. Titles are noun phrases, not questions -- the question a user would
actually type is shown separately on the full-answer page, taken from
data/paraphrases.csv.
"""

# Real KB rows that must never appear in Browse: the noise class the classifier
# is trained against, and the catch-all reply for anything off-topic. Both are
# machinery, not topics anyone browses to.
HIDDEN = {"noise", "out_of_scope"}

# Rows the KB has merged into another intent and kept only for provenance. The
# classifier has no questions of its own for these -- verified: cds_group has
# zero training rows, every CDS question is labelled cds_general -- so they must
# not surface as a second, identical Browse entry. Value = the intent that
# replaced them, so a caller can redirect to it if it ever needs to.
SUPERSEDED = {"cds_group": "cds_general"}

# Categories small enough to read as one list get no chapters at all. Only the
# three large ones are grouped -- see CHAPTERS below.
TITLES = {
    # ------------------------------------------------ Registration & Eligibility (44)
    "age_eligibility":                  "Age limit for service",
    "prior_registration_history":       "Serving a second time",
    "remobilization_after_abandon":     "Coming back after absconding",
    "exclusion_letter_process":         "Part-time and distance learning graduates",
    "siwes_vs_nysc":                    "SIWES and NYSC are different",
    "foreign_graduate_verification":    "Graduates from foreign schools",
    "postpone_defer_service":           "Delaying or deferring service",

    "senate_list_status":               "Senate List status",
    "jamb_number_issue":                "Invalid or missing JAMB number",
    "jamb_name_mismatch":               "Name mismatch between JAMB and your school",
    "jamb_regularization":              "JAMB regularisation",
    "jamb_documents_requirement":       "Whether JAMB documents are needed",
    "statement_of_result_requirement":  "Statement of Result requirements",
    "waec_certificate_requirement":     "WAEC certificate",
    "olevel_fslc_requirement":          "O-level and FSLC certificates",

    "portal_open_registration_window":  "When registration opens",
    "registration_method_at_home":      "Registering from home",
    "registration_documents_general":   "What you need to register",
    "registration_payment_issue":       "Payment problems",
    "portal_account_access":            "Locked out of the portal",
    "portal_evaluation_status":         "What “not evaluated” means",
    "registration_slip_printing":       "Printing your registration slip",
    "green_card_printing":              "Printing your Green Card",
    "biometric_capture":                "Fingerprints and live photo",
    "medical_fitness_report":           "Medical Fitness Certificate",
    "nerd_clearance_process":           "NERD clearance and its fee",

    "name_correction":                  "Wrong name",
    "dob_discrepancy_correction":       "Wrong date of birth",
    "place_of_birth_correction":        "Wrong place of birth",
    "state_of_origin_correction":       "Wrong state of origin",
    "course_of_study_correction":       "Wrong course of study",
    "institution_details_correction":   "Wrong institution details",
    "admission_year_correction":        "Wrong year of admission",
    "graduation_date_correction":       "Wrong graduation date",
    "profile_data_error":               "Wrong degree or class of degree",
    "bvn_name_mismatch":                "BVN name mismatch",

    "callup_letter_meaning":            "What a call-up letter is",
    "callup_number_vs_letter":          "Call-up number vs call-up letter",
    "callup_number_delay":              "Call-up number hasn’t arrived",
    "callup_letter_access":             "Getting your call-up letter",
    "batch_stream_timing":              "How batch and stream are decided",
    "stream_assignment":                "Whether you can choose your stream",
    "revalidation":                     "Revalidation for the next batch",
    "missed_posting_consequence":       "Not reporting to camp",

    # ------------------------------------------------ Orientation Camp (32)
    "logistics_general_experience":     "What the three weeks are like",
    "logistics_accommodation":          "Hostels and sleeping arrangements",
    "logistics_food":                   "Camp food and meal times",
    "logistics_platoon_duties":         "Platoon duties",
    "logistics_laundry":                "Laundry and washing",
    "logistics_social":                 "Making friends in camp",
    "logistics_budget":                 "How much money to bring",
    "logistics_curfew_leaving":         "Curfew and leaving the camp",
    "camp_visitors":                    "Visitors",

    "logistics_travel_to_camp":         "Finding your camp and getting there",
    "logistics_arrival_timing":         "Arriving late",
    "docs_required_at_camp":            "Documents to bring to camp",

    "kit_packing_list_general":         "Full packing list",
    "camp_kit":                         "What NYSC gives you, what you bring",
    "kit_footwear":                     "White canvas and footwear",
    "kit_footwear_extra_pair":          "A spare pair of shoes",
    "kit_tshirt":                       "White T-shirts",
    "kit_waist_pouch":                  "Waist pouch",
    "kit_khaki_customization":          "Adjusting or restyling your khaki",
    "kit_replacement_lost_items":       "Replacing lost kit",
    "logistics_belongings_mixed_up":    "Belongings getting mixed up",

    "camp_items_allowed":               "What is allowed and what is seized",
    "items_phone_allowed":              "Phones",
    "items_laptop_allowed":             "Laptops and tablets",
    "items_car_allowed":                "Cars",
    "items_food_allowed":               "Food and drinks",
    "items_personal_allowed":           "Books, games and personal items",

    "saed_program":                     "SAED skills programme",

    "state_secretariat_location":       "State Secretariat",
    "nysc_headquarters_location":       "NYSC Headquarters",
    "lgi_office_location":              "Your LGI office",

    # ------------------------------------------------ Posting & PPA (16)
    "ppa_checking_process":             "Checking your posting",
    "reporting_deadline_after_camp":    "Reporting to your PPA after camp",
    "posting_influence":                "Influencing where you are posted",
    "ppa_course_matching":              "Whether your course decides your PPA",
    "direct_posting":                   "“Direct posting” and middlemen",

    "ppa_type_non_teaching":            "Non-teaching postings",
    "ppa_private_sector":               "Private companies",
    "ppa_ngo_service":                  "NGOs",
    "serve_at_current_workplace":       "Serving at your current workplace",
    "ppa_registration_status":          "Whether a PPA is registered with NYSC",

    "ppa_rejection_reposting":          "If your PPA rejects you",
    "ppa_change_request":               "Changing your PPA",
    "change_local_government":          "Changing local government",
    "ppa_accommodation":                "Accommodation at your PPA",
    "ppa_documentation":                "Posting and acceptance letters",
    "consequence_of_not_reporting":     "Not reporting to your PPA",

    # ------------------------------------------------ small categories, no chapters
    # Allowance (4)
    "allowance_amount":                 "How much the allowance is",
    "allowance_payment_issue":          "Allowance not paid",
    "allowance_bank_account":           "Your NYSC bank account",
    "nhis_health_insurance":            "Health insurance cover",

    # Redeployment & Relocation (5)
    "relocation_general_process":       "How to apply for relocation",
    "relocation_status_tracking":       "Tracking your relocation request",
    "relocation_cost":                  "What relocation costs",
    "post_relocation_process":          "After relocation is approved",
    "multiple_redeployment":            "Relocating more than once",

    # Working & Life During Service (7)
    "cds_general":                      "CDS through the year",
    "leave_travel_during_service":      "Leave and travel",
    "work_side_hustle_during_service":  "Working or a side hustle",
    "professional_study_during_service": "Professional certifications",
    "postgraduate_study_during_service": "Postgraduate study",
    "disciplinary_query":               "Query letters",
    "dssc_during_service":              "Applying for DSSC",

    # Clearance (4)
    "monthly_clearance":                "Monthly clearance",
    "clearance_logistics_general":      "Where and how clearance happens",
    "clearance_ppa_wont_sign":          "If your PPA will not sign",
    "service_extension":                "Service extension as a penalty",

    # Certificates & Documents (4)
    "id_card_replacement":              "Replacing your ID card",
    "exemption_certificate":            "Certificate of Exemption",
    "certificate_verification":         "Verifying an NYSC certificate",
    "certificate_correction_pending":   "Corrections before you travel to camp",

    # End of Service (3)
    "pop_explainer":                    "Passing Out Parade",
    "final_clearance":                  "Final clearance",
    "discharge_certificate":            "Discharge Certificate",

    # Special Circumstances (6)
    "pregnancy_accommodation":          "Pregnancy",
    "marital_family_accommodation":     "Marriage and family",
    "disability_accommodation":         "Disability",
    "bereavement_family_emergency":     "Bereavement and family emergencies",
    "decampment":                       "Decampment",
    "service_abscondment":              "Absconding from service",

    # Terms & Lookups (3)
    "term_lookup":                      "Look up a term or institution code",
    "state_code_meaning":               "What your state code means",
    "nysc_terminology_corper":          "“Corper” and other slang",

    # General / Meta (4 shown; out_of_scope is HIDDEN)
    "general_meta_about_nysc":          "What NYSC is",
    "nysc_purpose_history":             "Why NYSC was created",
    "nysc_year_structure":              "The four stages of the service year",
    "nysc_skip_consequences":           "Consequences of never serving",
}

# Chapters, in reading order, for the three categories too large to read as one
# list: Registration & Eligibility (44 topics), Orientation Camp (32) and
# Posting & PPA (16). Every other category is under about seven topics and reads
# fine flat, so it is deliberately absent here.
#
# Note on the two Camp chapters: kit and items were one group ("belongings") in
# the original sketch, but merged they are 15 topics -- the same cramped wall the
# chapters are meant to fix. Split by the question being asked instead: what you
# should PACK, versus what you are ALLOWED to bring in.
CHAPTERS = {
    "Registration & Eligibility": [
        ("Can you serve", [
            "age_eligibility", "prior_registration_history",
            "remobilization_after_abandon", "exclusion_letter_process",
            "siwes_vs_nysc", "foreign_graduate_verification",
            "postpone_defer_service",
        ]),
        ("Your school, JAMB and certificates", [
            "senate_list_status", "jamb_number_issue", "jamb_name_mismatch",
            "jamb_regularization", "jamb_documents_requirement",
            "statement_of_result_requirement", "waec_certificate_requirement",
            "olevel_fslc_requirement",
        ]),
        ("Registering on the portal", [
            "portal_open_registration_window", "registration_method_at_home",
            "registration_documents_general", "registration_payment_issue",
            "portal_account_access", "portal_evaluation_status",
            "registration_slip_printing", "green_card_printing",
            "biometric_capture", "medical_fitness_report",
            "nerd_clearance_process",
        ]),
        ("When your details are wrong", [
            "name_correction", "dob_discrepancy_correction",
            "place_of_birth_correction", "state_of_origin_correction",
            "course_of_study_correction", "institution_details_correction",
            "admission_year_correction", "graduation_date_correction",
            "profile_data_error", "bvn_name_mismatch",
        ]),
        ("Call-up, batch and stream", [
            "callup_letter_meaning", "callup_number_vs_letter",
            "callup_number_delay", "callup_letter_access",
            "batch_stream_timing", "stream_assignment", "revalidation",
            "missed_posting_consequence",
        ]),
    ],
    "Orientation Camp": [
        ("What camp is like", [
            "logistics_general_experience", "logistics_accommodation",
            "logistics_food", "logistics_platoon_duties", "logistics_laundry",
            "logistics_social", "logistics_budget", "logistics_curfew_leaving",
            "camp_visitors",
        ]),
        ("Getting there", [
            "logistics_travel_to_camp", "logistics_arrival_timing",
            "docs_required_at_camp",
        ]),
        ("What to pack", [
            "kit_packing_list_general", "camp_kit", "kit_footwear",
            "kit_footwear_extra_pair", "kit_tshirt", "kit_waist_pouch",
            "kit_khaki_customization", "kit_replacement_lost_items",
            "logistics_belongings_mixed_up",
        ]),
        ("What you can bring in", [
            "camp_items_allowed", "items_phone_allowed", "items_laptop_allowed",
            "items_car_allowed", "items_food_allowed", "items_personal_allowed",
        ]),
        ("Camp programmes", [
            "saed_program",
        ]),
        ("Offices and addresses", [
            "state_secretariat_location", "nysc_headquarters_location",
            "lgi_office_location",
        ]),
    ],
    "Posting & PPA": [
        ("Getting your posting", [
            "ppa_checking_process", "reporting_deadline_after_camp",
            "posting_influence", "ppa_course_matching", "direct_posting",
        ]),
        ("Where you can be posted", [
            "ppa_type_non_teaching", "ppa_private_sector", "ppa_ngo_service",
            "serve_at_current_workplace", "ppa_registration_status",
        ]),
        ("Problems with your PPA", [
            "ppa_rejection_reposting", "ppa_change_request",
            "change_local_government", "ppa_accommodation",
            "ppa_documentation", "consequence_of_not_reporting",
        ]),
    ],
}

# Anything in a chaptered category that this file forgot lands here rather than
# vanishing off the page.
LEFTOVER_CHAPTER = "More in this category"

# The full-answer page quotes a real question in a user's own words. Those live in
# the training set (nysc_question_source-1.csv, 1,477 rows) and in
# data/paraphrases.csv -- between them they cover 119 of the 131 browsable
# intents. The 12 below are the exception, and for a reason: they were each split
# out of a broader parent intent (camp_kit, camp_items_allowed)
# AFTER the training set was built, so their questions are still filed under the
# parent. Every string here is a verbatim row from that parent's pool, re-homed
# for display only -- nothing is invented and no data file is rewritten.
QUESTION_OVERRIDES = {
    "kit_packing_list_general":     "What should I pack for NYSC orientation camp?",
    "kit_footwear":                 "Do we necessarily have to be on tennis shoes, "
                                    "or are other types of white sneakers allowed?",
    "kit_footwear_extra_pair":      "Do I need to carry two pairs of white shoes to camp?",
    "kit_tshirt":                   "Is a V-neck white T-shirt allowed in camp?",
    "kit_waist_pouch":              "Can my waist pouch be multicolour?",
    "kit_khaki_customization":      "Am I allowed to customize my khaki?",
    "kit_replacement_lost_items":   "How can I get NYSC uniform if mine got lost in transit?",
    "items_laptop_allowed":         "Can I take my laptop into NYSC camp?",
    "items_phone_allowed":          "Are phones allowed in camp?",
    "items_car_allowed":            "Can I come with my car to NYSC camp?",
    "items_food_allowed":           "Can I take beverages such as Milo, Milk and Flakes to camp?",
    "items_personal_allowed":       "Can I go with my chess board?",
}


def is_hidden(intent: str) -> bool:
    """True for KB rows that shouldn't be browsable: machinery (noise,
    out_of_scope) and rows superseded by a merge, kept only for provenance."""
    return intent in HIDDEN or intent in SUPERSEDED


def title_of(intent: str) -> str:
    """The human title, or the old computed label if this intent isn't mapped yet.
    A new KB row is therefore never invisible -- it just reads roughly until a
    title is written for it."""
    return TITLES.get(intent) or intent.replace("_", " ").strip()


def has_chapters(category: str) -> bool:
    return category in CHAPTERS


def chapter_of(category: str, intent: str) -> str:
    """The chapter heading an intent sits under.

    A small category has no chapters, so it answers with its own name -- that way the
    full-answer page always has a sub-line to show, and it is never the same string as the
    back control above it (which names the page one level up, not the category).
    """
    for name, members in CHAPTERS.get(category, []):
        if intent in members:
            return name
    return LEFTOVER_CHAPTER if category in CHAPTERS else category


def chapters_for(category: str, intents):
    """Group `intents` (the KB order for one category) into display chapters.

    Returns [(chapter_title, [intent, ...]), ...]. Categories with no chapter map
    come back as a single unnamed group, so a caller can render both shapes with
    one code path. Only intents actually present in `intents` are emitted, so a
    chapter listing an intent that later leaves the KB simply shrinks.
    """
    live = [i for i in intents if not is_hidden(i)]
    if category not in CHAPTERS:
        return [(None, live)]

    remaining = list(live)
    out = []
    for name, members in CHAPTERS[category]:
        picked = [i for i in members if i in remaining]
        if picked:
            out.append((name, picked))
            remaining = [i for i in remaining if i not in picked]
    if remaining:
        out.append((LEFTOVER_CHAPTER, remaining))
    return out

