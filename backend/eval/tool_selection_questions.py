# 20 test cases for tool-selection evaluation of the ReAct agent.
# Each case has a message plus the tool(s) the agent should call.
# expected_params (optional) checks that key arguments were extracted correctly
# for one of the called tools.

TOOL_TEST_CASES = [
    # Places — single tool
    {
        "message": "I have 25 minutes near CDS, where can I eat?",
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"location": "CDS", "place_type": "dining"}},
    },
    {
        "message": "Find me a quiet study spot near CAS with outlets",
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"location": "CAS", "place_type": "study"}},
    },
    {
        "message": "Where can I print near GSU?",
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"location": "GSU", "place_type": "printer"}},
    },
    {
        "message": "What's a good place to study near Questrom with outlets and coffee?",
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"location": "Questrom", "place_type": "study"}},
    },
    {
        "message": "Is there a library near West Campus?",
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"place_type": "library"}},
    },

    # BU resources — single tool
    {
        "message": "How do I apply for OPT as an F-1 student?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "What is CPT and how is it different from OPT?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "How do I drop a class at BU?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "Where can I get free tutoring at BU?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "How do I apply for financial aid at BU?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "How does BU housing lottery work?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "I'm an international student — where's the ISSO office?",
        "expected_tools": ["search_bu_resource"],
    },
    {
        "message": "Where can I get academic advising in CAS?",
        "expected_tools": ["search_bu_resource"],
    },

    # Events — single tool
    {
        "message": "Any AI or startup events this week?",
        "expected_tools": ["get_events"],
    },
    {
        "message": "What hackathons are happening this month?",
        "expected_tools": ["get_events"],
    },
    {
        "message": "Are there any wellness events I could check out?",
        "expected_tools": ["get_events"],
    },
    {
        "message": "What career fairs are coming up?",
        "expected_tools": ["get_events"],
    },
    {
        "message": "Any AI events or hackathons I should check out near Agganis?",
        "expected_tools": ["get_events"],
    },

    # Multi-tool — the interesting cases
    {
        "message": "I have an hour before my AI event near CDS — where should I grab coffee, and what's the event about?",
        "expected_tools": ["get_nearby_places", "get_events"],
    },
    {
        "message": "I need a quiet study spot near CAS, and separately I want to know how to book a group study room at the library",
        "expected_tools": ["get_nearby_places", "search_bu_resource"],
    },

    # Multi-turn — only the final turn is scored. Each one is deliberately
    # ambiguous on its own, so passing requires carrying context from the
    # earlier turn rather than guessing from the words in the last message.
    {
        "turns": [
            "Find me a quiet study spot near CAS",
            "what about closer to Questrom instead?",
        ],
        "expected_tools": ["get_nearby_places"],
        # "study" and "quiet" appear only in turn 1.
        "expected_params": {"get_nearby_places": {"location": "Questrom", "place_type": "study"}},
    },
    {
        "turns": [
            "Where can I eat near CDS?",
            "anywhere quieter?",
        ],
        "expected_tools": ["get_nearby_places"],
        "expected_params": {"get_nearby_places": {"place_type": "dining"}},
    },
    {
        "turns": [
            "How do I apply for OPT as an F-1 student?",
            "and what about CPT?",
        ],
        "expected_tools": ["search_bu_resource"],
    },
    {
        "turns": [
            "What is the Educational Resource Center?",
            "where is it located?",
        ],
        "expected_tools": ["search_bu_resource"],
    },
    {
        "turns": [
            "Any AI events this week?",
            "what about startup ones?",
        ],
        "expected_tools": ["get_events"],
    },
]
