# Demo Script — 2-Minute Screen Recording

*Read naturally while recording. Pause briefly at each timestamp.*

---

**[0:00 – 0:15] Introduction**

"This is an AI agent I built that turns a plain-English request into a dashboard. You describe what you want to see, and the agent figures out what data to pull, how to aggregate it, and builds you an interactive chart — no SQL, no code required."

---

**[0:15 – 0:45] Vague request → clarifying questions**

*[Type "Show me claims" into the text area and click Build My Dashboard]*

"I'm going to start with a deliberately vague request — 'Show me claims' — to show how the agent handles it."

*[Wait for the clarifying questions screen to appear]*

"Instead of guessing, the agent pauses and asks three focused questions: which metric do I want, how should it be grouped, and what time range. This is called Human in the Loop — the agent asks instead of assumes. It's a conscious design choice to save API budget and avoid building something that misses the point."

---

**[0:45 – 1:15] Answers → processing → dashboard**

*[Fill in the answers: count_claims, state, this_year — then click Submit Answers]*

"I'll say I want claim counts, broken down by state, for this year."

*[Wait for the processing screen and then the results screen]*

"You can see the status messages as the pipeline runs — spec generation, validation, rendering. And here's the dashboard."

*[Point to the confidence indicator]*

"This line here — 'Confidence: High' — is the agent rating its own output. It checks whether the metric and grouping it chose actually match the words I used. High confidence means it interpreted the request closely. Medium or Low would be a signal to review the charts before trusting them."

---

**[1:15 – 1:40] What did the agent do?**

*[Click the "What did the agent do?" expander]*

"Under here, you can see the full JSON spec the AI generated — the structured plan it used to build the charts. You can also see the validation confirmation. The agent checked every column name against a data dictionary before rendering a single chart. If I had asked for something that doesn't exist in our data — like agent salaries — it would have stopped here with a plain-English message instead of building a misleading dashboard."

---

**[1:40 – 2:00] What's next**

"The next version of this connects to a live metadata catalog via MCP — the Model Context Protocol — so the agent always knows exactly what data is available in real time, across any dataset, not just the insurance data it was built with. That's the difference between a demo and something you could actually deploy across a company."

---

*End recording.*
