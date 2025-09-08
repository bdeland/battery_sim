

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


