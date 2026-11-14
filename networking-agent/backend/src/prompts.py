"""LLM prompts used by the search pipeline, kept in one place so they are easy to read and tune.

The pipeline (`pipeline/`) is a fixed LangGraph graph; the LLM only fills in structured
outputs, and code runs every search. One prompt per LLM step:

- `PLAN_PROMPT`: `plan` node. Profile -> target roles and which job sources to query with
  which filters (`pipeline.state.SearchPlan`).
- `USAJOBS_PLAN_PROMPT`: the USAJOBS paragraph of the plan prompt, added by `plan_prompt()`
  only when `config.usajobs_configured()`.
- `RANK_PROMPT`: `rank_companies` node. Jobs found -> companies scored 0-100 for fit, with
  their best postings and people-search keywords (`pipeline.state.CompanyRanking`).
- `COMPILE_PROMPT`: `compile` node. Gathered data -> `SearchResults` with alignment notes.
- `PEOPLE_NOTES_PROMPT`: on-demand people search ("Find People To Connect With"). People
  found at one company -> their alignment and connection notes.
- `LINKEDIN_MESSAGE_PROMPT`: rules for each person's `connect_message`, the example LinkedIn
  connection note. It is appended to the compile and people-notes prompts (see
  `compile_prompt()` / `people_notes_prompt()`), so notes are written in the same call as
  the rest; `{max_chars}` comes from `config.LINKEDIN_MESSAGE_MAX_CHARS`.
"""

import config

PLAN_PROMPT = """You plan a job search for a job seeker. From their profile, decide what to \
search for. Code then runs exactly the searches you plan, so be specific.

Decide:
- role_titles: 2-3 target role titles that fit their background and goals.
- seniority, industries (1-4) and location (where they want to work).
- people_location: the city to look for people to network with (e.g. "New York"), or "" if \
they want remote work or don't care where.

Job sources. Use one or more; an empty list skips that source:
- builtin_jobs: BuiltInNYC, a directory of New York City tech companies and their jobs (it \
also lists remote roles). Use it if the user is in or near New York City, or wants remote \
work. 1-3 searches, each a short phrase (1-3 words), optionally with a category, experience \
levels and remote preferences.
- builtin_companies: BuiltInNYC companies hiring in given industries. At most one, and only \
together with builtin_jobs, when industry fit matters.
- conservation_jobs: the Conservation Job Board, jobs at conservation and environmental \
organizations across the US (plus remote and international): wildlife, ecology, forestry, \
fisheries, botany, restoration, land trusts, environmental education, outdoor recreation, \
sustainability and conservation policy. Use it if the user wants conservation, \
environmental, nature, wildlife or outdoor work. 1-3 searches: categories, the user's \
state(s) and/or "remote", and an optional 1-2 word keyword. Filters combine with AND, so \
keep each search to a few filters.
{usajobs}
- ats_jobs: companies' own career boards on Greenhouse, Lever and Ashby, found through Google; \
postings come straight from the employer, in any city or industry. 0-2 searches, each a \
role phrase of 1-3 words matched against posting titles (e.g. "data analyst"; no seniority \
words) and a city ("New York"), "remote", or "" for anywhere. Use it when the user wants \
roles at tech or other companies that hire through careers pages, especially outside NYC. \
Each search costs one Google search per board provider, so skip it when the sources above \
fit well.
- google_queries: Google, for job postings the sources above don't cover. 0-2 queries such \
as `"<role>" jobs <city> site:ashbyhq.com`. Google is slow; skip it when \
the other sources fit well."""

USAJOBS_PLAN_PROMPT = """- usajobs: USAJOBS, the official US federal job site. Use it for \
federal and government roles, and especially for conservation, environmental, wildlife, \
forestry and park jobs (National Park Service, Fish and Wildlife Service, Forest Service, \
EPA). 0-2 searches, each with role keywords (e.g. "wildlife biologist"), a city and state \
(e.g. "Denver, Colorado"), "remote" or "" for anywhere, and optionally agencies ("nps", \
"usfws", "usfs", "epa"; [] for any agency). Federal pay is public and structured; hiring \
is slow and formal.
"""

RANK_PROMPT = """You rank companies for a job seeker, using job postings that were just \
found. Each posting has an id ("j1", ...).

Rules:
- Choose up to {max_companies} companies that fit the user best, and score each one 0-100 \
for overall fit (role, seniority, skills, industry, location, and how many relevant open \
jobs it has). Use the whole range: 80+ is a strong fit, below 40 a weak one.
- Only choose companies that appear in the data, with the name exactly as listed. For a \
Google result without a company, name the employer shown in its title, site or URL.
- jobs: that company's relevant postings by id, at most 4, each with its own 0-100 score.
- people_keywords: 1-2 short keyword sets describing people the user should contact there: \
someone on the team they would join (e.g. "data science manager", "engineering manager") \
and/or "recruiter". Describe the person, not the job posting (no "jobs", "hiring").
- reason: one short sentence on the score."""

COMPILE_PROMPT = """You turn gathered job-search research data into the final results.

Rules:
- Include every company in the research data, in the given order (they are ranked).
- For each company, list up to 4 relevant jobs and up to 4 people to contact from the data. \
Include every relevant person found at that company (the team the user would join, hiring \
leaders, recruiters); skip people who clearly no longer work there (`at_company: false`, \
"Ex-<company>") or are unrelated. If a company's `people_searched` is false, leave its \
people empty. Empty lists are allowed if nothing was found.
- Copy names, titles and URLs exactly as they appear in the data. Never invent them.
- Use `posting_text`, when present, for requirements, seniority and salary.
- `alignment` fields speak to the user ("You ...") and point to concrete overlaps between \
their background/goals and the company, job or person: skills, industry, school, past \
employers, location, seniority.
- Keep each alignment to 1-3 sentences."""

PEOPLE_NOTES_PROMPT = """You help a job seeker reach out to people at one company. You get \
their profile, the company (and the job they are interested in, if any) and LinkedIn \
profiles that were just found.

Rules:
- Return up to 4 of the found people, most relevant first: the team the user would join, \
hiring leaders, recruiters. Skip people who clearly no longer work there \
(`at_company: false`, "Ex-<company>") or are unrelated.
- Copy names, titles and profile URLs exactly as they appear in the data. Never invent them.
- `alignment` speaks to the user ("You ...") in 1-3 sentences: why connect, and what they \
have in common."""

LINKEDIN_MESSAGE_PROMPT = """Each person's `connect_message` is a LinkedIn connection note \
the user can send as-is:
- Hard limit: {max_chars} characters including spaces. Aim for {target_chars} or fewer; \
longer notes are cut off.
- Written by the user in the first person, addressed to the person by first name \
("Hi Jane, ...").
- Mention one specific, true overlap from the profile and the research data (their team or \
role, a shared skill, industry, school or past employer, or a job the user is applying to \
at their company).
- End with a light ask: connecting, or a short chat about their team or the role.
- Friendly and professional. No placeholders like [Name], no emojis, no hashtags, no links, \
no sign-off with the user's name.
- Never invent facts about the user or the person."""


def rank_prompt(max_companies: int | None = None) -> str:
    """`RANK_PROMPT` with the company cap (default from config)."""
    limit = max_companies if max_companies is not None else config.MAX_COMPANIES
    return RANK_PROMPT.format(max_companies=limit)


def linkedin_message_prompt(max_chars: int | None = None) -> str:
    """`LINKEDIN_MESSAGE_PROMPT` filled in with the character limit (default from config)."""
    limit = max_chars if max_chars is not None else config.LINKEDIN_MESSAGE_MAX_CHARS
    # Ask for a bit less than the hard limit: models count characters loosely.
    return LINKEDIN_MESSAGE_PROMPT.format(max_chars=limit, target_chars=max(1, limit * 5 // 6))


def plan_prompt(usajobs: bool | None = None) -> str:
    """System prompt of the plan step. USAJOBS is only offered when its key is configured
    (`usajobs` overrides `config.usajobs_configured()`)."""
    offer = config.usajobs_configured() if usajobs is None else usajobs
    return PLAN_PROMPT.replace("{usajobs}\n", USAJOBS_PLAN_PROMPT if offer else "")


def compile_prompt(max_chars: int | None = None) -> str:
    """System prompt of the compile step: results rules plus the LinkedIn note rules."""
    return f"{COMPILE_PROMPT}\n\n{linkedin_message_prompt(max_chars)}"


def people_notes_prompt(max_chars: int | None = None) -> str:
    """System prompt of the on-demand people step: people rules plus LinkedIn note rules."""
    return f"{PEOPLE_NOTES_PROMPT}\n\n{linkedin_message_prompt(max_chars)}"
