"""Python API for https://www.conservationjobboard.com (conservation and environmental jobs).

```python
from conservation_jobboard import Category, JobFilter, Location, get_jobs

jobs = get_jobs(JobFilter(keyword="biologist", locations=[Location.COLORADO]), n=10)
```
"""

from .api import get_jobs
from .models import Category, ExperienceLevel, Job, JobFilter, JobType, Location

__all__ = [
    "Category",
    "ExperienceLevel",
    "Job",
    "JobFilter",
    "JobType",
    "Location",
    "get_jobs",
]
