# app/core/profiling.py
#
# Production-grade timing + memory instrumentation for the LEVIATHAN pipeline.
#
# Usage (context manager):
#   from app.core.profiling import timed_step
#   with timed_step("clean_and_preprocess"):
#       df = clean_and_preprocess(df)
#
# Usage (decorator):
#   @profile_fn
#   def detect_spoofing_events(df): ...
#
# Usage (manual):
#   timer = StepTimer()
#   timer.start("load")
#   ...
#   timer.stop("load")
#   timer.report()

import gc
import logging
import time
import tracemalloc
from contextlib import contextmanager
from functools import wraps
from typing import Optional

logger = logging.getLogger("leviathan.perf")

# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT MANAGER  (recommended for pipeline steps)
# ─────────────────────────────────────────────────────────────────────────────

class _StepContext:
    """Internal context returned by timed_step(). Holds result metrics."""
    elapsed_ms: float = 0.0
    current_mb: float = 0.0
    peak_mb:    float = 0.0


@contextmanager
def timed_step(name: str, df=None, log_shape: bool = True):
    """
    Context manager that measures wall-clock time and peak memory for a pipeline step.

    Example:
        with timed_step("detect_spoofing", df=df_clean) as t:
            result = detect_spoofing_events(df_clean)
        # t.elapsed_ms, t.peak_mb are populated after the block
    """
    ctx = _StepContext()

    if df is not None and log_shape:
        try:
            rows, cols = df.shape
            logger.info(f"[STEP] ▶ {name:<40s} | input {rows:>8,} rows × {cols} cols")
        except Exception:
            pass

    # Force GC before measuring so we get accurate baseline
    gc.collect()
    # BUG-003 FIX: guard against nested timed_step / @profile_fn contexts.
    # tracemalloc.stop() inside an inner context would kill an outer context's
    # measurement.  Only start/stop if we are the outermost tracer.
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    t0 = time.perf_counter()

    try:
        yield ctx
    finally:
        ctx.elapsed_ms = (time.perf_counter() - t0) * 1000
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            ctx.current_mb = current / 1_048_576
            ctx.peak_mb    = peak    / 1_048_576
            if not already_tracing:
                tracemalloc.stop()

        logger.info(
            f"[STEP] ✔ {name:<40s} | "
            f"{ctx.elapsed_ms:>8.1f} ms | "
            f"cur {ctx.current_mb:>6.1f} MB | "
            f"peak {ctx.peak_mb:>6.1f} MB"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DECORATOR  (use on individual functions)
# ─────────────────────────────────────────────────────────────────────────────

def profile_fn(fn):
    """
    Decorator that logs execution time and peak memory for any function.
    Does not change the function's return value or exception behaviour.

    Example:
        @profile_fn
        def detect_spoofing_events(df): ...
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            logger.info(
                f"[PROF] {fn.__qualname__:<45s} | "
                f"{elapsed_ms:>8.1f} ms | peak {peak/1_048_576:>6.1f} MB"
            )
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-STEP TIMER  (accumulate across a full job run)
# ─────────────────────────────────────────────────────────────────────────────

class PipelineTimer:
    """
    Accumulates timing for named steps across an entire ingestion job.

    Example:
        timer = PipelineTimer(job_id="abc123")
        timer.start("ingest")
        ...
        timer.stop("ingest")
        timer.start("spoofing")
        ...
        timer.stop("spoofing")
        timer.report()          # logs a summary table
        perf = timer.to_dict()  # dict suitable for update_job()
    """

    def __init__(self, job_id: Optional[str] = None):
        self._job_id = job_id or "?"
        self._steps: dict = {}         # name → {"t0", "elapsed_ms"}
        self._order: list = []

    def start(self, name: str) -> None:
        self._steps[name] = {"t0": time.perf_counter(), "elapsed_ms": 0.0}
        if name not in self._order:
            self._order.append(name)

    def stop(self, name: str) -> float:
        step = self._steps.get(name)
        if not step:
            return 0.0
        elapsed = (time.perf_counter() - step["t0"]) * 1000
        step["elapsed_ms"] = elapsed
        return elapsed

    def report(self) -> None:
        total = sum(s["elapsed_ms"] for s in self._steps.values())
        logger.info(f"[TIMER] Pipeline timing report — job {self._job_id}")
        logger.info(f"[TIMER] {'Step':<35s} {'ms':>10s}  {'%':>6s}")
        logger.info(f"[TIMER] {'-'*55}")
        for name in self._order:
            ms  = self._steps[name]["elapsed_ms"]
            pct = (ms / total * 100) if total > 0 else 0
            logger.info(f"[TIMER] {name:<35s} {ms:>10.1f}  {pct:>5.1f}%")
        logger.info(f"[TIMER] {'TOTAL':<35s} {total:>10.1f}")

    def to_dict(self) -> dict:
        return {
            "job_id":      self._job_id,
            "step_timings": {
                name: round(self._steps[name]["elapsed_ms"], 1)
                for name in self._order
            },
            "total_ms": round(
                sum(s["elapsed_ms"] for s in self._steps.values()), 1
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# DATAFRAME MEMORY REPORTER  (call after any large transformation)
# ─────────────────────────────────────────────────────────────────────────────

def log_df_memory(df, label: str = "DataFrame") -> None:
    """
    Log per-column dtype and memory usage to identify bloated columns.
    Call this after read_csv or major transformations.

    Output format:
        [MEM] my_df | 206436 rows | total 18.3 MB
        [MEM]   mmsi         int32     0.8 MB
        [MEM]   lat          float32   0.8 MB
        ...
    """
    try:
        total_mb = df.memory_usage(deep=True).sum() / 1_048_576
        logger.info(f"[MEM] {label} | {len(df):,} rows | total {total_mb:.1f} MB")
        for col in df.columns:
            col_mb = df[col].memory_usage(deep=True) / 1_048_576
            logger.info(
                f"[MEM]   {col:<25s} {str(df[col].dtype):<12s} {col_mb:.2f} MB"
            )
    except Exception as e:
        logger.warning(f"[MEM] log_df_memory failed for {label}: {e}")
