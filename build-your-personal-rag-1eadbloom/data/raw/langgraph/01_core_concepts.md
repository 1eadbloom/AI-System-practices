# LangGraph Core Concepts: State, Nodes, and Edges

LangGraph is a low-level orchestration framework, built on top of LangChain's component ecosystem, for building stateful, multi-step applications with language models. Unlike a simple prompt-chain library, LangGraph models an application as a directed graph, which makes it natural to express loops, branches, and long-running agent behavior that a strictly linear chain cannot represent.

## State

The State is the central data structure that flows through the graph. It is typically declared as a `TypedDict` or a Pydantic `BaseModel`, and every field that any node might read or write must be declared up front in this schema. A node receives the full current state as its input and returns only the subset of keys it wants to change — LangGraph then merges that partial update back into the overall state using a "reducer" for each key.

By default, a key is simply overwritten by whatever a node returns for it. This is fine for scalar values such as a `step_count` integer, but it is the wrong behavior for things like conversation history, where you usually want to append rather than replace. For that case, LangGraph lets you annotate a field with a reducer function. The most common example is:

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
```

Here `add_messages` is a reducer that knows how to append new messages to the existing list (and even how to deduplicate or replace messages by ID), instead of clobbering the whole history every time a node returns a new message.

## Nodes

A node is just a Python function (or callable class) with the signature `(state) -> partial_state_update`. Nodes encode the actual logic of your application: calling an LLM, calling a tool, doing some deterministic computation, or producing a side effect like writing to a database. Nodes are registered on a graph builder with `add_node(name, fn)`. If you omit the name, LangGraph uses the function's name as the node's identifier.

Nodes are intentionally "dumb" about control flow — they do not decide what happens next. That decision is the job of edges. This separation is what makes LangGraph graphs easy to reason about: you can look at the node list to understand *what* work happens, and at the edge list to understand *when* it happens.

## Edges

Edges connect nodes and determine the path execution takes through the graph. There are three main kinds:

1. **Normal edges** — a fixed, unconditional transition from one node to another, created with `add_edge(node_a, node_b)`. Whenever `node_a` finishes, `node_b` always runs next.
2. **Conditional edges** — created with `add_conditional_edges(node, routing_fn, mapping)`. After `node` finishes, `routing_fn` is called with the current state and must return a string key. That key is looked up in `mapping` to decide the actual destination node. This is how you implement branching logic, such as "if the LLM asked for a tool call, go to the tools node; otherwise go to END."
3. **Entry and exit edges** — every graph needs an edge from the special `START` node to whichever node should run first, and at least one path that eventually reaches the special `END` node. Forgetting the edge into `START` means the graph compiles but does nothing when invoked; forgetting a path to `END` produces a graph with a "dead end" that LangGraph will flag as an error at compile time for orphaned or unreachable nodes.

## Super-steps and message passing

Internally, LangGraph's execution model is inspired by Google's Pregel system for large-scale graph processing. Execution proceeds in discrete "super-steps." In a single super-step, every node that has received a new incoming message (i.e., every node whose predecessor just finished) runs once. Nodes that happen to run in parallel within the same super-step are considered concurrent; nodes that depend on each other's output run in separate, sequential super-steps. This model is what allows LangGraph to support both straightforward sequential chains and complex fan-out/fan-in patterns using the same underlying engine.

## Compiling the graph

Once nodes and edges are added to a `StateGraph` builder, you call `.compile()` to turn it into a runnable object. The compiled graph exposes the same interface as any other LangChain "Runnable": `.invoke()`, `.stream()`, `.batch()`, and their async counterparts. Compilation is also where you attach a checkpointer (for persistence across runs) or interrupt configuration (for human-in-the-loop pausing), both of which are discussed in other notes in this knowledge base.

## Common beginner mistakes

In practice, three issues account for the majority of early debugging time:

- **Orphan nodes**: a node was added with `add_node` but never connected with any edge, so it sits in the graph but never executes. Calling `graph.get_graph()` and inspecting the visualization (or programmatically checking that every node has both incoming and outgoing edges) catches this quickly.
- **State key mismatches**: a node returns a dictionary key that was never declared in the `TypedDict` schema, e.g. returning `{"counter": 10}` when the schema declares `count`. LangGraph raises an `InvalidUpdateError` in this situation.
- **Routing string mismatches**: a conditional edge's routing function returns a string that does not appear as a key in the destination mapping, or that does not match an actual node name. This raises a `ValueError` at execution time, not at compile time, so it is worth unit-testing routing functions directly.
