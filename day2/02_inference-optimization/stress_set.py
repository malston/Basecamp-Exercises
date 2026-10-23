"""Stress set: ten harder supplier contracts for run_clausescan.py --stress.

The workshop sample is easy enough that every model scores 100%, which cannot justify a model
choice. These contracts each contain one trap the playbook explicitly addresses (amendments that
change or restore terms, venue vs governing law, insurance vs liability cap, cap exceptions,
renewal terms in a schedule, one-sided termination rights).

Gold labels follow the playbook's rules and were written by the engineer, not a lawyer. Have a
reviewer confirm them before quoting any stress-set number to a client.
"""

STRESS_CONTRACTS = [
    {"id": "S-301", "vendor": "Meridian Castings Inc. (amendment lowers cap)", "text": """SUPPLY AGREEMENT -- Meridian Castings Inc. ("Seller") and Volta Industrial Group ("Buyer").

1. SUPPLY. Seller supplies cast components per purchase orders.
2. TERM. Thirty-six (36) months. Any continuation requires a written agreement signed by both parties.
3. PRICING. Per Annex A.
4. LIMITATION OF LIABILITY. Each party's aggregate liability shall not exceed FIVE MILLION U.S. DOLLARS ($5,000,000).
5. ASSIGNMENT. Neither party may assign this Agreement, including by merger or change of control, without the other party's prior written consent.
6. GOVERNING LAW. The laws of the State of New York.

AMENDMENT NO. 1 (executed and effective). Section 4 is deleted and replaced with: "Each party's aggregate liability shall not exceed SEVEN HUNDRED FIFTY THOUSAND U.S. DOLLARS ($750,000)." All other terms unchanged."""},
    {"id": "S-302", "vendor": "Corvid Software Ltd. (cap deleted then reinstated)", "text": """SOFTWARE LICENCE AND SUPPORT AGREEMENT -- Corvid Software Ltd. ("Licensor") and Volta Industrial Group ("Licensee").

1. LICENCE. Non-exclusive licence to the Corvid platform for Licensee's internal use.
2. TERM AND RENEWAL. Two (2) years, then renewing for successive one-year terms unless either party gives sixty (60) days' written notice of non-renewal.
3. LIMITATION OF LIABILITY. Licensor's aggregate liability shall not exceed ONE MILLION U.S. DOLLARS ($1,000,000).
4. ASSIGNMENT. Either party may assign this Agreement on written notice, including to a successor on a change of control. No consent is required.
5. GOVERNING LAW. The laws of England and Wales.

AMENDMENT NO. 1 (executed). Section 3 is deleted in its entirety.

AMENDMENT NO. 2 (executed, later in time than Amendment No. 1). Section 3 is reinstated with the following text: "Licensor's aggregate liability shall not exceed TWO MILLION U.S. DOLLARS ($2,000,000)." """},
    {"id": "S-303", "vendor": "Tidewater Packaging B.V. (one-sided termination right)", "text": """PACKAGING SUPPLY AGREEMENT -- Tidewater Packaging B.V. ("Supplier") and Volta Industrial Group ("Customer").

1. SUPPLY. Supplier supplies packaging materials per Customer's forecasts.
2. TERM. Three (3) years. The Agreement then expires; renewal is only by mutual written agreement.
3. LIABILITY. Each party's total liability under this Agreement is limited to THREE HUNDRED THOUSAND U.S. DOLLARS ($300,000).
4. ASSIGNMENT. Either party may assign this Agreement to an affiliate on notice.
5. TERMINATION. Supplier may terminate this Agreement on sixty (60) days' notice if Customer undergoes a change of control. Customer has no corresponding right.
6. GOVERNING LAW. The laws of the Netherlands."""},
    {"id": "S-304", "vendor": "Oakridge Chemicals LLC (customer-only consent, no cap)", "text": """CHEMICAL SUPPLY AGREEMENT -- Oakridge Chemicals LLC ("Supplier") and Volta Industrial Group ("Customer").

1. SUPPLY. Supplier delivers process chemicals per Customer's orders.
2. TERM AND RENEWAL. One (1) year, automatically renewing for successive one-year terms unless either party gives thirty (30) days' notice.
3. LIABILITY. Each party is liable for direct damages arising from its breach. No limitation of liability applies to either party.
4. ASSIGNMENT. Supplier may assign this Agreement freely on written notice. Customer may not assign or transfer this Agreement, including by merger or change of control, without Supplier's prior written consent.
5. GOVERNING LAW. The laws of the State of Delaware."""},
    {"id": "S-305", "vendor": "Summit Grounds Care Inc. (insurance is not a cap)", "text": """GROUNDS MAINTENANCE AGREEMENT -- Summit Grounds Care Inc. ("Contractor") and Volta Industrial Group ("Client").

1. SCOPE. Landscaping and snow removal for the sites in Exhibit 1.
2. TERM. Twenty-four (24) months, expiring at the end of the term without renewal.
3. FEES. Fixed monthly fee per Exhibit 2.
4. INSURANCE. Contractor maintains commercial general liability insurance of $5,000,000 per occurrence and $10,000,000 in the aggregate.
5. ASSIGNMENT. Either party may assign this Agreement on written notice without consent.
6. GOVERNING LAW. The laws of the State of Florida."""},
    {"id": "S-306", "vendor": "Pinecrest Logistics Inc. (cap with fees-paid formula)", "text": """TRANSPORT SERVICES AGREEMENT -- Pinecrest Logistics Inc. ("Carrier") and Volta Industrial Group ("Shipper").

1. SERVICES. Carrier provides road freight services.
2. TERM AND RENEWAL. Twelve (12) months, renewing automatically for successive twelve-month terms unless either party gives ninety (90) days' notice.
3. LIMITATION OF LIABILITY. CARRIER'S AGGREGATE LIABILITY SHALL NOT EXCEED THE GREATER OF FOUR HUNDRED THOUSAND U.S. DOLLARS ($400,000) AND THE FEES PAID IN THE PRIOR TWELVE MONTHS, PROVIDED THAT IN NO EVENT SHALL IT EXCEED $400,000.
4. ASSIGNMENT. Neither party may assign this Agreement, whether by operation of law, merger, change of control or otherwise, without the prior written consent of the other party.
5. GOVERNING LAW. The laws of the State of Washington."""},
    {"id": "S-307", "vendor": "Harbor IP Tools Corp. (indemnity outside the cap)", "text": """TOOLING AND LICENCE AGREEMENT -- Harbor IP Tools Corp. ("Vendor") and Volta Industrial Group ("Customer").

1. SUPPLY. Vendor supplies tooling and associated software licences.
2. TERM AND RENEWAL. Two (2) years, then automatically renewing for one-year terms unless either party gives sixty (60) days' notice.
3. LIMITATION OF LIABILITY. Each party's aggregate liability shall not exceed ONE MILLION FIVE HUNDRED THOUSAND U.S. DOLLARS ($1,500,000), except that Vendor's IP indemnity obligations under Section 6 are uncapped.
4. ASSIGNMENT. This Agreement may not be assigned by either party without the other party's prior written consent.
5. WARRANTY. Tooling conforms to its specifications for 12 months.
6. INDEMNITY. Vendor defends and indemnifies Customer against third-party IP infringement claims.
7. GOVERNING LAW. The laws of the Commonwealth of Massachusetts."""},
    {"id": "S-308", "vendor": "Emerald Components Ltd. (venue differs from governing law)", "text": """COMPONENT SUPPLY AGREEMENT -- Emerald Components Ltd. ("Supplier") and Volta Industrial Group ("Buyer").

1. SUPPLY. Supplier supplies electronic components per purchase orders.
2. TERM. Twelve (12) months. Renewal only by mutual written agreement; otherwise the Agreement expires.
3. LIMITATION OF LIABILITY. Each party's aggregate liability shall not exceed NINE HUNDRED THOUSAND U.S. DOLLARS ($900,000).
4. ASSIGNMENT. Either party may assign this Agreement to a successor or affiliate on notice; no consent is required.
5. GOVERNING LAW AND VENUE. This Agreement is governed by the laws of Ireland. The state and federal courts located in New York County, New York have exclusive jurisdiction over any dispute."""},
    {"id": "S-309", "vendor": "Granite Metals Co. (amendment changes governing law)", "text": """METALS SUPPLY AGREEMENT -- Granite Metals Co. ("Seller") and Volta Industrial Group ("Buyer").

1. SUPPLY. Seller supplies bar and plate stock.
2. TERM AND RENEWAL. Two (2) years, automatically renewing for one-year terms unless either party gives sixty (60) days' notice.
3. LIMITATION OF LIABILITY. Each party's aggregate liability shall not exceed TWO HUNDRED FIFTY THOUSAND U.S. DOLLARS ($250,000).
4. ASSIGNMENT. Either party may assign this Agreement to an affiliate on notice. Seller may terminate this Agreement on thirty (30) days' notice upon any change of control of Buyer.
5. GOVERNING LAW. The laws of the State of Delaware.

AMENDMENT NO. 1 (executed and effective). Section 5 is deleted and replaced with: "GOVERNING LAW. This Agreement is governed by the laws of Singapore." """},
    {"id": "S-310", "vendor": "Larkspur Office Supply Co. (renewal sits in a schedule)", "text": """OFFICE SUPPLY AGREEMENT -- Larkspur Office Supply Co. ("Supplier") and Volta Industrial Group ("Customer").

1. SUPPLY. Supplier supplies office consumables per Schedule 3.
2. TERM. The initial term is twenty-four (24) months. Renewal is governed by Schedule 3.
3. LIMITATION OF LIABILITY. Supplier's aggregate liability shall not exceed FIFTY THOUSAND U.S. DOLLARS ($50,000).
4. ASSIGNMENT. Either party may assign this Agreement without consent.
5. GOVERNING LAW. The laws of the State of Ohio.

SCHEDULE 3 -- COMMERCIAL TERMS. Pricing per catalogue. Renewal: at the end of the initial term this Agreement renews automatically for successive twelve-month periods unless either party gives sixty (60) days' written notice of non-renewal."""},
]

STRESS_GOLD = {
    "S-301": {"auto_renewal": False, "change_of_control": True, "liability_cap_usd": 750000,
              "governing_law": "New York", "risk_tier": "MEDIUM"},
    "S-302": {"auto_renewal": True, "change_of_control": False, "liability_cap_usd": 2000000,
              "governing_law": "England and Wales", "risk_tier": "LOW"},
    "S-303": {"auto_renewal": False, "change_of_control": True, "liability_cap_usd": 300000,
              "governing_law": "Netherlands", "risk_tier": "MEDIUM"},
    "S-304": {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": None,
              "governing_law": "Delaware", "risk_tier": "HIGH"},
    "S-305": {"auto_renewal": False, "change_of_control": False, "liability_cap_usd": None,
              "governing_law": "Florida", "risk_tier": "MEDIUM"},
    "S-306": {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": 400000,
              "governing_law": "Washington", "risk_tier": "MEDIUM"},
    "S-307": {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": 1500000,
              "governing_law": "Massachusetts", "risk_tier": "MEDIUM"},
    "S-308": {"auto_renewal": False, "change_of_control": False, "liability_cap_usd": 900000,
              "governing_law": "Ireland", "risk_tier": "LOW"},
    "S-309": {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": 250000,
              "governing_law": "Singapore", "risk_tier": "MEDIUM"},
    "S-310": {"auto_renewal": True, "change_of_control": False, "liability_cap_usd": 50000,
              "governing_law": "Ohio", "risk_tier": "LOW"},
}
