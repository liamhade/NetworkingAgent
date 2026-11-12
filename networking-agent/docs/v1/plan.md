# goal

The purpose of this project is to create an application that helps users find companies to research, job postings, and people to network with in order to find career opportunities. 

# backend

## stack

- `Python` using a virtual environment.
- `LangChain` for the agent harness
- `FastAPI` for the server

# frontend

## pages

*hero*: 
- users type in their background, where they live, and what they're looking for. 
- Users can optionally upload a PDF of their resume; the LLM will parse it and use that to fill in the background section.
- The algorithm then searches for companies, jobg postings, and people related to those companies and positions that would be aligned with them.

*results*: 
- The model will spit out a list of companies with job openings, and people at those companies who you should network with a simple list format.

## stack

`Vite`: `React` + `Typescript` 

## design

Keep the design clean and intuitive.
Use the components from `https://www.boardui.com/installation` for consistency.