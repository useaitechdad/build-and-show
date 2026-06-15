"""Deterministic verifier for a candidate WorkerPool module.

Usage:  python3 verify_pool.py <candidate.py> <trace_out.jsonl>

Stress-tests the candidate's graceful shutdown and prints a JSON verdict to stdout.
Writes an animatable event trace (flushed per event) so that even if the candidate
DEADLOCKS and the parent kills this process, the partial trace survives and shows
exactly which jobs froze. A hang is detected by the parent's subprocess timeout.
"""
import importlib.util
import json
import sys
import threading
import time

NUM_WORKERS = 4
MAX_QUEUE = 8
TOTAL = 60
JOB_SLEEP = 0.02  # seconds per task


def load_pool(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "WorkerPool")


def main():
    candidate_path, trace_path = sys.argv[1], sys.argv[2]
    trace = open(trace_path, "w")
    t0 = time.monotonic()

    def ev(name, **kw):
        rec = {"t": round(time.monotonic() - t0, 4), "ev": name, **kw}
        trace.write(json.dumps(rec) + "\n")
        trace.flush()

    def fail(reason, **extra):
        print(json.dumps({"passed": False, "reason": reason, **extra}))
        trace.close()
        sys.exit(0)

    try:
        WorkerPool = load_pool(candidate_path)
    except Exception as e:
        fail(f"import_error: {type(e).__name__}: {e}")

    completed = set()
    comp_lock = threading.Lock()
    conc = 0
    max_conc = 0
    conc_lock = threading.Lock()

    def make_job(i):
        def job():
            nonlocal conc, max_conc
            with conc_lock:
                conc += 1
                max_conc = max(max_conc, conc)
                c = conc
            ev("start", job=i, conc=c)
            time.sleep(JOB_SLEEP)
            with conc_lock:
                conc -= 1
            with comp_lock:
                completed.add(i)
            ev("finish", job=i)
        return job

    try:
        pool = WorkerPool(NUM_WORKERS, MAX_QUEUE)
    except Exception as e:
        fail(f"construct_error: {type(e).__name__}: {e}")

    ev("pool_created", num_workers=NUM_WORKERS, max_queue=MAX_QUEUE, total=TOTAL)

    # Submit all tasks. With a bounded queue, submit() blocks (backpressure), so by
    # the time the last submit returns, many tasks are still queued/in-flight --
    # which is exactly what graceful shutdown must drain.
    try:
        for i in range(TOTAL):
            pool.submit(make_job(i))
            ev("submit", job=i)
    except Exception as e:
        fail(f"submit_error: {type(e).__name__}: {e}", submitted=len(completed))

    ev("shutdown_called", done_so_far=len(completed))
    sd_start = time.monotonic()
    try:
        pool.shutdown()  # if this hangs, the parent kills us -> DEADLOCK
    except Exception as e:
        fail(f"shutdown_error: {type(e).__name__}: {e}", completed=len(completed))
    sd_secs = round(time.monotonic() - sd_start, 4)
    ev("shutdown_returned", completed=len(completed), shutdown_secs=sd_secs)

    # --- Verdict checks ---
    missing = sorted(set(range(TOTAL)) - completed)
    if missing:
        fail("tasks_lost", completed=len(completed), total=TOTAL,
             missing_count=len(missing), missing_sample=missing[:10],
             max_concurrency=max_conc, shutdown_secs=sd_secs)

    if max_conc > NUM_WORKERS:
        fail("concurrency_exceeded", max_concurrency=max_conc, limit=NUM_WORKERS,
             completed=len(completed), shutdown_secs=sd_secs)

    # submit after shutdown must raise RuntimeError
    rejected = False
    try:
        pool.submit(lambda: None)
    except RuntimeError:
        rejected = True
    except Exception:
        rejected = False
    if not rejected:
        fail("submit_after_shutdown_not_rejected", completed=len(completed),
             max_concurrency=max_conc, shutdown_secs=sd_secs)

    print(json.dumps({
        "passed": True,
        "reason": "ok",
        "completed": len(completed),
        "total": TOTAL,
        "max_concurrency": max_conc,
        "concurrency_limit": NUM_WORKERS,
        "shutdown_secs": sd_secs,
    }))
    trace.close()


if __name__ == "__main__":
    main()
