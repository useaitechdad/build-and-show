"""The task every config attempts, plus the system prompts.

Fairness: all three configs share the same neutral coding system prompt and the
same task. The advisor config additionally gets the advisor tool AND the
Anthropic-documented advisor timing/advice steering — i.e. the feature used as
intended. The (Advisor: ...) line trims advisor output length per the docs.
"""

# ---- The coding task (identical for every config) ----------------------------
TASK = (
    "Implement a thread-safe, BOUNDED worker pool with GRACEFUL SHUTDOWN using only "
    "the Python standard library (threading, queue). Return a SINGLE self-contained "
    "module as exactly one ```python code block and NOTHING outside it. Define exactly "
    "this public API:\n\n"
    "class WorkerPool:\n"
    "    def __init__(self, num_workers, max_queue):\n"
    "        # Start num_workers worker threads. Use an internal queue bounded to\n"
    "        # max_queue PENDING tasks.\n"
    "    def submit(self, fn):\n"
    "        # fn is a zero-argument callable. Enqueue it to be run by a worker.\n"
    "        # If the internal queue is full, BLOCK until space frees (backpressure).\n"
    "        # If the pool is already shut down, do NOT run fn -- raise RuntimeError.\n"
    "        # Returns None.\n"
    "    def shutdown(self):\n"
    "        # GRACEFUL shutdown: stop accepting new tasks, let EVERY task already\n"
    "        # submitted run to completion, then join all worker threads and return.\n"
    "        # Must not drop any submitted task and must NOT deadlock/hang.\n"
    "        # submit() after shutdown() raises RuntimeError. shutdown() is idempotent.\n\n"
    "Hard requirements:\n"
    "- At most num_workers tasks execute concurrently, ever.\n"
    "- No task submitted before shutdown() may be lost.\n"
    "- shutdown() MUST return once all submitted tasks finish (no hang, no busy-wait).\n"
    "- Standard library only. No prints. Thread-safe."
)

ADVISOR_TRIM = (" (Advisor: keep your guidance under 120 words -- I need a focused "
                "plan for the shutdown/draining design, not a full implementation.)")

# ---- System prompts -----------------------------------------------------------
BASE_SYSTEM = (
    "You are an expert Python systems engineer. You write correct, production-quality "
    "concurrent code. Concurrency edge cases -- graceful shutdown ordering, queue "
    "draining, worker join, and deadlock avoidance -- are exactly where most "
    "implementations fail, so reason through them before you finalize."
)

# Anthropic's documented advisor timing + advice steering for coding tasks.
ADVISOR_STEER = (
    "\n\nYou have access to an `advisor` tool backed by a stronger reviewer model. It "
    "takes NO parameters -- when you call advisor(), your entire conversation history "
    "is automatically forwarded; the advisor sees the task and everything you've done.\n\n"
    "Call advisor BEFORE substantive work -- before writing, before committing to an "
    "interpretation, before building on an assumption. Orientation is not substantive "
    "work; writing and declaring an answer are. On tasks longer than a few steps, call "
    "advisor at least once before committing to an approach and once before declaring "
    "done.\n\n"
    "Give the advice serious weight. If you follow a step and it fails empirically, or "
    "you have primary-source evidence that contradicts a specific claim, adapt. A "
    "passing self-test is not evidence the advice is wrong."
)

ADVISOR_TOOL = {
    "type": "advisor_20260301",
    "name": "advisor",
    "model": "claude-opus-4-8",
    "max_tokens": 2048,
}

# ---- Config matrix ------------------------------------------------------------
CONFIGS = {
    "sonnet_solo": {
        "label": "Sonnet solo",
        "model": "claude-sonnet-4-6",
        "system": BASE_SYSTEM,
        "tools": [],
        "user_suffix": "",
    },
    "advisor": {
        "label": "Sonnet + Opus advisor",
        "model": "claude-sonnet-4-6",
        "system": BASE_SYSTEM + ADVISOR_STEER,
        "tools": [ADVISOR_TOOL],
        "user_suffix": ADVISOR_TRIM,
    },
    "opus_solo": {
        "label": "Opus solo",
        "model": "claude-opus-4-8",
        "system": BASE_SYSTEM,
        "tools": [],
        "user_suffix": "",
    },
}
