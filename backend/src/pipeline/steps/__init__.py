"""The graph's nodes and the helpers they share with the on-demand people search.

Each node takes the `PipelineState`, returns a partial update, appends `TraceStep`s and
reports progress through `status()`. Source errors are recorded and skipped; a node only
sets `error` when nothing usable is left.

One module per node (`plan`, `find_jobs`, `rank`, `rescore`, `people`, `postings`, `compile`)
plus `common` and `reading`. Everything is re-exported here, so callers use `steps.<name>`.
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
    _fallback_company,
    compile_node,
    match_jobs,
    match_people,
    person_data,
    research_data,
    restrict_results,
)
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
from pipeline.steps.postings import read_postings_node
from pipeline.steps.rank import (
    MAX_JOBS_PER_COMPANY,
    MAX_PEOPLE_KEYWORDS,
    _jobs_table,
    default_ranking,
    rank_companies_node,
    validate_ranking,
)
from pipeline.steps.reading import (
    _REQUIREMENTS,
    PAGE_READERS,
    _page_pool,
    posting_excerpt,
    read_pages,
)
from pipeline.steps.rescore import _rescore_targets, apply_rescoring, rescore_jobs_node

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
    "MAX_JOBS_PER_COMPANY",
    "MAX_PEOPLE_KEYWORDS",
    "_jobs_table",
    "validate_ranking",
    "default_ranking",
    "rank_companies_node",
    "PAGE_READERS",
    "_page_pool",
    "read_pages",
    "_REQUIREMENTS",
    "posting_excerpt",
    "_rescore_targets",
    "apply_rescoring",
    "rescore_jobs_node",
    "ladder",
    "similar_ladder",
    "search_similar_people",
    "search_people",
    "QUERY_MAX_SEARCHES",
    "search_people_by_query",
    "find_people_node",
    "read_postings_node",
    "person_data",
    "research_data",
    "match_jobs",
    "match_people",
    "_fallback_company",
    "restrict_results",
    "compile_node",
    "tools",
]
