# TODO 

## Rough Ideas

- [ ] (**redirects to related entities from entity cards**) If a person is connected to a job, those jobs should be listed beneath their card. If a job also has a list of people to connect with, then those should be selectable beneath the job card. And if a company has jobs or people connected to, those should be selectable beneath the company card.

- [ ] (**add application stories**) When user applies for a job, if there are questions on the application, the agent should be able to help the user answer the questions.

- [ ] (**match users writing style**) Tweak the LinkedIn messages to match the users writing style. Optionally provide 5-10 writing samples to train the model.

- [ ] (**refine UI**) It's a little confusiong at the moment, especially with the headers.

## In-Queue

## Postponed

- [ ] (**Job queue for background searches**) Move background searches off in-memory threads onto a persistent job queue so they survive restarts and work with more than one server process (plan alongside the Supabase migration).

- [ ] (**Add sign-in so users can use accounts**) 
    - [ ] Store account information on Supabase
    - [ ] Support Google OAuth (I'll need to create the GCP project for this)
    - [ ] Support username and password sign-in

## Done

- [x] (**can exit and come back to ongoing search**) If a user clicks on "Find Opportunities", then looks around at some of the other pages, they should still be able to find that ongoing search in the "Previous Searches" panel, even if it hasn't finished yet. User's shouldn't have to wait on a "searching" page for the results to finish.

- [x] (**Cancel a running search**) Add a Cancel button for a running search in the Previous Searches panel, and cap how many searches can run at the same time (extra ones wait or are refused with a clear message).

- [x] (**Delete failed searches**) Failed searches now stay in the Previous Searches panel marked "Failed". Add a way to delete a search (failed or otherwise) from the panel.

- [x] (**ATS job boards: Greenhouse**) Find employer-direct postings by running Google `site:` searches for Greenhouse boards (e.g. `site:job-boards.greenhouse.io "data analyst" New York`), then pull the company's job list from Greenhouse's public JSON board API. Build this as a shared `ats` layer that Lever, Ashby and Workable plug into, and wire it into the search pipeline.

- [x] (**ATS job boards: Lever**) Add Lever (`jobs.lever.co`, public postings API) to the `ats` layer.

- [x] (**ATS job boards: Ashby**) Add Ashby (`jobs.ashbyhq.com`, public job-board API) to the `ats` layer.

- [x] (**ATS job boards: Workable**) Add Workable (`apply.workable.com`, public widget/accounts API) to the `ats` layer.

- [x] (**USAJOBS**) Add the official USAJOBS search API (free key, `USAJOBS_API_KEY` + `USAJOBS_EMAIL` env vars) as a job source, mainly for federal conservation roles (NPS, USFWS, USFS, EPA). Skip the source gracefully when no key is configured.

- [x] (**search board configuration panel**) On the search page, add a configuration panel for the search that lets us decide which boards to search, and how many jobs to look for on each one. The bot should still decide how to rank the jobs and sort them for the user.

- [x] (**remember user resume and search credentials**) When a user comes back to the search page, they shouldn't have to keep resubmiting their resume or reinputing their search credentials. Compress and save their PDF, and store their search parameters.

- [x] (**save different search configurations**) On a right panel in the search page, users should see a list of their search configurations. They can save their current configuration, name it on the side (default to "Search Configuration #n"), and load previous configurations

- [x] (**add ability to sort companies, jobs, or people in their pages**) In their individual pages, we should be able to sort by "CONNECTED" / "NOT CONNECTED" (or other field values) to organize the listing.

- [x] (**add counts**) For jobs and people, we should add a count to their pages to show how many out of the total number we have connected / applied to, shown as an X/Y format.

- [x] (**example message to send over linkedin**) For people, add an extra bubble below the Why Connect bubble that is an example linkedin message. It should be an under 300 (configurable value) character message that I can send to that person to connect with them. Expose the prompt for creating this message in the `prompts.py` file.

- [x] (**pin for later**) We should be able to pin entities to come back to for later if we're interested in them. We can then pull op our pinned entities in their individual pages by sorting by pins.

- [x] (**cleanup serp module**) The `google_serp` module is organized in a strange way. It has a `cli.py`, a `__main__.py` file, etc. Make strip away the fluff from the `serp` module and keep only what is neccessary for the `networking_agent` to use it. I want the module to be lean, and easy to read. Bonus: apply the same kind of update to `builtin_nyc` module.

- [x] (**add conservation board support**) For now, I only plan to work with the `Google SERP` API and the BuiltInNYC API. In the future, when I expand support, the first thing will be to create an API for this site: `https://www.conservationjobboard.com/`.

- [x] (**migrate modules into `src`**) Move the `built-in-nyc` and `google-serp-url` modules into the networking-agent `src` folder to consolidate code under the `networking-agent` repo.  

- [x] (**Store previous searchs**) User should see a side-panel on the left of the different searches they've done, ordered by the most recent. Each chat bubble should have a short the time it was created, and a short title.

- [x] (**Keep log of which jobs we've applied to**) Every job that shows up for a user should have a toggle that says "APPLIED" or "NOT APPLIED". And every person that shows up should have a toggle that says "CONNECTED" or "NOT CONNECTED". That toggle is persisted across runs. So if the user applies to a job, does another search, and the same job appears, it should stay as "APPLIED".

- [x] (**Add company + jobs + person to menu bar**) In the menu bar, there should be three pages we can navigate to: `Companies`, `Jobs`, and `People`. Each page shows a list of the respective entities that we have encountered through our search. Each entity (company, job, or person) should be in it's own widget box.. Every time we make a new search, these lists are updated to include them. 

- [x] (**Add read_page() tool**) Given a URL, the Agent should get the text of the webpage rendered as Markdown, including with hyperlinks. The tool should use a default method for pages, but we should add the option to use a more efficient method if we discover one that is particulary suited for a page or group of pages.
    - [x] (*experiment*) Figure out what Python modules or tools are best suited for crawling converting a web-page into an easy to read format. Some suggestions are using tools like `Crawl4AI`, `trafilatura`, or `markdownify`.
    - [x] (*plan*) Create a plant to implement this module and tool
    - [x] (*implement*) Implement the plan

- [x] (**investigate speeding up Google SERP results**) Check if there's a way to speed up the Google SERP results without flagging the bot-detection radar, while still keeping full redirect links.

- [x] (**Log token usage for each LLM**) Logs LLM token usage + cost to `logs` in a csv format so that I can easily calculate token usage per person, per timeframe, or just overall.