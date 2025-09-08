"""Streaming utilities for the generic BESS Digital Twin.

Provides a generator that advances the simulation one step at a time and
returns the updated `BESS_Site` for interactive UIs.
"""

from __future__ import annotations

from typing import Iterator, Optional

from simulation_objects import BESS_Site


def execute_simulation_step(
    site: BESS_Site,
    time_step_s: int,
    max_steps: Optional[int] = None,
) -> Iterator[BESS_Site]:
    """Advance the simulation and yield the site after each step.

    Stops when the site's test state reaches "DONE" or when max_steps is hit.
    """
    steps_run = 0
    while True:
        site.run_time_step(time_step_s)
        steps_run += 1
        yield site

        if site.test_state == 'DONE':
            break
        if max_steps is not None and steps_run >= max_steps:
            break


