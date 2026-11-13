# TODO

## In-Queue

- [x] (**Store previous searchs**) User should see a side-panel on the left of the different searches they've done, ordered by the most recent. Each chat bubble should have a short the time it was created, and a short title.

- [ ] (**Keep log of which jobs we've applied to**) Every job that shows up for a user should have a toggle that says "APPLIED" or "NOT APPLIED". And every person that shows up should have a toggle that says "CONNECTED" or "NOT CONNECTED". That toggle is persisted across runs. So if the user applies to a job, does another search, and the same job appears, it should stay as "APPLIED".

- [ ] (**Add company + jobs + person to menu bar**) In the menu bar, there should be three pages we can navigate to: `Companies`, `Jobs`, and `People`. Each page shows a list of the respective entities that we have encountered through our search. Each entity (company, job, or person) should be in it's own widget box.. Every time we make a new search, these lists are updated to include them. 

- [ ] (**Add read_page() tool**) Given a URL, the Agent should get the text of the webpage rendered as Markdown, including with hyperlinks. The tool should use a default method for pages, but we should add the option to use a more efficient method if we discover one that is particulary suited for a page or group of pages.
    - [ ] (*experiment*) Figure out what Python modules or tools are best suited for crawling converting a web-page into an easy to read format. Some suggestions are using tools like `Crawl4AI`, `trafilatura`, or `markdownify`.
    - [ ] (*plan*) Create a plant to implement this module and tool
    - [ ] (*implement*) Implement the plan

- [ ] (**investigate speeding up Google SERP results**) Check if there's a way to speed up the Google SERP results without flagging the bot-detection radar, while still keeping full redirect links.

- [ ] (**Log token usage for each LLM**) Logs LLM token usage + cost to `logs` in a csv format so that I can easily calculate token usage per person, per timeframe, or just overall.

# Postponed

- [ ] (**Add sign-in so users can use accounts**) 
    - [ ] Store account information on Supabase
    - [ ] Support Google OAuth (I'll need to create the GCP project for this)
    - [ ] Support username and password sign-in

- [ ] (**add conservation board support**) For now, I only plan to work with the `Google SERP` API and the BuiltInNYC API. In the future, when I expand support, the first thing will be to create an API for this site: `https://www.conservationjobboard.com/`.

# Done

- [x] (**migrate modules into `src`**) Move the `built-in-nyc` and `google-serp-url` modules into the networking-agent `src` folder to consolidate code under the `networking-agent` repo.  
