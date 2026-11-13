# Goal

Using the `inspect_page.py` file, along with your own web search, I'd like for you to come up with an API for the `BuiltInNYC` website. The function signatures should look something like:

```python
# api.py
def get_companies(company_filter: CompanyFilter, n: int) -> list[Company]:
    """Fetches companies from the BuiltInNYC website."""
    pass

def get_jobs(job_filter: JobFilter, n: int) -> list[Job]:
    """Fetches job listings from the BuiltInNYC website."""
    pass
```

The data structures should look something like:

```python
# models.py
from pydantic import BaseModel

class Company(BaseModel):
    ...

class CompanyFilter(BaseModel):
    ...

class Job(BaseModel):
    ...

class JobFilter(BaseModel):
    ...
```

# Process

Here are the two websites you should use to create the API: `https://www.builtinnyc.com/companies` and `https://www.builtinnyc.com/jobs`. Use the tools at your disposal to investigates these sites, inspect their packets, and figure out how to translate the requests they utilize into useable APIs that meet my needs. 