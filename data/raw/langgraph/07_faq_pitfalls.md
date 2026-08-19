# LangGraph FAQ and Common Pitfalls

This note collects practical questions that come up repeatedly when building with LangGraph, organized as a FAQ.

## "My graph compiles but invoke() does nothing."

This almost always means there is no edge from `START` into your first node. LangGraph happily compiles a graph with disconnected pieces; it only fails at *invoke* time (or simply never reaches any real node) if the entry point isn't wired. Always check `builder.add_edge(START, "first_node")` exists.

## "I get InvalidUpdateError when a node returns its update."

The dictionary keys a node returns must exactly match field names declared in your state's `TypedDict` (or Pydantic model). A typo like returning `{"counter": 1}` against a schema that declares `count` will raise this error. There is no fuzzy matching — the keys must be exact.

## "My conditional edge throws a ValueError about an unknown node."

`add_conditional_edges(source, routing_fn, mapping)` requires that whatever string `routing_fn` returns exists as a key in `mapping`, and that the corresponding value is an actual node name (or `END`). A common mistake is the routing function returning `"process_data"` while the node was registered as `"process"` — LangGraph cannot guess that these refer to the same thing.

## "Why does my side effect run twice after a human approval pause?"

If a node calls `interrupt()`, and there is code with side effects *before* that call in the same function, resuming the graph re-runs the entire node from its top — including that earlier side-effecting code. See the persistence and human-in-the-loop notes for mitigation strategies (separate nodes, idempotency checks, or the Functional API's `task()` decorator).

## "How is LangGraph different from a plain LangChain chain (e.g., LCEL)?"

LCEL (`prompt | model | parser`) composes a fixed, single-pass pipeline: data flows through exactly once, start to finish, with no cycles. LangGraph is for situations that need looping (an agent retrying or re-planning), conditional branching based on runtime state, persistence across multiple separate calls, or multiple cooperating sub-components — none of which map cleanly onto a single linear pipe.

## "Do I need a checkpointer for every graph?"

No. A checkpointer is only required if you need cross-invocation memory, `interrupt()`-based human-in-the-loop pauses, or "time travel" through state history. A simple, single-shot graph that runs start-to-finish in one `.invoke()` call and doesn't need to be resumed later can be compiled without one.

## "How do I limit how many loop iterations an agent can take?"

Two complementary mechanisms: track an explicit counter inside your state schema and have a conditional edge force a route to `END` once it exceeds a threshold (giving you full control over the "giving up" message shown to the user), and/or set the `recursion_limit` in the invocation config as a hard safety net that raises an exception if the graph runs more super-steps than expected — useful for catching genuine bugs in routing logic rather than just expected long-but-bounded agent loops.

## "Can two nodes write to the same state key in the same super-step?"

Only if that key has a reducer that knows how to combine multiple updates (like `add_messages`, which knows how to merge multiple new messages into one list). For a plain overwrite key, having two parallel nodes both return a value for it in the same super-step is ambiguous and should be avoided — design your fan-out/fan-in so that parallel branches write to distinct keys, then have a downstream "join" node combine them explicitly.

## "My sub-graph's state isn't compatible with the parent graph."

When embedding a compiled graph as a node inside a parent graph, either ensure the two `TypedDict`/`BaseModel` schemas are structurally compatible (share the relevant key names and types), or wrap the sub-graph invocation in a small adapter node that translates the parent's state into the shape the sub-graph expects on the way in, and translates the sub-graph's output back into the parent's schema on the way out.
