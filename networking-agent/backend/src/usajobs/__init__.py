"""Python API for the official USAJOBS search API (federal jobs, https://developer.usajobs.gov).

```python
from usajobs import Agency, JobFilter, search_jobs

jobs = search_jobs(JobFilter(keyword="biologist", agencies=[Agency.NPS]), 10, api_key, email)
```
"""

from .api import UsajobsError, search_jobs
from .models import Agency, Job, JobFilter

__all__ = ["Agency", "Job", "JobFilter", "UsajobsError", "search_jobs"]
