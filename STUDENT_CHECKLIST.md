# Assessment 3 submission checklist

- [x] Working local product and one-command `./start.sh`
- [x] Editable request intake and all six required output fields
- [x] Five read-only tools, including deterministic policy checks
- [x] Single-agent baseline A and analyst/reviewer architecture B
- [x] Human handoff export; no autonomous approvals or purchases
- [x] Supplied data/policy and public adapter preserved
- [x] Same 32-case offline evaluation for A/B; three repetitions and raw results
- [x] Live Gemini comparison: one repetition, 64 analyses, 160 model calls; all scores/failures published
- [x] 73 automated tests and eight headless UI checks passed
- [x] Workflow/architecture diagrams, assumptions, known limitations
- [x] Decision memo below 500 words
- [x] README, pinned dependencies and `.env.example`
- [x] Clean checkout startup verified
- [x] Tracked-file secret scan passed
- [x] Public GitHub repository published: https://github.com/vedanshun05/fde-assessment3-procurement-copilot
- [ ] Submit public repository URL through the Google Form by 8 October 2026

Live Gemini access is verified. The complete paired comparison scored A 21/32 and B 31/32, while both retained all tested policy/evidence/human-handoff controls. B is the supervised-pilot choice and the UI default; the decision memo documents its remaining error, added latency/calls, and limited evidence. Follow [the Gemini setup](docs/GEMINI_SETUP.md) to reproduce the experiment. Fresh held-out requests, repeated live runs, and independent rationale review remain future validation. OpenAI live access remains unmeasured. An OpenAI key or paid provider is not required by the assessment.
