# TriageAI: 3-minute demo script

**Setup (before the demo):** open the app (Hugging Face Space or `http://localhost:7860`), type a reviewer name such as `Asha (Warden)` in the **Reviewer** field of the floating navigation dock, and keep this script open on a second screen. The queue is pre-seeded with 400 synthetic complaints. Figures below come from the offline mode; with an Anthropic key the summary wording and confidence differ slightly.

---

### 0:00 – 0:20 · The problem

> "Campus and city help desks get hundreds of complaints a week: in English, Hinglish, Telugu-English, full of typos, and often five people reporting the same broken thing. TriageAI reads each one, works out what and how urgent it is, groups duplicates, and recommends who should handle it. It never acts on its own; a person decides."

Show the **Queue**: Critical items at the top (the only red in the app), then High, Medium and Low in deepening sky blue, sorted by urgency and then by how long each complaint has waited.

### 0:20 – 1:00 · Submit a messy complaint

Click **Submit** in the dock and paste:

```
yaar GH-2 mein kal raat se light nahi hai!!! generator bhi on nahi kiya, phone laptop sab dead.
mera naam Sneha Reddy hai 98480 12345 pls jaldi karo
```

Set **Location** to `Girls Hostel 2` (pick it from the suggestions), then click **Submit**.

Point out on the inline result:

- **Masked text:** the name and phone number are now `[NAME]` and `[PHONE]`. That masked text is all the AI ever sees.
- **Structured result:** *Electricity / power outage*, a one-line English summary, department *Electrical Maintenance*, a 4-hour SLA and the standard next action from the routing table.
- **Confidence:** about 0.73. Under 0.60 it would go to the *Needs manual triage* queue instead of a department.
- **Duplicates:** *Joined incident #…, now 5 reports.*

### 1:00 – 1:40 · One incident, not five tickets

Click **Open the full record to review it**.

- At the top: *"AI suggestion only. Human decision required."*
- The line under the title reads *incident #… with 5 reports*.
- Under **Similar and duplicate complaints**, an earlier Hinglish report of the same outage shows *86% · likely duplicate · same incident*. Similar outages in *other* buildings are listed as *related* only: same issue, different place, different incident.

### 1:40 – 2:10 · Watch urgency escalate

In the floating decision panel on the right, read the **Urgency** line out loud:

> "Score 66/100 · severity 3/5 (disruptive) (+46), **5 reports of the same incident (+20)**."

> "With four reports this outage scored 54, which is Medium. The fifth report adds 20 points and the whole incident moves to High; every pending report in it is raised with it. If anyone had written *electric shock* or *fire*, a safety rule would force Critical no matter what the model said."

Optionally open one of the earlier reports from the similar list: its urgency now reads High too, with the note *Raised to High: a linked report in the same incident is High.*

### 2:10 – 2:40 · The reviewer decides

- In the decision panel, click **Edit**. Four dropdowns appear: category, sub-issue, urgency and department.
- Change **Department** to `Hostel Warden Office` (the warden coordinates the generator in this hostel) and click **Save edit**.
- The **Decision** line now reads *edited by Asha (Warden)*, and **History** (left side) shows the old and new department next to the AI's original suggestion.
- Mention that **Reject** and **Merge** ask for confirmation, and that nothing is sent to any department automatically.

### 2:40 – 3:00 · Close on the numbers

Click **Analytics** in the dock:

- Category and urgency distributions, and the largest duplicate incidents.
- **Human agreement:** the share of suggestions approved without changes. The edit you just made shows up here.
- **Bias check:** outcomes by writing style (formal, casual, Hinglish, Telugu-English) and the rewrite test, where urgency must stay the same when one complaint is rewritten in different tones and dialects.
- **Offline evaluation:** category accuracy, urgency macro-F1, duplicate precision and recall, routing accuracy.

> "Synthetic data, personal data masked before the AI sees anything, a human on every decision, and every decision in the audit log. That's TriageAI."

Optionally finish on **Audit Log** to show the edit with timestamp, reviewer, old value and new value.
