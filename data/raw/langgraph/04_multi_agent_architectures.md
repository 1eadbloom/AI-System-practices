# LangGraph Multi-Agent Architectures

As agentic systems grow more complex, a single LLM with a long system prompt and many tools tends to become hard to control: the model has to juggle too many responsibilities, and prompts grow unwieldy. LangGraph supports several established patterns for splitting one big agent into multiple smaller, specialized agents that collaborate inside a single graph.

## Why multi-agent

Three motivations come up repeatedly in practice:

- **Separation of concerns**: a "research agent" with web-search tools and a "writer agent" with no tools but a strong style prompt are each individually easier to test and prompt-engineer than one agent doing both jobs.
- **Tool isolation**: giving every agent every tool increases the chance the model picks the wrong one. Sub-agents that each see only the tools relevant to their job reduce this failure mode.
- **Independent context windows**: a sub-agent can be given a trimmed, task-specific slice of context instead of the entire conversation history, which keeps prompts shorter and more focused.

## Supervisor (orchestrator-worker) pattern

The most common multi-agent topology in LangGraph is a supervisor graph. A "supervisor" node — usually an LLM call with a routing-oriented system prompt — looks at the current state and decides which worker agent should act next, using a conditional edge to dispatch control. Each worker is itself a node (or even an entire sub-graph) that performs its specialized task and then returns control to the supervisor. The supervisor loops until it decides the overall task is complete, at which point a conditional edge routes to `END`.

```python
def supervisor(state):
    # LLM call decides: "researcher", "writer", or "done"
    ...

builder.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    {"researcher": "researcher", "writer": "writer", "done": END},
)
builder.add_edge("researcher", "supervisor")
builder.add_edge("writer", "supervisor")
```

## Network (peer-to-peer) pattern

Instead of a single central supervisor, agents can be wired so that each agent's node decides which peer to hand off to next, using conditional edges directly between worker nodes rather than always returning to a central dispatcher. This is more flexible but harder to reason about and debug, since there is no single place that holds the "current plan."

## Hierarchical (supervisor of supervisors)

For larger systems, supervisors can themselves be workers reporting to a higher-level supervisor — for instance, a top-level supervisor dispatching between a "research team" supervisor and a "writing team" supervisor, each of which manages its own pool of workers. In LangGraph this is implemented by compiling each team as its own sub-graph and then using that compiled sub-graph as a single node inside the parent graph.

## Sub-graphs

A compiled LangGraph graph can be embedded as a node inside another graph, as long as the parent and child share a compatible state shape (or the parent provides a small adapter function to translate between the two schemas). This is the primary mechanism for both hierarchical multi-agent systems and for reusing a well-tested sub-flow (e.g., a "retrieve and cite sources" sub-graph) across multiple parent applications.

## Handoffs and state sharing

When one agent hands off to another, a design decision is how much of the conversation history the second agent should see. Common choices:

- Pass the entire shared `messages` list, so every agent sees the full conversation — simplest, but context grows quickly and irrelevant turns can distract the receiving agent.
- Pass only a summarized or filtered subset of messages relevant to the receiving agent's task.
- Use separate state keys per agent (e.g., `researcher_state`, `writer_state`) and have the supervisor explicitly construct the input each worker receives, giving the most control at the cost of more orchestration code.

## Failure handling across agents

A frequent production concern is what happens when a worker agent fails or returns a low-confidence result. Supervisor graphs typically route low-confidence or error outputs back to the supervisor with an explicit "retry" or "escalate" signal in state, rather than letting the worker silently propagate a bad answer onward — the supervisor's routing function can then decide to retry with a different worker, ask a human via `interrupt()`, or terminate the run with an explanation.
