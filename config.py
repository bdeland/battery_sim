

# -------------------------------
# File paths
# -------------------------------

OUTPUT_CSV_PATH = 'outputs/simulation_results.csv'
PLOT_OUTPUT_DIR = 'outputs/'

# -------------------------------
# Simulation control
# -------------------------------
TIME_STEP_SECONDS = 1  # Simulation resolution in seconds
SIMULATION_DURATION_HOURS = 10  # Duration of the run

# Convenience derived value
TOTAL_STEPS = int(SIMULATION_DURATION_HOURS * 3600 / TIME_STEP_SECONDS)

# Optional structured configuration based on docs/improvements.md (Steps 3 and 4)
SIMULATION_CONFIG = {
    'simulation_control': {
        'start_datetime_utc': None,
        'duration_hours': SIMULATION_DURATION_HOURS,
        'time_step_seconds': TIME_STEP_SECONDS,
    },
    'environmental_conditions': {
        'mode': 'constant',
        'ambient_temperature_c': 35.0,
        'solar_irradiance_w_per_m2': 800.0,
        # Historical mode example shape (not active by default)
        'location': None,
        'historical_data_provider': None,
    },
    'bess_initial_state': {
        'soc_distribution_type': 'normal',  # 'uniform' | 'normal'
        'soc_mean_percent': 8.0,
        'soc_std_dev_percent': 1.5,
        'cell_temperatures_c': 25.0,
    },
    'test_sequence': [
        # Example default sequence matching the existing state machine semantics
        # Charge ramp and hold implied by explicit durations here
        {
            'step_name': 'Charge',
            'duration_minutes': 60,
            'power_command': {
                'command_type': 'real',
                'real_power_mw': 40.0
            },
            # optional taper example; interpreter will ignore if missing
            'taper_settings': {
                'start_soc_percent': 98.0,
                'end_power_mw': 0.0
            }
        },
        {
            'step_name': 'Heat Soak',
            'duration_hours': 2.0,
            'power_command': {'command_type': 'idle'}
        },
        {
            'step_name': 'Discharge',
            'duration_minutes': 60,
            'power_command': {
                'command_type': 'real',
                'real_power_mw': -40.0
            }
        }
    ]
}

# -------------------------------
# Layout configuration
# -------------------------------
# If provided, this list defines the number of containers for each inverter group
# in order. Example: [3,3,3,3,3,2,2,4]
INVERTER_GROUP_CONTAINER_COUNTS = []

# Fallback uniform layout when the above list is empty
NUM_INVERTER_GROUPS = 2
CONTAINERS_PER_GROUP = 2

# -------------------------------
# Test cycle parameters
# -------------------------------
SITE_TARGET_POWER_MW = 40.0
RAMP_DURATION_SECONDS = 30
CHARGE_TAPER_DURATION_SECONDS = 60
DISCHARGE_TAPER_DURATION_SECONDS = 60
CHARGE_TAPER_SOC_THRESHOLD = 98.0  # %
DISCHARGE_TAPER_SOC_THRESHOLD = 8.0  # %
HEAT_SOAK_DURATION_HOURS = 2.0

# -------------------------------
# BMS logic thresholds
# -------------------------------
L2_CALIBRATE_LOW_VOLTAGE = 3.0  # V -> Calibrates SOC to 6.0%
L2_CUTOFF_LOW_VOLTAGE = 2.8  # V -> Calibrates SOC to 5.2%
L2_CALIBRATE_HIGH_VOLTAGE = 3.45  # V -> Calibrates SOC to 99.2%
L2_CUTOFF_HIGH_VOLTAGE = 3.6  # V -> Calibrates SOC to 100.0%
MIN_SAFE_SOC = 5.2  # %
MAX_SAFE_SOC = 100.0  # %
WEAK_LINK_CUTOFF_BY_VOLTAGE = True

# -------------------------------
# Physical & thermal constants
# -------------------------------
AMBIENT_TEMPERATURE_C = 35.0

# Fluid (50% Ethylene Glycol)
FLUID_DENSITY_KG_M3 = 1075
FLUID_SPECIFIC_HEAT_J_KG_K = 3500

# -------------------------------
# Cell properties
# -------------------------------
CELL_CAPACITY_AH = 300.0
CELL_INTERNAL_RESISTANCE_OHMS = 0.0005  # Small, realistic internal resistance

# Simple SOC -> voltage lookup table (approximate LFP curve; SOC in %, Voltage in V)
# These points are intended for piecewise-linear interpolation
SOC_VOLTAGE_CURVE = [
    (0.0, 2.50),
    (5.0, 2.80),
    (10.0, 3.10),
    (20.0, 3.20),
    (30.0, 3.25),
    (40.0, 3.30),
    (50.0, 3.32),
    (60.0, 3.35),
    (70.0, 3.40),
    (80.0, 3.45),
    (90.0, 3.55),
    (95.0, 3.60),
    (100.0, 3.65),
]

# -------------------------------
# Initial SOC distribution
# -------------------------------
# Target a realistic spread with a median around 6.6% and a significant fraction at the floor
INITIAL_SOC_MEDIAN_PERCENT = 6.6
INITIAL_SOC_STD_PERCENT = 1.2
INITIAL_SOC_MIN_PERCENT = MIN_SAFE_SOC
INITIAL_SOC_MAX_PERCENT = 12.0
INITIAL_SOC_FRACTION_AT_FLOOR = 0.4  # ~40% of cells start at floor
INITIALIZE_ALL_MIN_SOC = False

# -------------------------------
# Balancing behavior
# -------------------------------
# Simple resistor-bleed model near the top and bottom windows
BALANCING_TOP_SOC_START = 94.0
BALANCING_BOTTOM_SOC_END = 6.0
BALANCING_BLEED_CURRENT_A = 0.6  # small per-cell bleed current


# Apply SIMULATION_CONFIG to legacy globals for backward compatibility
def _apply_simulation_config() -> None:
    global TIME_STEP_SECONDS, SIMULATION_DURATION_HOURS, TOTAL_STEPS
    global AMBIENT_TEMPERATURE_C

    try:
        sim_ctrl = SIMULATION_CONFIG.get('simulation_control') or {}
        TIME_STEP_SECONDS = int(sim_ctrl.get('time_step_seconds', TIME_STEP_SECONDS))
        SIMULATION_DURATION_HOURS = float(sim_ctrl.get('duration_hours', SIMULATION_DURATION_HOURS))
        TOTAL_STEPS = int(SIMULATION_DURATION_HOURS * 3600 / max(1, TIME_STEP_SECONDS))

        env = SIMULATION_CONFIG.get('environmental_conditions') or {}
        if (env.get('mode') or 'constant') == 'constant':
            AMBIENT_TEMPERATURE_C = float(env.get('ambient_temperature_c', AMBIENT_TEMPERATURE_C))
    except Exception:
        # Fail-safe: keep legacy defaults if SIMULATION_CONFIG is malformed
        pass


_apply_simulation_config()


