"""Python API for https://www.builtinnyc.com (companies and jobs).

```python
from builtin_nyc import JobFilter, get_jobs

jobs = get_jobs(JobFilter(search="data analyst"), n=10)
```
"""

from .api import get_companies, get_jobs
from .models import (
    Company,
    CompanyFilter,
    CompanySize,
    ExperienceLevel,
    Job,
    JobCategory,
    JobFilter,
    RemotePreference,
)

__all__ = [
    "Company",
    "CompanyFilter",
    "CompanySize",
    "ExperienceLevel",
    "Job",
    "JobCategory",
    "JobFilter",
    "RemotePreference",
    "get_companies",
    "get_jobs",
]
