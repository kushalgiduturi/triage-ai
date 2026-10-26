"""Scenario bank used by generate_synthetic.py.

Every entry describes one sub_issue from config/departments.yaml with:
  loc_types  - which kinds of places this issue plausibly happens in
  en         - core sentences in plain English ({loc} is replaced by a location alias)
  hi         - Hinglish variants
  te         - Telugu-English (Tenglish) variants
  details    - optional extra English detail sentences
  escalator  - optional (sentence, urgency) pair that makes an instance more urgent

All content is synthetic. No real people, places, or incidents are described.
"""

from __future__ import annotations

LOCATIONS: dict[str, dict] = {
    # name: {type, aliases used inside complaint text}
    "Block A Boys Hostel": {"type": "hostel", "aliases": ["Block A hostel", "A-block hostel", "boys hostel block A", "BH-A"]},
    "Block C Boys Hostel": {"type": "hostel", "aliases": ["Block C hostel", "C block", "boys hostel C", "BH-C"]},
    "Girls Hostel 1": {"type": "hostel", "aliases": ["Girls Hostel 1", "GH-1", "girls hostel one", "ladies hostel 1"]},
    "Girls Hostel 2": {"type": "hostel", "aliases": ["Girls Hostel 2", "GH-2", "girls hostel two", "new girls hostel"]},
    "PG Hostel": {"type": "hostel", "aliases": ["PG hostel", "postgraduate hostel", "PG block hostel"]},
    "CSE Block": {"type": "academic", "aliases": ["CSE block", "computer science building", "CSE dept building"]},
    "ECE Block": {"type": "academic", "aliases": ["ECE block", "electronics building", "ECE department"]},
    "Mechanical Workshop": {"type": "academic", "aliases": ["mech workshop", "mechanical workshop", "workshop shed"]},
    "Central Library": {"type": "academic", "aliases": ["central library", "the library", "main library"]},
    "Main Mess": {"type": "mess", "aliases": ["main mess", "the mess", "mess hall 1", "big mess"]},
    "North Mess": {"type": "mess", "aliases": ["north mess", "mess hall 2", "new mess"]},
    "Food Court": {"type": "mess", "aliases": ["food court", "canteen", "the canteen near library"]},
    "Admin Building": {"type": "admin", "aliases": ["admin building", "administrative block", "admin office"]},
    "Exam Cell Office": {"type": "admin", "aliases": ["exam cell", "examination branch", "exam section"]},
    "Gate 2 Road": {"type": "road", "aliases": ["road near Gate 2", "Gate 2 road", "gate no 2 stretch"]},
    "Ring Road Stretch": {"type": "road", "aliases": ["campus ring road", "ring road", "the main ring road"]},
    "Parking Lot B": {"type": "road", "aliases": ["parking lot B", "two-wheeler parking B", "parking B"]},
    "Ward 7 Colony": {"type": "public", "aliases": ["Ward 7 colony", "ward-7", "colony in ward 7"]},
    "Sector 4 Market": {"type": "public", "aliases": ["Sector 4 market", "sector-4 market area", "market in sector 4"]},
    "Bus Stand Road": {"type": "road", "aliases": ["bus stand road", "road to bus stand", "busstand road"]},
    "Sports Complex": {"type": "public", "aliases": ["sports complex", "indoor stadium", "sports ground"]},
    "Medical Centre": {"type": "public", "aliases": ["medical centre", "health centre", "dispensary"]},
}

SCENARIOS: dict[str, dict] = {
    # ---------------- Water and Plumbing ----------------
    "no_water_supply": {
        "category": "Water and Plumbing",
        "loc_types": ["hostel", "public", "academic"],
        "en": [
            "There is no water supply in {loc} since this morning.",
            "Taps in {loc} have been completely dry and we cannot even flush the toilets.",
            "Water is not coming in {loc}, the overhead tank seems to be empty.",
        ],
        "hi": [
            "{loc} mein subah se paani nahi aa raha hai, bathroom use karna mushkil ho gaya hai.",
            "Bhai {loc} me ek boond paani nahi hai, tank khali pada hai.",
        ],
        "te": [
            "{loc} lo morning nunchi water raavatledu, bathroom ki kuda neellu levu.",
            "{loc} lo taps anni dry ga unnayi, tank empty ayindi anukunta.",
        ],
        "details": ["Nobody has informed us about any maintenance work.", "Students are buying water bottles from outside."],
        "escalator": ("We have had no water for more than 2 days now.", "Critical"),
    },
    "leakage": {
        "category": "Water and Plumbing",
        "loc_types": ["hostel", "academic", "admin"],
        "en": [
            "A pipe is leaking continuously near the washroom in {loc}.",
            "Water is dripping from the ceiling of the corridor in {loc}.",
            "The tap in {loc} washroom does not close and water is getting wasted all day.",
        ],
        "hi": [
            "{loc} ke washroom ke paas pipe se lagatar paani leak ho raha hai.",
            "{loc} mein tap band hi nahi hota, poora din paani waste ho raha hai.",
        ],
        "te": [
            "{loc} lo washroom daggara pipe nunchi water leak avtundi continuous ga.",
            "{loc} corridor lo ceiling nunchi neellu kaaruthunnayi.",
        ],
        "details": ["The floor is slippery because of this.", "It has been like this for a week."],
    },
    "contaminated_water": {
        "category": "Water and Plumbing",
        "loc_types": ["hostel", "mess", "academic"],
        "en": [
            "The drinking water in {loc} is coming out yellow and smells bad.",
            "The RO water at {loc} tastes muddy and has particles floating in it.",
            "Dirty brown water is coming from the drinking water taps in {loc}.",
        ],
        "hi": [
            "{loc} ka peene ka paani peela aur badboodar aa raha hai.",
            "{loc} ke RO ka paani ganda hai, usme kachra tair raha hai.",
        ],
        "te": [
            "{loc} lo drinking water yellow colour lo vastundi, smell kuda chala bad ga undi.",
            "{loc} RO water lo mud laga undi, taagalekapothunnam.",
        ],
        "details": ["A few students complained of stomach ache after drinking it.", "We are scared to drink it."],
    },
    "blocked_drain": {
        "category": "Water and Plumbing",
        "loc_types": ["hostel", "mess", "public"],
        "en": [
            "The bathroom drain in {loc} is blocked and dirty water is standing on the floor.",
            "Drainage in {loc} is choked and water is not flowing out.",
            "The sink drain at {loc} is clogged, water stays in the basin for hours.",
        ],
        "hi": [
            "{loc} ke bathroom ka drain block ho gaya hai, ganda paani jama hai.",
            "{loc} mein naali jam ho gayi hai, paani nikal hi nahi raha.",
        ],
        "te": [
            "{loc} bathroom drain block ayindi, dirty water floor meeda nilichindi.",
            "{loc} lo drainage choke ayyindi, neellu bayataki povatledu.",
        ],
        "details": ["It is starting to smell really bad.", "Mosquitoes are breeding there."],
    },
    "water_cooler_broken": {
        "category": "Water and Plumbing",
        "loc_types": ["academic", "hostel", "public"],
        "en": [
            "The water cooler on the second floor of {loc} is not working.",
            "The drinking water dispenser in {loc} has stopped cooling and leaks a bit.",
            "Water cooler at {loc} is out of order for many days.",
        ],
        "hi": [
            "{loc} ke second floor ka water cooler kharab hai.",
            "{loc} mein water cooler kaam nahi kar raha, garam paani aa raha hai.",
        ],
        "te": [
            "{loc} second floor lo water cooler pani cheyyatledu.",
            "{loc} lo cooler repair lo undi chala rojulu nunchi, cool water raavatledu.",
        ],
        "details": ["We have to walk to another building to get water."],
    },
    # ---------------- Electricity ----------------
    "power_outage": {
        "category": "Electricity",
        "loc_types": ["hostel", "academic", "public"],
        "en": [
            "There has been a complete power cut in {loc} for the last 5 hours.",
            "No electricity in {loc} since last night and the generator is not switched on.",
            "Power went off in the entire {loc} and has not come back.",
        ],
        "hi": [
            "{loc} mein pichle 5 ghante se light nahi hai.",
            "Kal raat se {loc} mein bijli gayi hui hai, generator bhi on nahi kiya.",
        ],
        "te": [
            "{loc} lo last 5 hours nunchi current ledu.",
            "Ninna raatri nunchi {loc} lo power ledu, generator kuda on cheyyaledu.",
        ],
        "details": ["Our phones and laptops are all dead.", "It is very hot and nobody can sleep."],
    },
    "electric_shock_hazard": {
        "category": "Electricity",
        "loc_types": ["hostel", "academic", "mess"],
        "en": [
            "A student got an electric shock from the switchboard in {loc}.",
            "The metal door frame in {loc} is giving electric shock when touched.",
            "Exposed live wires near the water cooler in {loc}, someone got an electric shock today.",
        ],
        "hi": [
            "{loc} ke switchboard se ek student ko electric shock laga.",
            "{loc} mein darwaze ke frame ko chhoone par current lag raha hai, electric shock aata hai.",
        ],
        "te": [
            "{loc} lo switchboard touch cheste electric shock kodutundi, oka student ki shock tagilindi.",
            "{loc} lo water cooler daggara live wires open ga unnayi, evariko electric shock vachindi.",
        ],
        "details": ["Please send someone before someone gets seriously hurt.", "The area is still not cordoned off."],
    },
    "sparking_wiring": {
        "category": "Electricity",
        "loc_types": ["hostel", "academic", "admin"],
        "en": [
            "The switchboard in {loc} is sparking whenever we plug something in.",
            "There is sparking from the wiring near the corridor light in {loc}.",
            "Loose wiring in {loc} keeps sparking and making a burning smell.",
        ],
        "hi": [
            "{loc} ka switchboard plug lagate hi spark karta hai.",
            "{loc} ke corridor mein wiring se chingaari nikal rahi hai.",
        ],
        "te": [
            "{loc} lo switchboard lo plug pedithe sparks vastunnayi.",
            "{loc} corridor lo wiring nunchi sparking vastundi, burning smell kuda vastundi.",
        ],
        "details": ["We have switched off the main for now."],
        "escalator": ("Now there is smoke and a small fire started near the board.", "Critical"),
    },
    "lights_fans_not_working": {
        "category": "Electricity",
        "loc_types": ["hostel", "academic", "mess"],
        "en": [
            "Two tube lights and the ceiling fan in my room at {loc} are not working.",
            "The fans in the classroom on the first floor of {loc} are not working.",
            "Lights in the {loc} corridor have been off for a week.",
        ],
        "hi": [
            "{loc} mein mere room ka fan aur tube light kaam nahi kar rahe.",
            "{loc} ke classroom ke pankhe band pade hain.",
        ],
        "te": [
            "{loc} lo naa room lo fan and tube light work avvatledu.",
            "{loc} classroom lo fans tiragatledu, chala ukkapoota ga undi.",
        ],
        "details": ["Please replace them when possible."],
    },
    "voltage_fluctuation": {
        "category": "Electricity",
        "loc_types": ["hostel", "academic", "public"],
        "en": [
            "There is heavy voltage fluctuation in {loc}, lights keep dimming and flickering.",
            "Voltage in {loc} keeps going up and down, my charger got burnt.",
            "Frequent voltage drops in {loc} are tripping the lab equipment.",
        ],
        "hi": [
            "{loc} mein voltage baar baar upar neeche ho raha hai, lights flicker kar rahi hain.",
            "{loc} mein voltage fluctuation se mera charger jal gaya.",
        ],
        "te": [
            "{loc} lo voltage fluctuation ekkuva ga undi, lights flicker avtunnayi.",
            "{loc} lo voltage up down avtundi, naa charger burn ayipoyindi.",
        ],
        "details": ["Expensive devices might get damaged."],
    },
    # ---------------- Roads and Infrastructure ----------------
    "potholes_road_damage": {
        "category": "Roads and Infrastructure",
        "loc_types": ["road", "public"],
        "en": [
            "There are big potholes on the {loc} and bikes keep skidding.",
            "The road surface at {loc} is completely broken after the rain.",
            "A huge pothole has formed in the middle of {loc}, it fills with water and is not visible.",
        ],
        "hi": [
            "{loc} par bade bade gaddhe ho gaye hain, bike fisal rahi hai.",
            "Baarish ke baad {loc} ki sadak poori toot gayi hai.",
        ],
        "te": [
            "{loc} meeda pedda potholes unnayi, bikes slip avtunnayi.",
            "Varsham tarvata {loc} road motham damage ayyindi.",
        ],
        "details": ["It is very dangerous at night."],
        "escalator": ("Yesterday a student fell from his bike there and got injured.", "Critical"),
    },
    "streetlight_not_working": {
        "category": "Roads and Infrastructure",
        "loc_types": ["road", "public"],
        "en": [
            "The streetlights along {loc} are not working and it is pitch dark at night.",
            "Three streetlights near {loc} have been off for two weeks.",
            "No street lighting on {loc}, walking back after 8 pm is scary.",
        ],
        "hi": [
            "{loc} ki street lights band hain, raat ko bilkul andhera rehta hai.",
            "{loc} ke paas teen street light do hafte se kharab hain.",
        ],
        "te": [
            "{loc} lo street lights work avvatledu, raatri chala cheekati ga untundi.",
            "{loc} daggara moodu street lights rendu vaaralu nunchi off lo unnayi.",
        ],
        "details": ["Girls feel unsafe walking there."],
    },
    "building_structural_damage": {
        "category": "Roads and Infrastructure",
        "loc_types": ["hostel", "academic", "admin"],
        "en": [
            "Big cracks have appeared on the wall of {loc} and plaster is falling from the ceiling.",
            "A part of the balcony railing in {loc} has broken off.",
            "Ceiling plaster fell in a classroom at {loc}, luckily nobody was sitting there.",
        ],
        "hi": [
            "{loc} ki deewar mein badi daraarein aa gayi hain aur chhat se plaster gir raha hai.",
            "{loc} ki balcony ki railing toot gayi hai.",
        ],
        "te": [
            "{loc} wall lo pedda cracks vachayi, ceiling nunchi plaster padutundi.",
            "{loc} lo balcony railing oka part virigipoyindi.",
        ],
        "details": ["It looks like it could collapse further."],
    },
    "lift_not_working": {
        "category": "Roads and Infrastructure",
        "loc_types": ["hostel", "academic", "admin"],
        "en": [
            "The lift in {loc} has not been working for three days.",
            "Elevator at {loc} is stuck on the ground floor and shows an error.",
            "The only lift in {loc} is out of order.",
        ],
        "hi": [
            "{loc} ki lift teen din se kharab hai.",
            "{loc} ka elevator ground floor par atka hua hai.",
        ],
        "te": [
            "{loc} lo lift moodu rojulu nunchi pani cheyyatledu.",
            "{loc} elevator ground floor lo struck ayyindi, error chupistundi.",
        ],
        "details": ["Elderly staff and students with heavy bags have to climb six floors."],
        "escalator": ("A wheelchair user cannot reach their classes at all because of this.", "High"),
    },
    "broken_furniture": {
        "category": "Roads and Infrastructure",
        "loc_types": ["hostel", "academic", "mess"],
        "en": [
            "Several benches in {loc} are broken and have nails sticking out.",
            "My cot in {loc} is broken and the cupboard door has come off.",
            "Chairs in {loc} are broken, we sit on the floor.",
        ],
        "hi": [
            "{loc} mein kai bench toote hue hain, keel bahar nikli hai.",
            "{loc} mein mera palang toot gaya hai aur almari ka darwaza nikal gaya.",
        ],
        "te": [
            "{loc} lo chala benches virigipoyayi, mekulu bayataki unnayi.",
            "{loc} lo naa cot broken, cupboard door kuda oodipoyindi.",
        ],
        "details": ["Please send a carpenter."],
    },
    # ---------------- Sanitation and Cleanliness ----------------
    "garbage_not_collected": {
        "category": "Sanitation and Cleanliness",
        "loc_types": ["hostel", "public", "mess"],
        "en": [
            "Garbage has not been collected from {loc} for four days and bins are overflowing.",
            "Dustbins near {loc} are full and garbage is spilling on the road.",
            "Nobody has cleared the trash at {loc} this week.",
        ],
        "hi": [
            "{loc} se chaar din se kooda nahi uthaya gaya, dustbin bhar gaye hain.",
            "{loc} ke paas kachra sadak par phail raha hai.",
        ],
        "te": [
            "{loc} lo naalugu rojulu nunchi garbage teesukellaledu, bins full ayyayi.",
            "{loc} daggara chetha road meeda padutundi.",
        ],
        "details": ["Dogs are tearing the bags open.", "The smell is unbearable."],
    },
    "dirty_washrooms": {
        "category": "Sanitation and Cleanliness",
        "loc_types": ["hostel", "academic", "public"],
        "en": [
            "The washrooms in {loc} have not been cleaned for days and smell terrible.",
            "Toilets on the ground floor of {loc} are extremely dirty.",
            "Washrooms at {loc} are filthy, no soap and no cleaning.",
        ],
        "hi": [
            "{loc} ke washroom kai dino se saaf nahi hue, bahut badboo aa rahi hai.",
            "{loc} ke toilet bahut gande hain, sabun bhi nahi hai.",
        ],
        "te": [
            "{loc} lo washrooms clean cheyyatledu chala rojulu nunchi, smell bharinchalekapothunnam.",
            "{loc} ground floor toilets chala dirty ga unnayi.",
        ],
        "details": ["Housekeeping staff do not come regularly."],
    },
    "sewage_overflow": {
        "category": "Sanitation and Cleanliness",
        "loc_types": ["hostel", "public", "road"],
        "en": [
            "Sewage is overflowing from the manhole near {loc} onto the walkway.",
            "The septic line at {loc} has burst and sewage water is spreading.",
            "Sewer water is coming up through the drains in {loc}.",
        ],
        "hi": [
            "{loc} ke paas manhole se sewage bahar beh raha hai.",
            "{loc} mein gutter ka paani upar aa raha hai.",
        ],
        "te": [
            "{loc} daggara manhole nunchi sewage overflow avtundi.",
            "{loc} lo drainage nunchi sewage neellu paiki vastunnayi.",
        ],
        "details": ["People have to walk through it.", "Risk of disease outbreak."],
    },
    "pest_infestation": {
        "category": "Sanitation and Cleanliness",
        "loc_types": ["hostel", "mess", "academic"],
        "en": [
            "{loc} is full of cockroaches and rats at night.",
            "There are bed bugs in almost every room of {loc}.",
            "We saw rats running around in {loc}.",
        ],
        "hi": [
            "{loc} mein raat ko cockroach aur chuhe bhar jaate hain.",
            "{loc} ke har kamre mein khatmal hain.",
        ],
        "te": [
            "{loc} lo raatri cockroaches and elukalu chala unnayi.",
            "{loc} lo prati room lo nallulu unnayi.",
        ],
        "details": ["Pest control was last done months ago."],
    },
    "stray_animals": {
        "category": "Sanitation and Cleanliness",
        "loc_types": ["public", "road", "hostel"],
        "en": [
            "A pack of stray dogs is roaming near {loc} and chasing students.",
            "Stray dogs at {loc} bark and chase two-wheelers at night.",
            "There are many stray dogs around {loc}, people are afraid to walk.",
        ],
        "hi": [
            "{loc} ke paas aawara kutton ka jhund students ka peecha karta hai.",
            "{loc} par raat ko kutte bike walon ke peeche bhaagte hain.",
        ],
        "te": [
            "{loc} daggara stray dogs gumpu ga tirugutunnayi, students ni chase chestunnayi.",
            "{loc} lo raatri kukkalu bikes venaka parigedutunnayi.",
        ],
        "details": ["Please inform animal control."],
        "escalator": ("Today one of the dogs bit a student and he is injured.", "Critical"),
    },
    # ---------------- Hostel and Mess ----------------
    "food_quality": {
        "category": "Hostel and Mess",
        "loc_types": ["mess"],
        "en": [
            "The food at {loc} is consistently undercooked and tasteless.",
            "Rice served at {loc} today was half cooked and the dal was watery.",
            "Food quality in {loc} has gone down badly this month.",
        ],
        "hi": [
            "{loc} ka khana roz kaccha aur bekaar hota hai.",
            "Aaj {loc} mein chawal kacche the aur daal ekdum paani jaisi thi.",
        ],
        "te": [
            "{loc} lo food eppudu undercooked ga untundi, taste ledu.",
            "Ivala {loc} lo rice sagam udikindi, dal neellu laga undi.",
        ],
        "details": ["We pay a lot of mess fees for this.", "Many students skip meals now."],
    },
    "food_poisoning": {
        "category": "Hostel and Mess",
        "loc_types": ["mess"],
        "en": [
            "Many students fell sick with vomiting after dinner at {loc}, looks like food poisoning.",
            "After eating lunch at {loc}, more than ten students have food poisoning symptoms.",
            "Suspected food poisoning: several of us had stomach cramps and vomiting after the meal at {loc}.",
        ],
        "hi": [
            "{loc} mein dinner ke baad bahut students ko ulti ho rahi hai, food poisoning lag raha hai.",
            "{loc} ka lunch khane ke baad das se zyada bachon ko food poisoning ho gaya.",
        ],
        "te": [
            "{loc} lo dinner tinna tarvata chala mandi students ki vomiting, food poisoning anipistundi.",
            "{loc} lunch tinnaka padi mandi kanna ekkuva students ki food poisoning symptoms vachayi.",
        ],
        "details": ["Some were taken to the medical centre.", "Please check the food samples."],
    },
    "mess_hygiene": {
        "category": "Hostel and Mess",
        "loc_types": ["mess"],
        "en": [
            "We found an insect in the curry at {loc} and the plates are not washed properly.",
            "The kitchen at {loc} is dirty and the cooks do not wear gloves or caps.",
            "There was a hair and a small cockroach in the food served at {loc}.",
        ],
        "hi": [
            "{loc} ki sabzi mein keeda mila, plates bhi theek se nahi dhulti.",
            "{loc} ka kitchen bahut ganda hai, cooks gloves nahi pehente.",
        ],
        "te": [
            "{loc} curry lo purugu dorikindi, plates kuda sariga kadagatledu.",
            "{loc} kitchen chala dirty ga undi, cooks gloves veskovatledu.",
        ],
        "details": ["Photos are available if needed."],
    },
    "room_allocation": {
        "category": "Hostel and Mess",
        "loc_types": ["hostel"],
        "en": [
            "I have not been allotted a room in {loc} even after paying the hostel fees.",
            "Three of us have been put in a two-seater room in {loc}, please reallocate.",
            "My room change request for {loc} has been pending for a month.",
        ],
        "hi": [
            "Hostel fees bharne ke baad bhi mujhe {loc} mein room nahi mila.",
            "{loc} mein do logon ke room mein teen ko daal diya hai.",
        ],
        "te": [
            "Hostel fee kattina kuda naaku {loc} lo room allot cheyyaledu.",
            "{loc} lo iddari room lo mugguri ni pettaru, reallocate cheyyandi.",
        ],
        "details": ["The warden asked us to wait but nothing happened."],
    },
    "hostel_maintenance": {
        "category": "Hostel and Mess",
        "loc_types": ["hostel"],
        "en": [
            "The window glass in my room at {loc} is broken and the door lock does not work.",
            "The geyser on the third floor of {loc} has not worked since the semester started.",
            "Common room TV and the washing machine in {loc} are broken.",
        ],
        "hi": [
            "{loc} mein mere room ki khidki ka kaanch toota hai aur lock kaam nahi karta.",
            "{loc} ke teesre floor ka geyser semester start se kharab hai.",
        ],
        "te": [
            "{loc} lo naa room window glass broken, door lock kuda pani cheyyatledu.",
            "{loc} third floor geyser semester start ayinappati nunchi work avvatledu.",
        ],
        "details": ["Caretaker keeps saying it will be fixed tomorrow."],
    },
    # ---------------- IT and WiFi ----------------
    "wifi_down": {
        "category": "IT and WiFi",
        "loc_types": ["hostel", "academic"],
        "en": [
            "WiFi has been completely down in {loc} since yesterday evening.",
            "No internet connectivity in {loc}, the campus WiFi shows connected but no internet.",
            "The WiFi access points in {loc} are not working at all.",
        ],
        "hi": [
            "{loc} mein kal shaam se WiFi bilkul band hai.",
            "{loc} mein WiFi connected dikhata hai par internet nahi chal raha.",
        ],
        "te": [
            "{loc} lo ninna evening nunchi WiFi poorthiga down lo undi.",
            "{loc} lo WiFi connected ani chupistundi kani internet raavatledu.",
        ],
        "details": ["We cannot download lecture material."],
        "escalator": ("We have an online assignment submission deadline tonight.", "High"),
    },
    "slow_internet": {
        "category": "IT and WiFi",
        "loc_types": ["hostel", "academic"],
        "en": [
            "Internet speed in {loc} is extremely slow in the evenings.",
            "The WiFi in {loc} gives less than 1 Mbps, videos do not load.",
            "Campus internet at {loc} keeps disconnecting and is very slow.",
        ],
        "hi": [
            "{loc} mein shaam ko internet bahut slow chalta hai.",
            "{loc} ka WiFi 1 Mbps se bhi kam deta hai, video load hi nahi hoti.",
        ],
        "te": [
            "{loc} lo evening time internet chala slow ga untundi.",
            "{loc} WiFi 1 Mbps kuda raavatledu, videos load avvatledu.",
        ],
        "details": ["It has been like this for weeks."],
    },
    "portal_login_issue": {
        "category": "IT and WiFi",
        "loc_types": ["admin", "academic"],
        "en": [
            "I am unable to log in to the student portal, it says invalid credentials even after reset.",
            "The ERP portal shows an error when I try to register for courses from {loc}.",
            "The fee payment page on the student portal keeps crashing.",
        ],
        "hi": [
            "Student portal mein login nahi ho raha, password reset ke baad bhi invalid bolta hai.",
            "ERP portal par course registration karte waqt error aa raha hai.",
        ],
        "te": [
            "Student portal lo login avvatledu, password reset chesina invalid ani vastundi.",
            "ERP portal lo course registration chesetappudu error vastundi.",
        ],
        "details": ["The last date for registration is close."],
    },
    "lab_computer_fault": {
        "category": "IT and WiFi",
        "loc_types": ["academic"],
        "en": [
            "Half of the computers in the lab at {loc} do not boot.",
            "Systems in the {loc} lab are very slow and the keyboards are broken.",
            "The projector and two PCs in {loc} lab are not working.",
        ],
        "hi": [
            "{loc} lab ke aadhe computer on hi nahi hote.",
            "{loc} lab ke systems bahut slow hain aur keyboard toote hain.",
        ],
        "te": [
            "{loc} lab lo sagam computers boot avvatledu.",
            "{loc} lab systems chala slow, keyboards kuda broken.",
        ],
        "details": ["We have to share one system among three students."],
    },
    "email_account_issue": {
        "category": "IT and WiFi",
        "loc_types": ["admin", "academic"],
        "en": [
            "My college email account has been locked and I am not receiving any mails.",
            "The institute email shows mailbox full even after deleting everything.",
            "I never received my official email ID even after two months of joining.",
        ],
        "hi": [
            "Mera college email account lock ho gaya hai, koi mail nahi aa raha.",
            "Institute email sab delete karne ke baad bhi mailbox full dikhata hai.",
        ],
        "te": [
            "Naa college email account lock ayyindi, mails raavatledu.",
            "Institute email anni delete chesina mailbox full ani chupistundi.",
        ],
        "details": ["Important notices are sent only on email."],
    },
    # ---------------- Safety and Harassment ----------------
    "harassment": {
        "category": "Safety and Harassment",
        "loc_types": ["hostel", "academic", "public", "road"],
        "en": [
            "A group of outsiders has been passing comments and harassing girls near {loc} every evening.",
            "I am being repeatedly harassed and followed by a person near {loc}.",
            "Some men near {loc} made lewd gestures and tried to grab a student, this is harassment.",
        ],
        "hi": [
            "{loc} ke paas kuch log roz shaam ladkiyon ko chhedte hain, yeh harassment hai.",
            "{loc} ke paas ek aadmi mera peecha karta hai aur harass karta hai.",
        ],
        "te": [
            "{loc} daggara konthamandi outsiders prati evening ammayilni harass chestunnaru.",
            "{loc} daggara oka vyakthi nannu follow chesi harass chestunnadu.",
        ],
        "details": ["Please keep my identity confidential.", "We are scared to go out."],
    },
    "ragging": {
        "category": "Safety and Harassment",
        "loc_types": ["hostel"],
        "en": [
            "First year students in {loc} are being ragged by seniors late at night.",
            "Seniors in {loc} forced juniors to do humiliating tasks, this is ragging.",
            "Ragging is happening on the top floor of {loc}, juniors are being threatened.",
        ],
        "hi": [
            "{loc} mein seniors raat ko first year walon ki ragging karte hain.",
            "{loc} mein seniors juniors se zabardasti ulte seedhe kaam karwate hain, ragging ho rahi hai.",
        ],
        "te": [
            "{loc} lo seniors raatri first years ni ragging chestunnaru.",
            "{loc} top floor lo ragging jarugutundi, juniors ni bedirisunnaru.",
        ],
        "details": ["Juniors are too afraid to complain openly."],
    },
    "theft": {
        "category": "Safety and Harassment",
        "loc_types": ["hostel", "academic", "road"],
        "en": [
            "My laptop was stolen from my room in {loc} while I was at class.",
            "Two bicycles were stolen from {loc} last night.",
            "Mobile phones are going missing from {loc}, there have been multiple thefts.",
        ],
        "hi": [
            "Class ke time {loc} mein mere room se laptop chori ho gaya.",
            "Kal raat {loc} se do cycle chori ho gayi.",
        ],
        "te": [
            "Nenu class lo unnappudu {loc} lo naa room nunchi laptop dongatanam jarigindi.",
            "Ninna raatri {loc} nunchi rendu cycles dongilincharu.",
        ],
        "details": ["The CCTV camera there is not working."],
    },
    "fire_hazard": {
        "category": "Safety and Harassment",
        "loc_types": ["hostel", "mess", "academic"],
        "en": [
            "There is a fire in the kitchen area of {loc}, smoke is coming out.",
            "A small fire broke out in the electrical room of {loc}.",
            "Gas leak smell in {loc} kitchen and the fire extinguishers are empty.",
        ],
        "hi": [
            "{loc} ke kitchen mein aag lagi hai, dhuaan nikal raha hai.",
            "{loc} ke kitchen mein gas leak ki smell aa rahi hai aur fire extinguisher khaali hain.",
        ],
        "te": [
            "{loc} kitchen lo fire vachindi, smoke bayataki vastundi.",
            "{loc} kitchen lo gas leak smell vastundi, fire extinguishers empty ga unnayi.",
        ],
        "details": ["Please send the fire safety team immediately."],
    },
    "unsafe_area": {
        "category": "Safety and Harassment",
        "loc_types": ["road", "public"],
        "en": [
            "The area behind {loc} is isolated and unsafe, there is no security guard after dark.",
            "Unknown people gather and drink near {loc} at night, it feels unsafe.",
            "The boundary wall near {loc} is broken and outsiders walk in freely.",
        ],
        "hi": [
            "{loc} ke peeche ka area sunsaan aur unsafe hai, raat ko guard nahi hota.",
            "{loc} ke paas raat ko anjaan log sharaab peete hain, darr lagta hai.",
        ],
        "te": [
            "{loc} venaka area chala isolated, raatri security guard undadu.",
            "{loc} daggara raatri teliyani vallu taagutu untaru, unsafe ga undi.",
        ],
        "details": ["Please increase patrolling."],
    },
    # ---------------- Academic and Administrative ----------------
    "exam_schedule_clash": {
        "category": "Academic and Administrative",
        "loc_types": ["admin", "academic"],
        "en": [
            "Two of my exams are scheduled at the same time in the new timetable.",
            "The exam timetable published by {loc} has a clash between an elective and a core paper.",
            "The revised exam schedule puts three papers on the same day.",
        ],
        "hi": [
            "Naye timetable mein mere do exam ek hi time par hain.",
            "{loc} ke timetable mein elective aur core paper ka clash hai.",
        ],
        "te": [
            "Kotha timetable lo naa rendu exams same time lo unnayi.",
            "{loc} ichina timetable lo elective and core paper clash ayyayi.",
        ],
        "details": ["Many students in my section have the same problem."],
    },
    "fee_refund": {
        "category": "Academic and Administrative",
        "loc_types": ["admin"],
        "en": [
            "I applied for a caution deposit refund three months ago and have not received it.",
            "Excess fee paid twice through the portal has not been refunded yet.",
            "My scholarship amount was deducted from fees but the refund is still pending at {loc}.",
        ],
        "hi": [
            "Teen mahine pehle caution deposit refund apply kiya tha, abhi tak nahi mila.",
            "Portal par do baar fees kat gayi, refund abhi tak nahi aaya.",
        ],
        "te": [
            "Moodu nelala kritam caution deposit refund ki apply chesanu, inka raaledu.",
            "Portal lo rendu saarlu fee cut ayyindi, refund inka raaledu.",
        ],
        "details": ["Nobody at the counter gives a clear answer."],
    },
    "certificate_delay": {
        "category": "Academic and Administrative",
        "loc_types": ["admin"],
        "en": [
            "My bonafide certificate request at {loc} has been pending for three weeks.",
            "I have not received my transcripts even after paying the fee a month ago.",
            "The provisional certificate is delayed and {loc} keeps asking me to come back later.",
        ],
        "hi": [
            "{loc} mein bonafide certificate ki request teen hafte se pending hai.",
            "Ek mahine pehle fees bharne ke baad bhi transcript nahi mila.",
        ],
        "te": [
            "{loc} lo bonafide certificate request moodu vaaralu nunchi pending lo undi.",
            "Nela kritam fee kattina kuda transcripts raaledu.",
        ],
        "details": ["I have visited the office four times."],
        "escalator": ("I need it urgently for my visa interview next week.", "Medium"),
    },
    "attendance_error": {
        "category": "Academic and Administrative",
        "loc_types": ["academic", "admin"],
        "en": [
            "My attendance is shown as 40 percent on the portal though I attended all classes.",
            "Attendance for the whole section was not uploaded for last month.",
            "I was marked absent for days I was on official sports duty.",
        ],
        "hi": [
            "Saari classes attend karne ke baad bhi portal par meri attendance 40 percent dikha rahi hai.",
            "Pichle mahine ki poore section ki attendance upload nahi hui.",
        ],
        "te": [
            "Anni classes ki vellina portal lo naa attendance 40 percent chupistundi.",
            "Last month motham section attendance upload cheyyaledu.",
        ],
        "details": ["I may be detained from exams because of this."],
    },
    "faculty_conduct": {
        "category": "Academic and Administrative",
        "loc_types": ["academic"],
        "en": [
            "A faculty member in {loc} regularly skips classes and does not complete the syllabus.",
            "One lecturer in {loc} insults students in class and refuses to answer doubts.",
            "Internal marks in {loc} were given unfairly without showing answer sheets.",
        ],
        "hi": [
            "{loc} ke ek faculty roz class chhod dete hain aur syllabus poora nahi karte.",
            "{loc} mein ek lecturer class mein students ki insult karte hain.",
        ],
        "te": [
            "{loc} lo oka faculty classes ki raavatledu, syllabus complete cheyyatledu.",
            "{loc} lo oka lecturer class lo students ni insult chestaru.",
        ],
        "details": ["Please keep this complaint anonymous."],
    },
}

# Opening / closing phrases by style. Kept small on purpose; variety comes from combinations.
OPENERS = {
    "formal": ["Respected Sir/Madam,", "Dear Grievance Cell,", "To the concerned authority,", "I would like to report an issue."],
    "casual": ["hi,", "hello team", "guys pls look into this", "ok so"],
    "hi": ["Sir,", "Namaste sir,", "Bhai log,", "Respected sir,"],
    "te": ["Sir,", "Namaskaram sir,", "Hello sir,", "Andi,"],
}
CLOSERS = {
    "formal": ["Kindly take necessary action at the earliest.", "I request you to resolve this soon.", "Thank you for your attention."],
    "casual": ["pls fix asap", "plz do something!!", "this is so annoying", "thanks"],
    "hi": ["Jaldi action lijiye please.", "Kripya jaldi theek karwaiye.", "Bahut pareshani ho rahi hai."],
    "te": ["Twaraga action teesukondi please.", "Konchem fast ga fix cheyyandi.", "Chala problem ga undi sir."],
}

FAKE_FIRST = ["Aarav", "Priya", "Rahul", "Sneha", "Kiran", "Divya", "Arjun", "Meena", "Vikram", "Lakshmi", "Rohan", "Anjali", "Suresh", "Kavya", "Naveen", "Pooja"]
FAKE_LAST = ["Sharma", "Reddy", "Kumar", "Rao", "Patel", "Iyer", "Naidu", "Verma", "Gupta", "Varma", "Singh", "Menon"]
