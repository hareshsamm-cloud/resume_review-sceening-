# Programmatic software companies database with 200+ entries split by tier

# Raw lists of companies: (Name, Initials)
HIGH_TIER_RAW = [
    ("Google", "GO"), ("Microsoft", "MS"), ("Amazon", "AM"),
    ("Netflix", "NF"), ("Meta", "ME"), ("Apple", "AP"),
    ("NVIDIA", "NV"), ("OpenAI", "OA"), ("Stripe", "ST"),
    ("Snowflake", "SF"), ("Databricks", "DB"), ("Tesla", "TS"),
    ("SpaceX", "SX"), ("Uber", "UB"), ("Airbnb", "AB"),
    ("ByteDance", "BD"), ("TikTok", "TT"), ("Palantir", "PL"),
    ("GitHub", "GH"), ("GitLab", "GL"), ("Atlassian", "AT"),
    ("Coinbase", "CB"), ("Figma", "FG"), ("Oracle", "OR"),
    ("Salesforce", "SF"), ("Adobe", "AD"), ("Spotify", "SP"),
    ("Zoom", "ZM"), ("Slack", "SL"), ("Cloudflare", "CF"),
    ("Datadog", "DD"), ("MongoDB", "MD"), ("Elastic", "EL"),
    ("Okta", "OK"), ("Twilio", "TW"), ("Unity", "UN"),
    ("Roblox", "RX"), ("Shopify", "SH"), ("LinkedIn", "LI"),
    ("Pinterest", "PR"), ("Snap", "SN"), ("X Corp", "XX"),
    ("Reddit", "RD"), ("Dropbox", "DP"), ("ZoomInfo", "ZI"),
    ("CrowdStrike", "CS"), ("Splunk", "SP"), ("VMware", "VM"),
    ("Intel", "IN"), ("AMD", "MD"), ("Qualcomm", "QC"),
    ("Broadcom", "BC"), ("Cisco Systems", "CI"), ("IBM", "IB"),
    ("Juniper Networks", "JN"), ("ARM", "AR"), ("Micron", "MC"),
    ("ASML", "AS"), ("Applied Materials", "AM"), ("TSMC", "TS"),
    ("Synopsys", "SY"), ("Cadence", "CD"), ("Autodesk", "AU"),
    ("ServiceNow", "SN"), ("Workday", "WD"), ("Palo Alto Networks", "PA"),
    ("Fortinet", "FN"), ("Dynatrace", "DT"), ("Akamai", "AK"),
    ("Automattic", "AU")
]

MID_TIER_RAW = [
    ("HubSpot", "HS"), ("Mailchimp", "MC"), ("Wix", "WX"),
    ("Squarespace", "SQ"), ("GoDaddy", "GD"), ("Wayfair", "WF"),
    ("Zillow", "ZL"), ("Yelp", "YP"), ("TripAdvisor", "TA"),
    ("Expedia", "EX"), ("Booking.com", "BK"), ("Lyft", "LF"),
    ("DoorDash", "DD"), ("Instacart", "IC"), ("Etsy", "ET"),
    ("eBay", "EB"), ("PayPal", "PP"), ("Robinhood", "RH"),
    ("SoFi", "SF"), ("Plaid", "PD"), ("Affirm", "AF"),
    ("Gusto", "GT"), ("Rippling", "RP"), ("Box", "BX"),
    ("Zendesk", "ZD"), ("Asana", "AS"), ("Monday.com", "MN"),
    ("ClickUp", "CU"), ("Notion", "NT"), ("Canva", "CV"),
    ("DocuSign", "DS"), ("Webflow", "WF"), ("Discord", "DC"),
    ("Twitch", "TW"), ("Steam", "ST"), ("Epic Games", "EG"),
    ("Cloudera", "CD"), ("Confluent", "CF"), ("HashiCorp", "HC"),
    ("PagerDuty", "PD"), ("New Relic", "NR"), ("Fastly", "FL"),
    ("F5 Networks", "F5"), ("Citrix", "CX"), ("NetApp", "NA"),
    ("Priceline", "PL"), ("Groupon", "GR"), ("Shutterstock", "SS"),
    ("Vimeo", "VM"), ("Medium", "MD"), ("Substack", "SB"),
    ("Ghost", "GH"), ("Patreon", "PT"), ("Kickstarter", "KS"),
    ("Eventbrite", "EV"), ("Meetup", "MU"), ("Foursquare", "FS"),
    ("Mapbox", "MB"), ("Strava", "SV"), ("Duolingo", "DL"),
    ("Coursera", "CR"), ("Udemy", "UD"), ("edX", "ED"),
    ("Kaggle", "KG"), ("HackerRank", "HR"), ("LeetCode", "LC"),
    ("Stack Overflow", "SO"), ("Quora", "QR"), ("Prezi", "PZ"),
    ("Scribd", "SC")
]

LOW_TIER_RAW = [
    ("Infosys", "IN"), ("TCS", "TC"), ("Wipro", "WP"),
    ("Cognizant", "CG"), ("Accenture", "AC"), ("Capgemini", "CP"),
    ("Tech Mahindra", "TM"), ("HCL Tech", "HC"), ("Mindtree", "MT"),
    ("LTI Mindtree", "LT"), ("Hexaware", "HW"), ("Mphasis", "MP"),
    ("Genpact", "GP"), ("DXC Technology", "DX"), ("NTT Data", "NT"),
    ("Fujitsu", "FJ"), ("NEC", "NE"), ("Hitachi", "HT"),
    ("Toshiba", "TB"), ("Sony", "SN"), ("Panasonic", "PN"),
    ("Sharp", "SP"), ("Kyocera", "KC"), ("Murata", "MR"),
    ("TDK", "TD"), ("Keyence", "KY"), ("Fanuc", "FN"),
    ("Omron", "OM"), ("Yaskawa", "YS"), ("Yokogawa", "YK"),
    ("Advantest", "AD"), ("Tokyo Electron", "TE"), ("Canon", "CN"),
    ("Nikon", "NK"), ("Olympus", "OL"), ("Ricoh", "RC"),
    ("Seiko", "SK"), ("Epson", "EP"), ("Casio", "CS"),
    ("Brother Industries", "BI"), ("Konica Minolta", "KM"), ("Fujifilm", "FF"),
    ("Pioneer", "PI"), ("Yamaha", "YM"), ("Roland", "RL"),
    ("Cisco Systems", "CS"), ("Juniper", "JP"), ("Broadcom Corp", "BC"),
    ("HP Enterprise", "HP"), ("Dell Technologies", "DL"), ("Lenovo Group", "LV"),
    ("Cisco Meraki", "CM"), ("Micro Focus", "MF"), ("Software AG", "SA"),
    ("Sopra Steria", "SS"), ("Atea", "AT"), ("Tietoevry", "TE"),
    ("CGI Group", "CG"), ("Atos", "AS"), ("Altran", "AL"),
    ("Informatica", "IF"), ("Progress Software", "PS"), ("Quest Software", "QS"),
    ("SolarWinds", "SW"), ("NetSuite", "NS"), ("Infor", "IF"),
    ("Epicor", "EP"), ("Sage Group", "SG"), ("Xero", "XR"),
    ("QuickBooks", "QB")
]

# Programmatic details for matching and rendering
SKILL_PRESETS = {
    "High": ["System Design", "Algorithms", "Python", "Go", "Kubernetes", "AWS", "Machine Learning", "React", "TypeScript"],
    "Mid": ["Python", "JavaScript", "React", "Node.js", "SQL", "Git", "Docker", "APIs", "HTML", "CSS"],
    "Low": ["Java", "SQL", "C++", "HTML", "CSS", "Excel", "Data Structures", "Testing", "Git"]
}

SALARY_PRESETS = {
    "High": "$135k - $210k / yr",
    "Mid": "$85k - $130k / yr",
    "Low": "$45k - $75k / yr"
}

EXP_PRESETS = {
    "High": "3-6 Years",
    "Mid": "1-3 Years",
    "Low": "0-1 Years"
}

GPAS = {
    "High": "3.5 / 4.0",
    "Mid": "3.0 / 4.0",
    "Low": "No Minimum"
}

ROUNDS = {
    "High": "5 Tech Rounds (OA + System Design + Live Coding)",
    "Mid": "3 Rounds (OA + Tech Interview + HR)",
    "Low": "2 Rounds (Aptitude Test + General Interview)"
}

COMPANIES_DATABASE = []

def generate_database():
    global COMPANIES_DATABASE
    if COMPANIES_DATABASE:
        return COMPANIES_DATABASE
        
    import random
    
    # Process High Tier
    for i, (name, initials) in enumerate(HIGH_TIER_RAW):
        random.seed(i + 100)
        skills = random.sample(SKILL_PRESETS["High"], 5)
        COMPANIES_DATABASE.append({
            "id": f"high-{i}",
            "name": name,
            "initials": initials,
            "tier": "High",
            "tier_color": "green",
            "skills": skills,
            "experience": EXP_PRESETS["High"],
            "salary": SALARY_PRESETS["High"],
            "gpa": GPAS["High"],
            "rounds": ROUNDS["High"],
            "description": f"Tier-1 industry leader. Specializes in advanced engineering systems, cloud scale deployments, and highly complex technical solutions."
        })
        
    # Process Mid Tier
    for i, (name, initials) in enumerate(MID_TIER_RAW):
        random.seed(i + 200)
        skills = random.sample(SKILL_PRESETS["Mid"], 5)
        COMPANIES_DATABASE.append({
            "id": f"mid-{i}",
            "name": name,
            "initials": initials,
            "tier": "Mid",
            "tier_color": "orange",
            "skills": skills,
            "experience": EXP_PRESETS["Mid"],
            "salary": SALARY_PRESETS["Mid"],
            "gpa": GPAS["Mid"],
            "rounds": ROUNDS["Mid"],
            "description": f"Mid-tier tech accelerator. Specializes in high growth consumer platforms, modern web architecture, and agile product feature deliveries."
        })
        
    # Process Low Tier
    for i, (name, initials) in enumerate(LOW_TIER_RAW):
        random.seed(i + 300)
        skills = random.sample(SKILL_PRESETS["Low"], 5)
        COMPANIES_DATABASE.append({
            "id": f"low-{i}",
            "name": name,
            "initials": initials,
            "tier": "Low",
            "tier_color": "red",
            "skills": skills,
            "experience": EXP_PRESETS["Low"],
            "salary": SALARY_PRESETS["Low"],
            "gpa": GPAS["Low"],
            "rounds": ROUNDS["Low"],
            "description": f"IT consultancy and global software services provider. Focuses on system maintenance, operations support, and enterprise software rollouts."
        })
        
    return COMPANIES_DATABASE

# Run initialization
generate_database()
