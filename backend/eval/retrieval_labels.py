"""Relevance labels for deterministic retrieval evaluation.

These are deliberately *corpus-grounded*: each question is labelled with the
document(s) a competent librarian would hand you from the pages we actually
index. That differs from the ground-truth answers in test_questions.py, which
were written independently of the corpus — a reasonable choice for judging
answer quality, but wrong for judging retrieval. Asking "did the retriever find
the right page" presupposes the page exists.

`coverage` records whether the corpus can actually answer the question:
  full    — the labelled pages contain the answer
  partial — the labelled pages are the right target but thin on specifics
  none    — nothing in the corpus answers this; excluded from hit@k and MRR

Keeping the `none` cases visible rather than deleting them means the coverage
gap stays measurable instead of being quietly scored as a retrieval failure.
"""

RETRIEVAL_LABELS = [
    {
        "question": "How do I apply for OPT as an F-1 student?",
        "relevant_urls": [
            "https://www.bu.edu/isso/employment/opt/",
            "https://www.bu.edu/isso/international-students/off-campus-student-employment-training/",
        ],
        "coverage": "full",
    },
    {
        "question": "What is CPT and how is it different from OPT?",
        "relevant_urls": [
            "https://www.bu.edu/isso/international-students/off-campus-student-employment-training/curricular-practical-training-cpt/",
            "https://www.bu.edu/isso/employment/opt/",
        ],
        "coverage": "full",
    },
    {
        "question": "Where is the ISSO office at BU?",
        "relevant_urls": [
            "https://www.bu.edu/isso/",
            "https://www.bu.edu/isso/international-students/",
        ],
        "coverage": "full",
    },
    {
        "question": "What documents do I need for my F-1 visa travel signature?",
        "relevant_urls": ["https://www.bu.edu/isso/travel/"],
        # The travel page is only 1.7k chars — right target, thin content.
        "coverage": "partial",
    },
    {
        "question": "How do I get resume help at BU?",
        "relevant_urls": ["https://www.bu.edu/careers/"],
        "coverage": "full",
    },
    {
        "question": "Does BU have a career fair?",
        "relevant_urls": ["https://www.bu.edu/careers/"],
        "coverage": "full",
    },
    {
        "question": "Where is the BU Career Development office?",
        "relevant_urls": ["https://www.bu.edu/careers/"],
        "coverage": "full",
    },
    {
        "question": "How do I drop a class at BU?",
        "relevant_urls": [
            "https://www.bu.edu/reg/registration/",
            "https://www.bu.edu/reg/",
        ],
        # "add/drop" and "drop a class" appear nowhere in the corpus; the
        # registrar pages are the correct retrieval target regardless.
        "coverage": "none",
    },
    {
        "question": "Where can I get academic advising in CAS?",
        "relevant_urls": [
            "https://www.bu.edu/cas/academics/advising/",
            "https://www.bu.edu/advising/",
        ],
        "coverage": "full",
    },
    {
        "question": "What is the add/drop deadline at BU?",
        "relevant_urls": [
            "https://www.bu.edu/reg/calendars/",
            "https://www.bu.edu/reg/registration/",
        ],
        "coverage": "none",
    },
    {
        "question": "Where can I get free tutoring at BU?",
        "relevant_urls": [
            "https://www.bu.edu/advising/educational-resource-center/",
            "https://www.bu.edu/advising/",
        ],
        "coverage": "partial",
    },
    {
        "question": "What subjects does the Educational Resource Center cover?",
        "relevant_urls": ["https://www.bu.edu/advising/educational-resource-center/"],
        # ERC page is 1.5k chars and does not enumerate subjects.
        "coverage": "partial",
    },
    {
        "question": "How do I make an appointment at Student Health Services?",
        "relevant_urls": [
            "https://www.bu.edu/shs/",
            "https://www.bu.edu/shs/medical/",
        ],
        "coverage": "full",
    },
    {
        "question": "Does BU offer mental health counseling?",
        "relevant_urls": [
            "https://www.bu.edu/shs/behavioral-medicine/",
            "https://www.bu.edu/wellness/",
        ],
        "coverage": "full",
    },
    {
        "question": "What are Mugar Library hours?",
        "relevant_urls": [
            "https://www.bu.edu/library/about/hours/",
            "https://www.bu.edu/library/mugar-memorial/",
        ],
        # Hours load client-side; httpx sees navigation chrome only.
        "coverage": "none",
    },
    {
        "question": "Can I book a study room at the BU library?",
        "relevant_urls": [
            "https://www.bu.edu/library/mugar-memorial/",
            "https://www.bu.edu/library/services/",
        ],
        "coverage": "full",
    },
    {
        "question": "How do I apply for financial aid at BU?",
        "relevant_urls": [
            "https://www.bu.edu/finaid/",
            "https://www.bu.edu/finaid/how-aid-works/",
        ],
        "coverage": "full",
    },
    {
        "question": "How does BU housing lottery work?",
        "relevant_urls": [
            "https://www.bu.edu/housing/undergrad/",
            "https://www.bu.edu/housing/",
        ],
        # "lottery" appears nowhere in the corpus.
        "coverage": "none",
    },
    {
        "question": "How do I register for disability accommodations at BU?",
        "relevant_urls": [
            "https://www.bu.edu/disability/accommodations/",
            "https://www.bu.edu/disability/",
        ],
        "coverage": "full",
    },
    {
        "question": "How do I apply for study abroad at BU?",
        "relevant_urls": ["https://www.bu.edu/abroad/"],
        "coverage": "full",
    },
]
