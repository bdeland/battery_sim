"""Object model for the generic BESS Digital Twin.

Classes are defined from the bottom up to mirror the physical hierarchy:
- Cell -> BatteryPack -> BatteryRack -> BatteryContainer -> InverterGroup -> BESS_Site

Only class skeletons and essential method signatures are provided initially.
Implementations will be filled in iteratively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import math
import random

import config
import numpy as np


def interpolate_voltage_from_soc(points: List[Tuple[float, float]], soc_percent: float) -> float:
    """Piecewise-linear interpolation of voltage from SOC.

    Args:
        points: List of (soc_percent, voltage) tuples sorted by SOC.
        soc_percent: State of charge in percent [0, 100].

    Returns:
        Interpolated voltage in volts.
    """
    x = max(0.0, min(100.0, soc_percent))
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        if x <= x1:
            # Linear interpolation
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)
    return points[-1][1]


# Precompute SOC curve arrays for vectorized interpolation
_CURVE_SOC = np.array([p[0] for p in config.SOC_VOLTAGE_CURVE], dtype=float)
_CURVE_V = np.array([p[1] for p in config.SOC_VOLTAGE_CURVE], dtype=float)


def interpolate_voltage_from_soc_vectorized(soc_percent: np.ndarray) -> np.ndarray:
    """Vectorized piecewise-linear interpolation using numpy."""
    x = np.clip(soc_percent.astype(float), 0.0, 100.0)
    return np.interp(x, _CURVE_SOC, _CURVE_V)


@dataclass
class Cell:
    soc: float  # percent [0, 100]
    voltage: float
    temperature: float
    current: float = 0.0
    internal_resistance: float = config.CELL_INTERNAL_RESISTANCE_OHMS
    capacity_ah: float = config.CELL_CAPACITY_AH

    def update_soc(self, current_a: float, time_step_s: float) -> None:
        """Update SOC based on current (positive charge, negative discharge)."""
        self.current = current_a
        # amp-seconds to Ah
        delta_ah = (current_a * time_step_s) / 3600.0
        delta_soc = (delta_ah / self.capacity_ah) * 100.0
        self.soc = max(0.0, min(100.0, self.soc + delta_soc))

    def lookup_voltage(self) -> float:
        self.voltage = interpolate_voltage_from_soc(config.SOC_VOLTAGE_CURVE, self.soc)
        return self.voltage

    def calculate_heat_generation(self) -> float:
        """Return heat generation (Watts) using I^2 * R."""
        return (self.current ** 2) * self.internal_resistance


@dataclass
class BatteryPack:
    # Keep optional cells list for compatibility, but use NumPy arrays internally for speed
    cells: List[Cell] = field(default_factory=list)
    coolant_in_temp: float = config.AMBIENT_TEMPERATURE_C
    coolant_out_temp: float = config.AMBIENT_TEMPERATURE_C
    coolant_mass_flow_rate_kg_s: float = 0.0

    # Internal vectorized state (initialized in __post_init__)
    cell_soc: np.ndarray = field(init=False, repr=False)
    cell_voltage: np.ndarray = field(init=False, repr=False)
    cell_temperature: np.ndarray = field(init=False, repr=False)
    cell_current: np.ndarray = field(init=False, repr=False)
    last_total_heat_W: float = field(default=0.0, init=False)

    # Caches
    average_soc: float = field(default=0.0, init=False)
    num_cells: int = field(default=44, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.cells:
            # Convert provided cells to arrays
            self.cell_soc = np.array([c.soc for c in self.cells], dtype=float)
            self.cell_voltage = np.array([c.lookup_voltage() for c in self.cells], dtype=float)
            self.cell_temperature = np.array([c.temperature for c in self.cells], dtype=float)
            self.cell_current = np.zeros(self.num_cells, dtype=float)
        else:
            # Initialize arrays directly with realistic distribution
            n = self.num_cells
            initial_state = (getattr(config, 'SIMULATION_CONFIG', {}) or {}).get('bess_initial_state') or {}
            if initial_state:
                dist_type = str(initial_state.get('soc_distribution_type', 'normal')).lower()
                mean = float(initial_state.get('soc_mean_percent', 8.0))
                std = float(max(1e-6, float(initial_state.get('soc_std_dev_percent', 1.5))))
                if dist_type == 'uniform':
                    self.cell_soc = np.full(n, np.clip(mean, 0.0, 100.0), dtype=float)
                else:
                    samples = np.random.normal(loc=mean, scale=std, size=n).astype(float)
                    self.cell_soc = np.clip(samples, config.MIN_SAFE_SOC, 100.0)
            else:
                initialize_all_min = getattr(config, 'INITIALIZE_ALL_MIN_SOC', False)
                if initialize_all_min:
                    self.cell_soc = np.full(n, config.MIN_SAFE_SOC, dtype=float)
                else:
                    floor_fraction = float(max(0.0, min(1.0, getattr(config, 'INITIAL_SOC_FRACTION_AT_FLOOR', 0.4))))
                    floor_count = int(round(n * floor_fraction))
                    remaining = max(0, n - floor_count)
                    loc = float(getattr(config, 'INITIAL_SOC_MEDIAN_PERCENT', 6.6))
                    scale = float(max(1e-6, getattr(config, 'INITIAL_SOC_STD_PERCENT', 1.2)))
                    low = float(getattr(config, 'INITIAL_SOC_MIN_PERCENT', config.MIN_SAFE_SOC))
                    high = float(getattr(config, 'INITIAL_SOC_MAX_PERCENT', 12.0))
                    samples = np.random.normal(loc=loc, scale=scale, size=remaining).astype(float)
                    samples = np.clip(samples, low, high)
                    if floor_count > 0:
                        floor_arr = np.full(floor_count, config.MIN_SAFE_SOC, dtype=float)
                        self.cell_soc = np.concatenate([floor_arr, samples])
                    else:
                        self.cell_soc = samples
                    # Shuffle to avoid ordered groups
                    if self.cell_soc.size:
                        rng = np.random.default_rng()
                        rng.shuffle(self.cell_soc)
            self.cell_voltage = interpolate_voltage_from_soc_vectorized(self.cell_soc)
            init_temp = None
            if initial_state:
                try:
                    init_temp = float(initial_state.get('cell_temperatures_c'))
                except Exception:
                    init_temp = None
            if init_temp is None:
                init_temp = float(getattr(config, 'AMBIENT_TEMPERATURE_C', 25.0))
            self.cell_temperature = np.full(n, init_temp, dtype=float)
            self.cell_current = np.zeros(n, dtype=float)

        # Initialize cached average SOC
        self.average_soc = float(self.cell_soc.mean())

    def update_state(self, power_w: float, time_step_s: float) -> None:
        """Vectorized per-cell update for current, SOC, voltage, heat, and balancing.

        - Distributes power across cells proportionally to voltage by using sum(V) as divisor.
        - Applies simplified L2 voltage-based SOC calibration.
        - Applies bounded balancing (bleed) in top 6% and bottom 6% windows.
        """
        # Use latest voltages and compute per-cell current assuming even current based on sum of voltages
        soc = self.cell_soc
        self.cell_voltage = interpolate_voltage_from_soc_vectorized(soc)
        sum_voltage = float(self.cell_voltage.sum())
        denom = sum_voltage if sum_voltage > 1e-6 else 1e-6
        current_per_cell = power_w / denom  # Amps for each cell (uniform)
        self.cell_current.fill(current_per_cell)

        # SOC update (scalar math since current is uniform across cells)
        delta_ah = (current_per_cell * time_step_s) / 3600.0
        delta_soc = (delta_ah / float(config.CELL_CAPACITY_AH)) * 100.0
        soc += delta_soc
        np.clip(soc, 0.0, 100.0, out=soc)

        # Recompute voltage after SOC change
        v = interpolate_voltage_from_soc_vectorized(soc)
        self.cell_voltage = v

        # Bounded balancing (resistor bleed) in top/bottom windows
        avg_soc_now = float(soc.mean())
        apply_top = avg_soc_now >= float(getattr(config, 'BALANCING_TOP_SOC_START', 94.0))
        apply_bottom = avg_soc_now <= float(getattr(config, 'BALANCING_BOTTOM_SOC_END', 6.0))
        bleed_heat_W = 0.0
        if apply_top or apply_bottom:
            bleed_current = float(getattr(config, 'BALANCING_BLEED_CURRENT_A', 0.6))
            if bleed_current > 0.0:
                bleed_delta_ah = (bleed_current * time_step_s) / 3600.0
                bleed_delta_soc = (bleed_delta_ah / float(config.CELL_CAPACITY_AH)) * 100.0
                # Bleed only cells above the current average SOC to narrow spread
                mask_bleed = soc > avg_soc_now
                if np.any(mask_bleed):
                    soc[mask_bleed] = np.maximum(0.0, soc[mask_bleed] - bleed_delta_soc)
                    # Extra heat from balancing resistors
                    bleed_count = int(np.count_nonzero(mask_bleed))
                    bleed_heat_W = (bleed_current ** 2) * config.CELL_INTERNAL_RESISTANCE_OHMS * float(bleed_count)
                    np.clip(soc, 0.0, 100.0, out=soc)
                    # Recompute voltage after balancing
                    v = interpolate_voltage_from_soc_vectorized(soc)
                    self.cell_voltage = v

        # L2 calibration masks
        # Low side
        mask_low_cut = v <= config.L2_CUTOFF_LOW_VOLTAGE
        soc[mask_low_cut] = np.maximum(soc[mask_low_cut], config.MIN_SAFE_SOC)
        mask_low_cal = (v > config.L2_CUTOFF_LOW_VOLTAGE) & (v <= config.L2_CALIBRATE_LOW_VOLTAGE)
        soc[mask_low_cal] = np.maximum(soc[mask_low_cal], 6.0)
        # High side
        mask_high_cut = v >= config.L2_CUTOFF_HIGH_VOLTAGE
        soc[mask_high_cut] = np.minimum(soc[mask_high_cut], 100.0)
        mask_high_cal = (v < config.L2_CUTOFF_HIGH_VOLTAGE) & (v >= config.L2_CALIBRATE_HIGH_VOLTAGE)
        soc[mask_high_cal] = np.minimum(soc[mask_high_cal], 99.2)
        np.clip(soc, 0.0, 100.0, out=soc)

        # Heat generation (scalar since current is uniform) and cache
        main_heat_W = (current_per_cell ** 2) * self.num_cells * config.CELL_INTERNAL_RESISTANCE_OHMS
        self.last_total_heat_W = main_heat_W + bleed_heat_W

        # Update cached average SOC
        self.average_soc = float(soc.mean())

    def get_total_heat_generation(self) -> float:
        return self.last_total_heat_W

    def get_average_soc(self) -> float:
        return self.average_soc


@dataclass
class BatteryRack:
    packs: List[BatteryPack] = field(default_factory=list)
    # Cached SOC
    average_soc: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if not self.packs:
            self.packs = [BatteryPack() for _ in range(9)]
        if self.packs:
            self.average_soc = sum(p.get_average_soc() for p in self.packs) / len(self.packs)

    def get_average_soc(self) -> float:
        return self.average_soc

    def update_state(self, power_w: float, time_step_s: float) -> None:
        if not self.packs:
            return
        power_per_pack = power_w / len(self.packs)
        total_soc = 0.0
        for pack in self.packs:
            pack.update_state(power_per_pack, time_step_s)
            total_soc += pack.get_average_soc()
        self.average_soc = total_soc / len(self.packs)


@dataclass
class Chiller:
    max_cooling_capacity_W: float
    total_flow_rate_m3_s: float
    supply_temp_setpoint_C: float
    current_supply_temp_C: float

    def update_supply_temperature(self, return_temp_C: float) -> None:
        """Simplified chiller control to meet setpoint under capacity limits.

        Computes required cooling load and clamps by max capacity. Updates
        current_supply_temp_C as a first-order approach to the setpoint.
        """
        # Required heat removal (simplified): Q = m * cp * dT
        m_dot_kg_s = config.FLUID_DENSITY_KG_M3 * max(self.total_flow_rate_m3_s, 0.0)
        cp = config.FLUID_SPECIFIC_HEAT_J_KG_K
        desired_return_to_supply_delta = max(0.0, return_temp_C - self.supply_temp_setpoint_C)
        q_req = m_dot_kg_s * cp * desired_return_to_supply_delta
        q_actual = min(q_req, self.max_cooling_capacity_W)
        # Translate actual Q to achievable supply temperature (simple proportional model)
        achievable_delta = q_actual / max(1e-6, m_dot_kg_s * cp)
        achievable_supply = max(
            0.0,  # guard temps
            return_temp_C - achievable_delta,
        )
        # First-order filter toward achievable supply
        alpha = 0.5
        self.current_supply_temp_C = (1 - alpha) * self.current_supply_temp_C + alpha * achievable_supply


@dataclass
class BatteryContainer:
    id: str
    racks: List[BatteryRack] = field(default_factory=list)
    chiller: Chiller = field(default_factory=lambda: Chiller(
        max_cooling_capacity_W=40700.0,
        total_flow_rate_m3_s=0.02,
        supply_temp_setpoint_C=20.0,
        current_supply_temp_C=20.0,
    ))
    # Cached container SOC
    soc: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if not self.racks:
            self.racks = [BatteryRack() for _ in range(9)]
        if self.racks:
            self.soc = sum(r.get_average_soc() for r in self.racks) / len(self.racks)

    def update_thermal_fluid_model(self, time_step_s: float) -> None:
        """Update pack temperatures and chiller supply based on heat generation.

        Placeholder implementation with mixed return calculation.
        """
        # Total flow split evenly across all packs
        num_packs = sum(len(rack.packs) for rack in self.racks)
        total_flow_m3_s = self.chiller.total_flow_rate_m3_s
        flow_per_pack_m3_s = total_flow_m3_s / max(1, num_packs)
        m_dot_per_pack_kg_s = flow_per_pack_m3_s * config.FLUID_DENSITY_KG_M3

        supply_temp = self.chiller.current_supply_temp_C
        # Vectorize over all packs and use cached heat directly
        if num_packs:
            q_arr = np.array([pack.get_total_heat_generation() for rack in self.racks for pack in rack.packs], dtype=float)
            cp = config.FLUID_SPECIFIC_HEAT_J_KG_K
            delta_t_arr = q_arr / max(1e-6, m_dot_per_pack_kg_s * cp)
            pack_out_temps = supply_temp + delta_t_arr
            t_return_chiller = float(pack_out_temps.mean())
            # Assign back coolant temps (optional bookkeeping)
            idx = 0
            for rack in self.racks:
                for pack in rack.packs:
                    pack.coolant_in_temp = supply_temp
                    pack.coolant_out_temp = float(pack_out_temps[idx])
                    idx += 1
        else:
            t_return_chiller = supply_temp
        # Update chiller
        self.chiller.update_supply_temperature(t_return_chiller)

    def get_soc(self) -> float:
        return self.soc

    def get_cell_voltage_extrema(self) -> Tuple[float, float]:
        v_min = math.inf
        v_max = -math.inf
        for rack in self.racks:
            for pack in rack.packs:
                if pack.cell_voltage.size:
                    pmin = float(pack.cell_voltage.min())
                    pmax = float(pack.cell_voltage.max())
                    if pmin < v_min:
                        v_min = pmin
                    if pmax > v_max:
                        v_max = pmax
        if v_min is math.inf:
            return 0.0, 0.0
        return v_min, v_max

    def get_min_cell_voltage(self) -> float:
        return self.get_cell_voltage_extrema()[0]

    def get_max_cell_voltage(self) -> float:
        return self.get_cell_voltage_extrema()[1]

    def update_state(self, power_w: float, time_step_s: float) -> None:
        if not self.racks:
            return
        power_per_rack = power_w / len(self.racks)
        total_soc = 0.0
        for rack in self.racks:
            rack.update_state(power_per_rack, time_step_s)
            total_soc += rack.get_average_soc()
        self.soc = total_soc / len(self.racks)
        self.update_thermal_fluid_model(time_step_s)


@dataclass
class InverterGroup:
    id: str
    containers: List[BatteryContainer] = field(default_factory=list)
    last_commanded_power_mw: float = field(default=0.0, init=False)
    last_applied_power_mw: float = field(default=0.0, init=False)

    def update_state(self, power_mw: float, time_step_s: float) -> None:
        # Critical weakest-link logic
        if not self.containers:
            return
        self.last_commanded_power_mw = power_mw
        charging = power_mw > 0
        discharging = power_mw < 0
        if getattr(config, 'WEAK_LINK_CUTOFF_BY_VOLTAGE', True):
            if charging and any(c.get_max_cell_voltage() >= config.L2_CUTOFF_HIGH_VOLTAGE for c in self.containers):
                power_mw = 0.0
            if discharging and any(c.get_min_cell_voltage() <= config.L2_CUTOFF_LOW_VOLTAGE for c in self.containers):
                power_mw = 0.0
        else:
            if charging and any(c.get_soc() >= config.MAX_SAFE_SOC for c in self.containers):
                power_mw = 0.0
            if discharging and any(c.get_soc() <= config.MIN_SAFE_SOC for c in self.containers):
                power_mw = 0.0
        power_w = power_mw * 1e6
        power_per_container_w = power_w / len(self.containers)
        for container in self.containers:
            container.update_state(power_per_container_w, time_step_s)
        self.last_applied_power_mw = power_mw


@dataclass
class BESS_Site:
    inverter_groups: List[InverterGroup]
    current_time_s: int = 0
    test_state: str = 'IDLE'
    state_time_s: int = 0
    current_site_power_target_mw: float = 0.0
    # Optional sequence interpreter state
    _sequence_enabled: bool = field(default=False, init=False, repr=False)
    _sequence: List[dict] = field(default_factory=list, init=False, repr=False)
    _seq_index: int = field(default=0, init=False, repr=False)
    _seq_elapsed_s: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            seq = (getattr(config, 'SIMULATION_CONFIG', {}) or {}).get('test_sequence') or []
            if isinstance(seq, list) and len(seq) > 0:
                self._sequence_enabled = True
                self._sequence = seq
                self.test_state = 'SEQUENCE'
                self.state_time_s = 0
                self._seq_index = 0
                self._seq_elapsed_s = 0
        except Exception:
            self._sequence_enabled = False

    def any_container_soc_at_or_above(self, threshold_percent: float) -> bool:
        for group in self.inverter_groups:
            for container in group.containers:
                if container.get_soc() >= threshold_percent:
                    return True
        return False

    def any_container_soc_at_or_below(self, threshold_percent: float) -> bool:
        for group in self.inverter_groups:
            for container in group.containers:
                if container.get_soc() <= threshold_percent:
                    return True
        return False

    def update_test_state(self, time_step_s: float) -> None:
        if self._sequence_enabled:
            self._update_by_sequence(time_step_s)
            return
        # Full test cycle state machine
        if self.test_state == 'IDLE':
            self.test_state = 'INIT'
            self.state_time_s = 0
            self.current_site_power_target_mw = 0.0
        elif self.test_state == 'INIT':
            # Immediately begin ramp to charge
            self.test_state = 'RAMP_CHARGE'
            self.state_time_s = 0
            self.current_site_power_target_mw = 0.0
        elif self.test_state == 'RAMP_CHARGE':
            dur = int(getattr(config, 'RAMP_DURATION_SECONDS', 30))
            t = self.state_time_s
            frac = min(1.0, t / max(1, dur))
            self.current_site_power_target_mw = frac * config.SITE_TARGET_POWER_MW
            if self.state_time_s >= dur:
                self.test_state = 'CONST_CHARGE'
                self.state_time_s = 0
                self.current_site_power_target_mw = config.SITE_TARGET_POWER_MW
        elif self.test_state == 'CONST_CHARGE':
            self.current_site_power_target_mw = config.SITE_TARGET_POWER_MW
            if self.any_container_soc_at_or_above(float(getattr(config, 'CHARGE_TAPER_SOC_THRESHOLD', 98.0))):
                self.test_state = 'TAPER_TO_REST'
                self.state_time_s = 0
        elif self.test_state == 'TAPER_TO_REST':
            dur = int(getattr(config, 'CHARGE_TAPER_DURATION_SECONDS', 60))
            t = self.state_time_s
            start = config.SITE_TARGET_POWER_MW
            frac = min(1.0, t / max(1, dur))
            self.current_site_power_target_mw = (1.0 - frac) * start
            if self.state_time_s >= dur:
                self.test_state = 'HEAT_SOAK'
                self.state_time_s = 0
                self.current_site_power_target_mw = 0.0
        elif self.test_state == 'HEAT_SOAK':
            self.current_site_power_target_mw = 0.0
            soak_s = int(getattr(config, 'HEAT_SOAK_DURATION_HOURS', 2.0) * 3600)
            if self.state_time_s >= soak_s:
                self.test_state = 'RAMP_DISCHARGE'
                self.state_time_s = 0
        elif self.test_state == 'RAMP_DISCHARGE':
            dur = int(getattr(config, 'RAMP_DURATION_SECONDS', 30))
            t = self.state_time_s
            frac = min(1.0, t / max(1, dur))
            self.current_site_power_target_mw = -frac * config.SITE_TARGET_POWER_MW
            if self.state_time_s >= dur:
                self.test_state = 'CONST_DISCHARGE'
                self.state_time_s = 0
                self.current_site_power_target_mw = -config.SITE_TARGET_POWER_MW
        elif self.test_state == 'CONST_DISCHARGE':
            self.current_site_power_target_mw = -config.SITE_TARGET_POWER_MW
            if self.any_container_soc_at_or_below(float(getattr(config, 'DISCHARGE_TAPER_SOC_THRESHOLD', 8.0))):
                self.test_state = 'TAPER_TO_FINISH'
                self.state_time_s = 0
        elif self.test_state == 'TAPER_TO_FINISH':
            dur = int(getattr(config, 'DISCHARGE_TAPER_DURATION_SECONDS', 60))
            t = self.state_time_s
            start = -config.SITE_TARGET_POWER_MW
            frac = min(1.0, t / max(1, dur))
            self.current_site_power_target_mw = (1.0 - frac) * start
            if self.state_time_s >= dur:
                self.test_state = 'DONE'
                self.state_time_s = 0
                self.current_site_power_target_mw = 0.0
        elif self.test_state == 'DONE':
            self.current_site_power_target_mw = 0.0

        self.state_time_s += time_step_s

    def _update_by_sequence(self, time_step_s: int) -> None:
        if self._seq_index >= len(self._sequence):
            self.test_state = 'DONE'
            self.current_site_power_target_mw = 0.0
            return
        step = self._sequence[self._seq_index]
        # Determine duration in seconds
        dur_s = 0
        if 'duration_seconds' in step:
            dur_s = int(step.get('duration_seconds', 0))
        elif 'duration_minutes' in step:
            dur_s = int(float(step.get('duration_minutes', 0.0)) * 60)
        elif 'duration_hours' in step:
            dur_s = int(float(step.get('duration_hours', 0.0)) * 3600)
        dur_s = max(0, dur_s)

        # Determine power command (only real power used here)
        cmd = step.get('power_command') or {}
        cmd_type = str(cmd.get('command_type', 'idle')).lower()
        if cmd_type == 'idle':
            target_mw = 0.0
        else:
            real_mw = float(cmd.get('real_power_mw', 0.0))
            # Map external convention (negative for charge) to internal (positive for charge)
            target_mw = -real_mw

        # Apply simple linear taper if taper_settings present and duration > 0
        taper = step.get('taper_settings') or None
        if taper and dur_s > 0:
            try:
                end_power_mw = float(taper.get('end_power_mw', target_mw))
                frac = min(1.0, max(0.0, self._seq_elapsed_s / max(1, dur_s)))
                target_mw = (1.0 - frac) * target_mw + frac * end_power_mw
            except Exception:
                pass

        self.current_site_power_target_mw = target_mw
        self.state_time_s = self._seq_elapsed_s
        self.test_state = step.get('step_name', 'SEQUENCE')
        self._seq_elapsed_s += time_step_s
        if self._seq_elapsed_s >= dur_s:
            self._seq_index += 1
            self._seq_elapsed_s = 0

    def get_site_target_power(self) -> float:
        return self.current_site_power_target_mw

    def run_time_step(self, time_step_s: float) -> None:
        self.update_test_state(time_step_s)
        target_power_mw = self.get_site_target_power()
        if not self.inverter_groups:
            self.current_time_s += time_step_s
            return
        power_per_group_mw = target_power_mw / len(self.inverter_groups)
        for group in self.inverter_groups:
            group.update_state(power_per_group_mw, time_step_s)
        self.current_time_s += time_step_s


