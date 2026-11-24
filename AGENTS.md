# Overview

The purpose of this workspace is to collect different tools that will be useful for the `Networking Agent`. The `Networking Agent` is the name I have given to a project where you type in your job search parameters, and it will give you a list of companies to look at, people to connect with, and jobs to apply to.

# Using the TODO

After you complete a task from the `TODO.md` check of the box.

# Version-Control

Always benchmark your work by making committing meaningful, working changes (don't save something that's broken).

Use the `Conventional Commits` format for saving work.

# Folder Structure

The app lives at the repo root: `backend/` (FastAPI), `frontend/` (Vite + React), `research/` (scripts, not used at runtime), `docs/`, and the `Dockerfile`.

Use a `Service Oriented` folder structure to group files in the `backend`.

# Documentation

For any large change you are going to make, write up the plan for that change into `docs/` so that there is auditability of the development process.

# Database

Eventually, I'm going to migrate the database to `Supabase`. For this POC, to keep the ball rolling, let's just use the local `database` folder as the database we're going to use. It holds personal data and is gitignored: never commit it.

I'm also going to add separate accounts in the future. But for now, we're going to test using the "TEST_USER" account.