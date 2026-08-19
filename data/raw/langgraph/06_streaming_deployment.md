# LangGraph Streaming Modes and Deployment

## Streaming modes

LangGraph's `.stream()` method supports several distinct "stream modes," each surfacing a different granularity of information as the graph executes:

- `values` — after each super-step, emit the full current state.
- `updates` — after each super-step, emit only the partial update each node returned (more compact than `values`, and useful when you want to know exactly which node produced which change).
- `messages` — streams individual LLM tokens as they're generated inside a node, in addition to step-level updates, which is what powers a typical "typing" chat UI rather than waiting for a node to finish before showing any text.
- `debug` — emits detailed internal events, primarily useful while developing a graph.

You select the mode with the `stream_mode` argument:

```python
for chunk in graph.stream(input, config, stream_mode="updates"):
    print(chunk)
```

Multiple modes can be requested together (e.g., `stream_mode=["updates", "messages"]`), in which case each yielded chunk is tagged with which mode it came from, so a single stream can drive both a "step completed" log and a token-by-token chat bubble.

## Async execution

Every LangGraph method has an async counterpart (`ainvoke`, `astream`, `abatch`), which matters for production deployments where you want to serve many concurrent graph runs from one process without each one blocking on network calls to an LLM provider or external tool API. Nodes themselves can be defined as either sync or async functions; LangGraph handles both inside the same graph.

## LangGraph Platform / langgraph deploy

Beyond running a compiled graph directly inside your own Python process, LangGraph applications can be packaged and deployed as a standalone service. A deployment is described by a `langgraph.json` configuration file that points to the Python module(s) exposing one or more compiled graphs, declares dependencies, and optionally points to environment files. Once deployed, each graph is exposed over a REST/streaming API that external clients (a frontend, another backend service, a CLI) can call without needing direct access to your Python code — the deployment service itself manages a checkpointer-backed persistence layer, queueing, and horizontal scaling of concurrent threads.

## Local development server

During development, the LangGraph CLI provides a local server (commonly invoked as `langgraph dev`) that hot-reloads your graph code, exposes the same API shape as the production deployment target, and integrates with LangGraph Studio, a visual debugger that renders the graph topology and lets you step through a run, inspect state at each super-step, and manually trigger an `interrupt()` resume from a UI instead of writing a separate test harness.

## Configuration and runtime context

Graphs frequently need per-invocation configuration that should not live in the persisted state itself — for example, which `thread_id` to use, which LLM API key or model name to apply, or feature flags for a particular tenant in a multi-tenant deployment. This is passed via the `config` argument's `configurable` dictionary on every call, and nodes can read it through a `RunnableConfig` parameter, keeping such cross-cutting concerns separate from the application's actual state schema.

## Observability

Because LangGraph is built on the same Runnable interface as LangChain, it integrates directly with LangSmith for tracing: every node execution, LLM call, and tool call inside a run is captured as a span in a trace tree, which is invaluable for debugging why a multi-step agent took the path it did, measuring latency per node, and catching cases where a conditional edge routed somewhere unexpected.
