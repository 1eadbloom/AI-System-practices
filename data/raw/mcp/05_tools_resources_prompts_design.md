# MCP Design Guidance: Choosing Between Tools, Resources, and Prompts

A common question when building an MCP server is which of the three primitives — tools, resources, or prompts — is the right fit for a given piece of functionality. The protocol doesn't strictly enforce this choice (a server could technically expose everything as a tool), but using the right primitive produces a much better experience for both the model and the human using the host application.

## When to use a tool

Use a tool when the operation should be something the *model* decides to invoke autonomously, based on the conversation, and especially when the operation has a side effect or performs a computation rather than simply retrieving static data. Examples: sending an email, creating a calendar event, running a calculation, searching a database with a model-generated query, executing code. The defining trait is that the model is in the loop deciding both *whether* to call it and *what arguments* to call it with.

## When to use a resource

Use a resource when the content is something a human user (or the host application's own logic) should be able to explicitly select and attach to context, independent of whether the model thinks it's relevant. Examples: "attach this file to the conversation," "show me the current contents of this configuration," "let the user pick which document to discuss." Resources are a good fit for read-only, addressable content where you want a human-driven "pick from a list" UX rather than relying on the model to decide to fetch it. A resource that happens to require parameters (like a specific note ID) should still generally be modeled as a templated resource (`notes://{note_id}`) rather than as a "get_note" tool, if the intended interaction is "the user picks a note from a list" rather than "the model decides to look up a note based on the conversation."

## When to use a prompt

Use a prompt when you want to offer a curated, reusable interaction pattern that a human user explicitly triggers — most host applications surface prompts as a slash command or quick-action menu item. Prompts are useful for codifying "the right way to ask the model to do X" as a server-provided template (e.g., a standardized code-review prompt, a standardized bug-report-triage prompt) so that users get the benefit of well-engineered prompting without having to write it themselves each time.

## A worked example: a project management server

Consider an MCP server wrapping a project management tool:

- **Tools**: `create_task(title, assignee, due_date)`, `update_task_status(task_id, status)`, `search_tasks(query)` — these are actions or queries the model should be free to invoke based on what the user asks for in conversation.
- **Resources**: `project://{project_id}/board` (the current state of a specific kanban board), `project://{project_id}/members` (the member list) — these are things a user might want to explicitly attach to give the model context, without necessarily wanting the model to decide on its own to go fetch them.
- **Prompts**: `sprint_retro_prompt(project_id)` — a template that assembles a well-structured "run a sprint retrospective" prompt referencing the project's recent activity, which a user explicitly selects from a menu rather than hoping the model thinks to do something similar unprompted.

## Avoiding an overly tool-heavy design

A frequent anti-pattern is building a server that exposes only tools, including for things that are really just "fetch this data," because tools are the most familiar primitive (closest to a typical REST/function-calling API). This pushes more decision-making onto the model than necessary and can make host UIs feel less direct, since the user has to phrase a request and hope the model picks the right tool, rather than just clicking on a resource or running a prompt themselves. A well-designed server uses all three primitives where each genuinely fits, rather than defaulting to tools for everything.

## Naming and description quality

Whichever primitive you choose, names and descriptions matter enormously, because they are the only signal the model (for tools) or the host's UI (for resources and prompts) has to decide relevance. Vague tool descriptions like "performs an operation" produce far worse model behavior than specific ones like "creates a new task in the given project with the given title, optional assignee, and optional due date in YYYY-MM-DD format" — the latter both reduces incorrect invocations and improves argument accuracy.
