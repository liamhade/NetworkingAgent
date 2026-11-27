"""The graph's nodes and the helpers they share with the on-demand people search.

Each node takes the `PipelineState`, returns a partial update, appends `TraceStep`s and
reports progress through `status()`. Source errors are recorded and skipped; a node only
sets `error` when nothing usable is left.

One module per node (`plan`, `find_jobs`, `filter`, `rank`, `people`, `compile`) plus
`complete` (`complete_jobs`, called by `filter`), `common` and `reading`. Everything is
re-exported here, so callers use `steps.<name>`.
"""

import tools  # noqa: F401  (tests patch `steps.tools.read_page`)
from pipeline.steps.common import (
    call,
    clean_schools,
    dump,
    format_profile,
    name_key,
    plural,
    scored,
    short,
    status,
    structured,
    url_key,
)
from pipeline.steps.compile import (
    assemble_results,
    build_summary,
    compile_node,
    job_result,
    match_people,
    person_data,
    research_data,
)
from pipeline.steps.complete import HOST_READS, PAGE_MAX_CHARS, REQUIREMENTS_CHARS, complete_jobs
from pipeline.steps.filter import filter_jobs, filter_node, user_years
from pipeline.steps.find_jobs import (
    BUILTIN_PER_QUERY,
    GOOGLE_PER_QUERY,
    JobRunner,
    JobSearch,
    _ats_allowance,
    _ats_searches,
    _job_from,
    _job_searches,
    find_jobs_node,
    google_job_search,
)
from pipeline.steps.people import (
    QUERY_MAX_SEARCHES,
    find_people_node,
    ladder,
    search_people,
    search_people_by_query,
    search_similar_people,
    similar_ladder,
)
from pipeline.steps.plan import (
    MAX_ATS_QUERIES,
    MAX_GOOGLE_QUERIES,
    MAX_JOB_QUERIES,
    MIN_JOBS_BEFORE_GOOGLE,
    _ats_user_off,
    _usajobs_wanted,
    _user_off,
    cap_plan,
    google_fallback_query,
    plan_node,
    turned_off_queries,
)
from pipeline.steps.rank import (
    MAX_PEOPLE_KEYWORDS,
    build_chosen,
    default_ranking,
    job_card,
    rank_jobs_node,
    validate_ranking,
)
from pipeline.steps.reading import (
    _REQUIREMENTS,
    PAGE_READERS,
    page_pool,
    posting_excerpt,
    read_pages,
)

__all__ = [
    "status",
    "call",
    "structured",
    "clean_schools",
    "format_profile",
    "short",
    "plural",
    "url_key",
    "name_key",
    "dump",
    "scored",
    "MAX_JOB_QUERIES",
    "MAX_GOOGLE_QUERIES",
    "MAX_ATS_QUERIES",
    "MIN_JOBS_BEFORE_GOOGLE",
    "_usajobs_wanted",
    "_user_off",
    "_ats_user_off",
    "turned_off_queries",
    "cap_plan",
    "google_fallback_query",
    "plan_node",
    "_job_from",
    "BUILTIN_PER_QUERY",
    "GOOGLE_PER_QUERY",
    "JobSearch",
    "_job_searches",
    "google_job_search",
    "JobRunner",
    "_ats_allowance",
    "_ats_searches",
    "find_jobs_node",
    "filter_jobs",
    "filter_node",
    "user_years",
    "MAX_PEOPLE_KEYWORDS",
    "job_card",
    "validate_ranking",
    "default_ranking",
    "build_chosen",
    "rank_jobs_node",
    "PAGE_READERS",
    "page_pool",
    "read_pages",
    "_REQUIREMENTS",
    "posting_excerpt",
    "ladder",
    "similar_ladder",
    "search_similar_people",
    "search_people",
    "QUERY_MAX_SEARCHES",
    "search_people_by_query",
    "find_people_node",
    "person_data",
    "research_data",
    "job_result",
    "match_people",
    "assemble_results",
    "build_summary",
    "compile_node",
    "HOST_READS",
    "PAGE_MAX_CHARS",
    "REQUIREMENTS_CHARS",
    "complete_jobs",
    "tools",
]
