# User Stories

Derived from **PRD_and_Tech_Spec.md** (Section 5). These stories capture the functional expectations for the Guideline Gateway platform.

| ID | Title | User Story | Acceptance Criteria |
|----|-------|------------|---------------------|
| US-01 | Offside query | As a referee, I ask "can a player be offside when receiving the ball from a throw‑in?" | Correct answer, names the relevant Law, shows the original source text (EN) plus an explanation (ID). |
| US-02 | Source citation | As a user, I want to see the sources of an answer | Every answer has at least one citation (Law, section, page, edition); clicking a citation opens the original text. |
| US-03 | Out‑of‑scope handling | As a user, I ask something outside football | The system politely declines: "outside the scope of this guide". |
| US-04 | No‑regulation handling | As a user, I ask something the document does not regulate | The system answers "no basis found in the document" and points to the nearest section. |
| US-05 | Multi‑rule scenario | As a user, I submit a multi‑rule scenario (e.g., handball + DOGSO) | The system retrieves at least two relevant Laws and summarizes both with citations. |
| US-06 | Pack version install | As an admin, I load a new edition of the Laws | The new Knowledge Pack installs from a file (USB); the old version can be rolled back. |
| US-07 | New domain creation | As an admin, I create a new domain | Preparing a PDF + `pack.yaml` + eval set is enough; the build pipeline produces the pack with no code change. |
| US-08 | Performance on weak device | As a user on a weak device | First response time (TTFT) meets the hardware tier target; the app does not crash from OOM. |

*These stories can be further refined into epics and tasks for implementation.*