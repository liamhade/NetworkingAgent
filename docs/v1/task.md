# goal

The purpose of this project is to create an application that helps users find companies to research, job postings, and people to network with in order to find career opportunities. 

All changes should be focused in `networking-agent`.

# backend

## modules

Use the `C:\Users\liamh\OneDrive\Desktop\projects\networking-agent\find-google-serp-url` and `C:\Users\liamh\OneDrive\Desktop\projects\networking-agent\built-in-nyc-api` modules as the backbone of the networking agent. Those two APIs should be accessible as tool calls.

## stack

- `Python` using a virtual environment.
- `LangChain` for the agent harness
- `FastAPI` for the server
- `LLM` object should be model agnostic - for now, we're using an Anthropic key (let's use `Haiku` for this first version to keep things simple)

# frontend

## pages

*hero*: 
- users type in their background, where they live, and what they're looking for. 
- Users can optionally upload a PDF of their resume; the LLM will parse it and use that to fill in the background section.
- The algorithm then searches for companies, job postings, and people related to those companies and positions that would be aligned with them.

*results*: 
- The model will spit out a list of companies with job openings, and people at those companies who you should network with a simple list format.
- For each company, job posting, and person, it tells you how you align with them in an expandable greenbox.

## stack

`Vite`: `React` + `Typescript` 

## design

Keep the design clean and intuitive.
Use the components from `https://www.boardui.com/installation` for consistency.