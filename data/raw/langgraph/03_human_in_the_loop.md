# LangGraph Human-in-the-Loop Patterns

Many real agent workflows need a human to approve, edit, or reject an action before it takes effect — for example, approving an outbound email an agent drafted, or confirming a financial transaction. LangGraph supports this directly through the `interrupt()` primitive combined with its checkpointing system.

## The interrupt() function

Calling `interrupt(payload)` from inside a node does two things: it persists the current state as a checkpoint, and it raises a special control-flow signal that pauses the graph and returns `payload` to whatever code called `.invoke()` or `.stream()`. The calling application — typically a web backend — can then show `payload` to a human (e.g., render it as an approval dialog) and wait for a decision.

```python
from langgraph.types import interrupt, Command

def review_node(state):
    decision = interrupt({"action": state["proposed_action"], "question": "Approve?"})
    return {"approved": decision}
```

To resume, the caller invokes the graph again on the same thread, passing a `Command(resume=<value>)` instead of a normal input:

```python
graph.invoke(Command(resume=True), config={"configurable": {"thread_id": "abc"}})
```

LangGraph replays the node from its start, but the `interrupt()` call this time returns the resumed value instead of pausing again.

## Side effects before interrupt()

Because the node restarts from the top when resumed, any code that runs *before* the `interrupt()` call inside that node will execute again on resume. If that code has side effects — sending a notification, incrementing a counter, calling a paid API — those side effects will fire twice (once before the original pause, once again on resume) unless you guard them. The recommended approaches are:

- Move side effects to a separate node that runs only once, after the interrupt-containing node returns a decision.
- Wrap the side effect in an idempotency check (e.g., "has this notification ID already been sent?").
- Use the Functional API's `task()` decorator, which checkpoints the *result* of the wrapped call so it is not re-executed on resume — but see the warning in the persistence notes about changing task ordering across a pause boundary.

## Common human-in-the-loop topologies

- **Approve or reject**: a single interrupt that returns a boolean; a conditional edge routes to "execute" or "abort" based on the answer.
- **Edit before continuing**: the interrupt payload includes a draft (e.g., a generated email), and the resumed value is the human-edited version of that draft, which downstream nodes treat as the source of truth instead of the original LLM output.
- **Multiple sequential approvals**: a node can call `interrupt()` more than once in sequence (e.g., approve the plan, then separately approve each step), as long as each call is idempotent with respect to re-execution.

## Static breakpoints versus dynamic interrupts

LangGraph also supports "static" breakpoints configured at compile time via `interrupt_before=["node_name"]` or `interrupt_after=["node_name"]`. These always pause execution at the same point in the graph, which is useful for simple "always require approval before this step" policies. Dynamic `interrupt()` calls inside node code are more flexible because the decision to pause (and the payload shown to the human) can depend on runtime state — for instance, only pausing for approval if a proposed transaction exceeds some dollar threshold.

## Streaming intermediate state to a UI

Because LangGraph's `.stream()` method emits state updates after every super-step, a frontend can render an agent's reasoning and tool calls as they happen, rather than waiting for the entire run to finish. Combined with `interrupt()`, this lets you build chat-style UIs where the user sees the agent's plan appear, then sees a clear "waiting for your approval" state, then sees execution resume live once they respond — all backed by the same checkpoint thread.
