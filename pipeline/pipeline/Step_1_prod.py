import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
from enum import Enum
from Functions_step_1 import map_location, next_state, string_to_index, sample_departure_time, value_to_index #sample_initial_soc


class DayType(Enum):
    MON_THU  = 'Mon-Thu'   # Standard workday
    FRIDAY   = 'Friday'    # Workday + higher leisure/shopping probability after work
    SATURDAY = 'Saturday'  # No commute, leisure dominant, later departures
    SUNDAY   = 'Sunday'    # Lowest mobility, personal/leisure only
    HOLIDAY  = 'Holiday'   # Same as Sunday

# ---------------------------------------- # Definiran delovnik # ---------------------------------------- #
def sample_work_start():
    return np.random.uniform(7,9)

def sample_work_duration():
    return np.random.uniform(7,9)

# ---------------------------------------- # Import NHTS data results # ---------------------------------------- #

version = 1
df_index = pd.read_excel(f'Selected_profiles_v{version}.xlsx')
selected_profiles_index = df_index.iloc[:, 1]

df_start_time = pd.read_excel(f'df_start_time_15min_v{version}.xlsx')
df_start_time = df_start_time.iloc[:, 1:]
df_start_time = df_start_time.iloc[selected_profiles_index]

df_end_time = pd.read_excel(f'df_end_time_15min_v{version}.xlsx')
df_end_time = df_end_time.iloc[:, 1:]
df_end_time = df_end_time.iloc[selected_profiles_index]

df_start_location = pd.read_excel(f'df_start_location_v{version}.xlsx')
df_start_location = df_start_location.iloc[:, 1:]
df_start_location = df_start_location.iloc[selected_profiles_index]

profiles_df = df_start_location

df_end_location = pd.read_excel(f'df_end_location_v{version}.xlsx')
df_end_location = df_end_location.iloc[:, 1:]
df_end_location = df_end_location.iloc[selected_profiles_index]

df_prob = pd.read_excel(f'df_gauss_v{version}.xlsx')

hourly_prob = pd.to_numeric(df_prob.iloc[:,1], errors='coerce').fillna(0).values

trips_probability = np.repeat(hourly_prob, 4)

trips_probability = trips_probability / trips_probability.sum()

print("len trips_probability:", len(trips_probability))
print(len(trips_probability))
print(sum(trips_probability))

# Prevent trips before 6am for Slovenia
trips_probability[:24] = 0  # 6 hours * 4 intervals/hour = 24
trips_probability = trips_probability / trips_probability.sum()


# ---------------------------------------- # Import Gauss fitting parameters # ---------------------------------------- #

# Kalibrirano na slovensko statistiko (SURS, Dnevna mobilnost potnikov 2021,
# stat.si/StatWeb/News/Index/10324, neposredno preverjeno): povprečje 23 min.
# POMEMBNO: scale != mean-loc, ker je porazdelitev odsekana pri 60 min in
# diskretizirana na 1000 točk (glej spodaj) — to sistematično zniža povprečje.
# scale=24.5 je numerično poiskan tako, da JE PO odsekanju/diskretizaciji
# resnično povprečje 23.0 min (preverjeno: analitično 23.0007, MC N=100k: 22.96).
# Glej Step_1_fit_si.py za izpeljavo in validacijo.
trip_duration_params = np.array([5.0, 24.5])
x_axis_trips = np.linspace(0, 60, 1000)
trips_distribution = (1 / trip_duration_params[1]) * np.exp(-(x_axis_trips - trip_duration_params[0]) / trip_duration_params[1])
trips_distribution[x_axis_trips < trip_duration_params[0]] = 0


# ---------------------------------------- # Preparation # ---------------------------------------- #

#trips_probability = df_prob
days_week = [
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.FRIDAY,
    DayType.SATURDAY,
    DayType.SUNDAY,
]
states = ['Home', 'Work', 'Business', 'Education', 'Shopping', 'Transport', 'Leisure', 'Personal']


df_start_location = map_location(df_start_location)
df_end_location = map_location(df_end_location)

intervals_in_day = 24*4
profiles_df = pd.DataFrame(index=range(len(df_start_time)), columns=range(1, intervals_in_day+1))


# ---------------------------------------- # Create daily profiles # ---------------------------------------- #

for day in range(len(df_start_time)):
    start_time = df_start_time.iloc[day, :]
    start_time = start_time[pd.notna(start_time)].values
    # print(f'Profile {day+1} departure time: {start_time}')

    end_time = df_end_time.iloc[day, :]
    end_time = end_time[pd.notna(end_time)].values
    # print(f'Profile {day+1} arrival time: {end_time}')

    start_location = df_start_location.iloc[day, :]
    start_location = start_location[pd.notna(start_location)].values
    # print(f'Profile {day+1} departure location: {start_location}')

    end_location = df_end_location.iloc[day, :]
    end_location = end_location[pd.notna(end_location)].values
    # print(f'Profile {day + 1} departure location: {end_location}')

    for start, end, departure_location, arrival_location in zip(start_time, end_time, start_location, end_location):
        # print(start, end, departure_location, arrival_location)
        start_index = string_to_index(start)
        end_index = string_to_index(end)
        # print(f'Start index: {start_index}')
        # print(f'End index: {end_index}')

        if start == start_time[0]:
            profiles_df.iloc[day, 0:start_index] = departure_location
            # print(profiles_df.iloc[day])
        # profiles_df.iloc[day, start_index:end_index] = 'Drive'
        profiles_df.iloc[day, start_index:end_index] = arrival_location

        # print(profiles_df.iloc[day])
        profiles_df.iloc[day, end_index:] = arrival_location
        # print(profiles_df.iloc[day])


# -------- USER PROFILE DEFINITIONS -------- #

class UserProfile:
    """Base class for user profiles."""
    def __init__(self, profile_name, allowed_purposes, work_required=False):
        self.name = profile_name
        self.allowed_purposes = allowed_purposes  # List of allowed trip types
        self.work_required = work_required  # Must include 'Work' trip

    def can_use_purpose(self, trip_purpose):
        """Check if trip purpose is allowed for this profile."""
        return trip_purpose in self.allowed_purposes

    def validate_chain(self, trip_chain):
        """Check if trip chain satisfies profile constraints."""
        if self.work_required and 'Work' not in trip_chain:
            return False
        return all(purpose in self.allowed_purposes for purpose in trip_chain)

class CommuterProfile(UserProfile):
    """Commuter profile - must include Work, flexible beyond that."""
    def __init__(self):
        allowed = ['Home', 'Work', 'Personal', 'Shopping', 'Leisure', 'Business', 'Transport', 'Education']
        super().__init__('Commuter', allowed, work_required=True)

    def get_work_start_time(self):
        """Commuter leaves work between 7-9 AM."""
        return np.random.uniform(7, 9)

    def get_work_duration(self):
        """Commuter typically works 7-9 hours."""
        return np.random.uniform(7, 9)

    def get_trip_count_weights(self, day_type: 'DayType') -> list:
        # Commuters almost always leave home (work obligation).
        # Fridays see more trip chaining (errand after work).
        # Source: NHTS 2017 — employed persons avg 4.2 trips/day vs 2.8 for retired.
        return {
            DayType.MON_THU:  [0.02, 0.73, 0.25],
            DayType.FRIDAY:   [0.02, 0.58, 0.40],
            DayType.SATURDAY: [0.15, 0.60, 0.25],
            DayType.SUNDAY:   [0.30, 0.60, 0.10],
            DayType.HOLIDAY:  [0.35, 0.55, 0.10],
        }[day_type]

class RetiredProfile(UserProfile):
    """Retired profile - no Work, leisure and personal focus."""
    def __init__(self):
        allowed = ['Home', 'Leisure', 'Shopping', 'Personal']
        super().__init__('Retired', allowed, work_required=False)

    def flexible_timing(self):
        """Retired users have flexible departure times (no peak-hour constraints)."""
        return True

    def get_trip_count_weights(self, day_type: 'DayType') -> list:
        # Retired persons have significantly higher stay-home rates and fewer
        # multi-stop trip chains. Source: Pucher & Renne (2003); NHTS 2017.
        return {
            DayType.MON_THU:  [0.45, 0.45, 0.10],
            DayType.FRIDAY:   [0.40, 0.45, 0.15],
            DayType.SATURDAY: [0.45, 0.42, 0.13],
            DayType.SUNDAY:   [0.55, 0.38, 0.07],
            DayType.HOLIDAY:  [0.55, 0.38, 0.07],
        }[day_type]

class NoncommuterProfile(UserProfile):
    """Non-commuter profile - typically excludes Work, more diverse than retired."""
    def __init__(self):
        allowed = ['Home', 'Leisure', 'Shopping', 'Personal', 'Business', 'Education', 'Transport']
        super().__init__('Nonccommuter', allowed, work_required=False)

    def flexible_timing(self):
        """Non-commuters have medium temporal structure."""
        return True

    def get_trip_count_weights(self, day_type: 'DayType') -> list:
        # Non-commuters (students, inactive 15-64, children) have moderate mobility —
        # more active than retired but without the work obligation of commuters.
        # Source: McGuckin & Nakamoto (2004); SURS transport surveys.
        return {
            DayType.MON_THU:  [0.20, 0.60, 0.20],
            DayType.FRIDAY:   [0.18, 0.55, 0.27],
            DayType.SATURDAY: [0.25, 0.55, 0.20],
            DayType.SUNDAY:   [0.35, 0.55, 0.10],
            DayType.HOLIDAY:  [0.38, 0.52, 0.10],
        }[day_type]

# Source: SiStat demographic data, Krško municipality, 1 Jan 2025
# Commuter  = delovno aktivni po prebivališču  (11,748 / 26,175)
# Retired   = 65+ residents                    (5,654  / 26,175)
# Noncommuter = 0-14 + inactive 15-64          (8,773  / 26,175)
PROFILE_DISTRIBUTION = {
    'Commuter':    0.449,
    'Retired':     0.216,
    'Nonccommuter': 0.335
}

PROFILE_CLASSES = {
    'Commuter': CommuterProfile(),
    'Retired': RetiredProfile(),
    'Nonccommuter': NoncommuterProfile()
}

def assign_profiles(number_of_vehicles):
    """
    Assign user profiles to vehicles based on probabilistic distribution.

    Returns:
        list: Profile object for each vehicle (index = vehicle_id - 1)
    """
    profiles = np.random.choice(
        list(PROFILE_DISTRIBUTION.keys()),
        size=number_of_vehicles,
        p=list(PROFILE_DISTRIBUTION.values())
    )
    return [PROFILE_CLASSES[profile] for profile in profiles]


def next_state_constrained(interval, state, profiles_df_arg, allowed_purposes):
    """
    Select next trip purpose from transition matrix,
    but only from purposes allowed by current profile.

    Args:
        interval: Current time interval
        state: Current location state
        profiles_df_arg: DataFrame with location states
        allowed_purposes: List of allowed trip types for this profile

    Returns:
        probability: Weighted probability distribution (filtered)
        next_trip: Selected next trip purpose (or 'None' if unavailable)
    """
    current_states = profiles_df_arg.iloc[:, interval]
    previous_states = profiles_df_arg.iloc[:, interval - 1]

    transition_matrix = pd.DataFrame(0, index=states, columns=states)

    for prev_state, curr_state in zip(previous_states, current_states):
        if prev_state in states and curr_state in states:
            if prev_state == curr_state:
                transition_matrix.loc[prev_state, curr_state] = 0
            else:
                transition_matrix.loc[prev_state, curr_state] += 1

    prob_matrix = transition_matrix.div(transition_matrix.sum(axis=1), axis=0).fillna(0)
    probability = prob_matrix.loc[state]

    # FILTER: Zero out disallowed purposes
    filtered_probability = probability.copy()
    for purpose in probability.index:
        if purpose not in allowed_purposes:
            filtered_probability[purpose] = 0

    # Renormalize probabilities
    prob_sum = filtered_probability.sum()
    if prob_sum > 0.001:
        filtered_probability = filtered_probability / prob_sum
        next_trip = np.random.choice(filtered_probability.index, p=filtered_probability.values)
    else:
        next_trip = 'None'

    return filtered_probability, next_trip


def validate_chain_consistency(trip_chain: list, profile, day_type: DayType) -> tuple:
    """
    Validates a generated daily trip chain for logical consistency.
    trip_chain is chosen_distribution: a flat list of trip destination types
    (e.g. ['Work', 'Work'] or ['Leisure', 'Shopping']).  Home is NOT included as
    a frame — the round-trip return is handled implicitly by Step_2.

    Rules:
    1. Chain must not be empty.
    2. 'Work' is only allowed for Commuter profile AND on workday-type days.
    3. Commuter on a workday must have at least one 'Work' trip.

    Returns:
        (True, '') if valid, or (False, reason_string) if invalid.
    """
    if len(trip_chain) < 1:
        return False, "Chain is empty"

    work_count = trip_chain.count('Work')

    if work_count > 0 and not profile.work_required:
        return False, f"'Work' in chain but profile '{profile.name}' does not allow Work trips"

    if work_count > 0 and day_type in (DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
        return False, f"'Work' in chain on non-workday ({day_type.value})"

    if (profile.work_required
            and day_type not in (DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY)
            and work_count == 0):
        return False, f"Commuter has no 'Work' trip on workday ({day_type.value})"

    return True, ''

def get_day_config(day_type: DayType) -> dict:
    """
    Returns trip-generation config for each day type.
    'trip_count_weights': probability of [0, 2, 4] trips that day.
    'purpose_boost': multiplier applied on top of Markov for specific purposes.
    'departure_shift_h': shift the departure time distribution by this many hours (positive = later).
    """
    configs = {
        DayType.MON_THU: {
            'trip_count_weights': [0.0, 0.80, 0.20],
            'purpose_boost': {},
            'departure_shift_h': 0.0,
        },
        DayType.FRIDAY: {
            'trip_count_weights': [0.0, 0.70, 0.30],
            'purpose_boost': {'Leisure': 1.4, 'Shopping': 1.3},
            'departure_shift_h': 0.0,
        },
        DayType.SATURDAY: {
            'trip_count_weights': [0.10, 0.65, 0.25],
            'purpose_boost': {'Leisure': 1.8, 'Shopping': 1.6, 'Personal': 1.2},
            'departure_shift_h': 1.5,
        },
        DayType.SUNDAY: {
            'trip_count_weights': [0.20, 0.70, 0.10],
            'purpose_boost': {'Leisure': 2.0, 'Personal': 1.3},
            'departure_shift_h': 2.0,
        },
        DayType.HOLIDAY: {
            'trip_count_weights': [0.25, 0.65, 0.10],
            'purpose_boost': {'Leisure': 2.2},
            'departure_shift_h': 2.5,
        },
    }
    return configs[day_type]


# ---------------------------------------- # Main function for generating trip parameters # ---------------------------------------- #

def get_trip_parameters(number_of_vehicles, number_of_trips, number_of_days):
    days = days_week[:number_of_days]

    # ===== NEW: ASSIGN PROFILES TO VEHICLES =====
    vehicle_profiles = assign_profiles(number_of_vehicles)
    print(f"\n=== PROFILE ASSIGNMENT ===")
    for i, profile in enumerate(vehicle_profiles):
        print(f"Vehicle {i+1}: {profile.name}")
    # ===========================================

    # ===== INITIAL SOC ASSIGNMENT =====
   # vehicle_soc = {
    #    vehicle: sample_initial_soc(vehicle_profiles[vehicle])
     #   for vehicle in range(number_of_vehicles)
    #}
    #print(f"\n=== INITIAL SOC ASSIGNMENT ===")
    #for vehicle_id, soc in vehicle_soc.items():
    #    print(f"Vehicle {vehicle_id + 1} ({vehicle_profiles[vehicle_id].name}): {soc:.1f}%")
    # ===================================

    trips_start_index_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))
    trips_end_index_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))
    trips_matrix_week = [[] for _ in range(number_of_vehicles * len(days))]
    trips_duration_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))

    total_chains = 0
    rejected_chains = 0

    for day in range(len(days)):
        day_config = get_day_config(days[day])
        if True:
            trips_start_index_matrix_day = np.zeros((number_of_vehicles, number_of_trips))
            trips_end_index_matrix_day = np.zeros((number_of_vehicles, number_of_trips))
            trips_matrix_day = [[] for _ in range(number_of_vehicles)]
            trips_duration_matrix_day = np.zeros((number_of_vehicles, number_of_trips))

            for vehicle in range(number_of_vehicles):
                profile = vehicle_profiles[vehicle]  # NEW
                print(f'Vehicle ID {vehicle+1} - Profile: {profile.name}')  # MODIFIED

                # Skip vehicle if it stays home today (weights are profile-specific)
                number_of_trips_today = np.random.choice(
                    [0, 2, 4],
                    p=profile.get_trip_count_weights(days[day])
                )
                if number_of_trips_today == 0:
                    print(f'Vehicle {vehicle+1} stays home on {days[day].value}.')
                    # Placeholder chain so downstream export (which always reads
                    # `number_of_trips` entries per vehicle) doesn't index into an
                    # empty list. Start/end/duration stay at their zero default.
                    trips_matrix_day[vehicle] = ['Home'] * number_of_trips
                    continue

                # On non-workdays remove Work from allowed purposes for all profiles
                if days[day] in (DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
                    effective_purposes = [p for p in profile.allowed_purposes if p != 'Work']
                else:
                    effective_purposes = profile.allowed_purposes

                success = False
                retry_outer = 0
                while not success and retry_outer < 50:
                    retry_outer += 1
                    try:

                        trip_counter = 0  # Trip number counter
                        rnd_dist = []
                        rnd_dists = []
                        rnd_value = []
                        chosen_distribution = []
                        rnd_strategy = []
                        chosen_values = np.zeros(number_of_trips)  # Starting hour of selected trip
                        chosen_values_after_trip = np.zeros(number_of_trips)
                        chosen_index = np.zeros(number_of_trips)  # Indexes of selected trips beginnings
                        chosen_trips = np.zeros(number_of_trips)  # Selected trip duration in minutes
                        trips_start_index = np.zeros(number_of_trips)  # Indexes of selected trips beginnings
                        trips_end_index = np.zeros(number_of_trips)  # Indexes of selected trips endings
                        strategies = ['A', 'B']

                        while trip_counter < number_of_trips:
                            while True:

                                x = np.linspace(0, 23.75, 96)

                                if number_of_trips == 2:
                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                    print(f'Randomly sampled departure time: {rnd_departure_time}')
                                    # chosen_values[trip_counter] = rnd_departure_time
                                    # print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                    if trip_counter == 0:
                                        while True:
                                            # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                            # print(f'Randomly sampled departure time (h): {rnd_departure_time}')


                                            rnd_departure_time = sample_work_start()

                                            chosen_values[trip_counter] = rnd_departure_time  # preimenuj u trip_start_time ako želiš
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                            index = int(value_to_index(rnd_departure_time))

                                            try:
                                                probability, rnd_dist = next_state_constrained(index, 'Home', profiles_df, effective_purposes)
                                                print(f'Probability: {probability}')
                                                print(f'Next trip purpose: {rnd_dist}')

                                                if rnd_dist == 'None':
                                                    print("rnd_dist is None — restarting selection...")
                                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                    print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                    continue

                                                chosen_distribution.append(rnd_dist)
                                                break

                                            except Exception as e:
                                                print(f"Exception in next_state: {e}. Restarting...")
                                                continue

                                    if trip_counter == 1:
                                        if chosen_distribution[0] in ['Work']:

                                            if day == 4:  # Friday
                                                end_time = np.random.uniform(14.5, 16.5)
                                            else:
                                                end_time = np.random.uniform(15, 17.5)

                                            rnd_departure_time = end_time

                                            chosen_values[trip_counter] = rnd_departure_time
                                        if rnd_dist in ['Work']:
                                            rnd_dist = chosen_distribution[0]
                                            chosen_distribution.append(rnd_dist)
                                            print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                            chosen_distribution[trip_counter] = rnd_dist
                                            print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                            print(f'Chosen_distribution: {chosen_distribution}')

                                            iteration = 2
                                            while not (chosen_values_after_trip[trip_counter - 1] + 7 < rnd_departure_time <
                                                       chosen_values_after_trip[trip_counter - 1] + 9 and rnd_departure_time >
                                                       chosen_values_after_trip[trip_counter - 1]):
                                                rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                iteration += 1
                                            chosen_values[trip_counter] = rnd_departure_time
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                        else:
                                            rnd_dist = chosen_distribution[0]
                                            chosen_distribution.append(rnd_dist)
                                            print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                            chosen_distribution[trip_counter] = rnd_dist
                                            print(
                                                f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                            print(f'Chosen_distribution: {chosen_distribution}')

                                            iteration = 2
                                            while not (rnd_departure_time > (
                                                    chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                print(
                                                    f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                iteration += 1
                                            chosen_values[trip_counter] = rnd_departure_time
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                if number_of_trips == 4:
                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                    print(f'Randomly sampled departure time (h): {rnd_departure_time}')

                                    # travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                    # print(f'Randomly sampled travel time (min): {travel_time}')
                                    # iteration = 2
                                    # while not travel_time >= 5:  # Minimal trip duration
                                    #     travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                    #     print(f'Randomly sampled travel time in {iteration}. iteration (min): {travel_time}')
                                    #     iteration += 1
                                    #
                                    # travel_time_intervals = np.ceil(travel_time/15)
                                    # print(f'Travel time in intervals : {travel_time_intervals}')
                                    #
                                    # arrival_time = rnd_departure_time + travel_time/60
                                    # print(f'Arrival time (h): {arrival_time}')

                                    if trip_counter == 0:

                                        while True:
                                            # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                            # print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                            while rnd_departure_time > 11:
                                                rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                            chosen_values[trip_counter] = rnd_departure_time  # preimenuj u trip_start_time ako želiš
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                            index = int(value_to_index(rnd_departure_time))

                                            try:
                                                probability, rnd_dist = next_state_constrained(index, 'Home', profiles_df, effective_purposes)
                                                print(f'Probability: {probability}')
                                                print(f'Next trip purpose: {rnd_dist}')

                                                if rnd_dist == 'None':
                                                    print("rnd_dist is None — restarting selection...")
                                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                    print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                    continue

                                                chosen_distribution.append(rnd_dist)
                                                break

                                            except Exception as e:
                                                print(f"Exception in next_state: {e}. Restarting...")
                                                continue

                                        if 'Work' in chosen_distribution:
                                            rnd_strategy = np.random.choice(strategies)
                                            print(f'Work is first trip purpose with strategy: {rnd_strategy}')

                                    if 'Work' in chosen_distribution:
                                        if rnd_strategy == 'A':
                                            if trip_counter == 1:
                                                while True:
                                                    # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                    # print(f'Randomly sampled departure time: {rnd_departure_time}')
                                                    iteration = 2
                                                    while not (10 < rnd_departure_time < 13 and rnd_departure_time > (chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                        rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                        print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                        iteration += 1
                                                    chosen_values[trip_counter] = rnd_departure_time
                                                    print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                                    index = int(value_to_index(rnd_departure_time))

                                                    try:
                                                        probability, rnd_dist = next_state_constrained(index, chosen_distribution[0], profiles_df, effective_purposes)
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                        while rnd_dist == 'Home':
                                                            probability, rnd_dist = next_state_constrained(index, chosen_distribution[0], profiles_df, effective_purposes)
                                                            print(f'Probability: {probability}')
                                                            print(f'Next trip purpose: {rnd_dist}')

                                                        if rnd_dist == 'None':
                                                            print("rnd_dist is None — restarting block...")
                                                            rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                            print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                            continue

                                                        chosen_distribution.append(rnd_dist)
                                                        break

                                                    except Exception as e:
                                                        print(f"Exception in next_state: {e}. Restarting block...")
                                                        continue

                                            elif trip_counter == 2:
                                                rnd_dist = chosen_distribution[1]
                                                chosen_distribution.append(rnd_dist)
                                                print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                                chosen_distribution[trip_counter] = rnd_dist
                                                print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                                print(f'Chosen_distribution: {chosen_distribution}')

                                                # rnd_departure_time = np.random.choice(x, p=trips_probability/sum(trips_probability))
                                                # print(f'Randomly sampled departure time: {rnd_departure_time}')
                                                iteration = 2
                                                while not chosen_values_after_trip[trip_counter - 1] + 0.25 < rnd_departure_time < \
                                                          chosen_values_after_trip[trip_counter - 1] + 1:
                                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                    print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                    iteration += 1
                                                chosen_values[trip_counter] = rnd_departure_time
                                                print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                            elif trip_counter == 3:
                                                rnd_dist = chosen_distribution[0]
                                                chosen_distribution.append(rnd_dist)
                                                print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                                chosen_distribution[trip_counter] = rnd_dist
                                                print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                                print(f'Chosen_distribution: {chosen_distribution}')

                                                iteration = 2
                                                # while not (rnd_departure_time > chosen_values_after_trip[trip_counter - 1] and rnd_departure_time > chosen_values_after_trip[0]):
                                                while not rnd_departure_time > (chosen_values_after_trip[trip_counter - 1] + 0.25):
                                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                    print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                    iteration += 1
                                                chosen_values[trip_counter] = rnd_departure_time
                                                print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                        if rnd_strategy == 'B':
                                            if trip_counter == 1:
                                                rnd_dist = chosen_distribution[0]
                                                chosen_distribution.append(rnd_dist)
                                                print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                                chosen_distribution[trip_counter] = rnd_dist
                                                print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                                print(f'Chosen_distribution: {chosen_distribution}')

                                                iteration = 2
                                                while not (chosen_values_after_trip[trip_counter - 1] + 7 < rnd_departure_time < chosen_values_after_trip[trip_counter - 1] + 9 and rnd_departure_time > chosen_values_after_trip[trip_counter - 1]):
                                                    rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                    print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                    iteration += 1
                                                chosen_values[trip_counter] = rnd_departure_time
                                                print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                            elif trip_counter == 2:
                                                while True:
                                                    # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                    # print(f'Randomly sampled departure time: {rnd_departure_time}')
                                                    rnd_departure_time = sample_departure_time(min_after_previous=0.25, previous_end_time=chosen_values_after_trip[trip_counter - 1], distribution=trips_probability)
                                                    chosen_values[trip_counter] = rnd_departure_time
                                                    print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                                    index = int(value_to_index(rnd_departure_time))

                                                    try:
                                                        probability, rnd_dist = next_state_constrained(index, 'Home', profiles_df, effective_purposes)
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                        while rnd_dist == 'Home':
                                                            probability, rnd_dist = next_state_constrained(index, chosen_distribution[0], profiles_df, effective_purposes)
                                                            print(f'Probability: {probability}')
                                                            print(f'Next trip purpose: {rnd_dist}')

                                                        if rnd_dist == 'None':
                                                            print("rnd_dist is None — restarting trip selection...")
                                                            rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                            print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                            continue

                                                        chosen_distribution.append(rnd_dist)
                                                        break

                                                    except Exception as e:
                                                        print(f"Exception in next_state: {e}. Restarting trip selection...")
                                                        continue

                                            elif trip_counter == 3:
                                                rnd_dist = chosen_distribution[2]
                                                chosen_distribution.append(rnd_dist)
                                                print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                                chosen_distribution[trip_counter] = rnd_dist
                                                print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                                print(f'Chosen_distribution: {chosen_distribution}')

                                                rnd_departure_time = sample_departure_time(min_after_previous=0.25, previous_end_time=chosen_values_after_trip[trip_counter - 1], distribution=trips_probability)

                                                chosen_values[trip_counter] = rnd_departure_time
                                                print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                    else:
                                        if trip_counter == 1:
                                            rnd_dist = chosen_distribution[0]
                                            chosen_distribution.append(rnd_dist)
                                            print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                            chosen_distribution[trip_counter] = rnd_dist
                                            print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                            print(f'Chosen_distribution: {chosen_distribution}')

                                            iteration = 2
                                            while not (rnd_departure_time > (chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                iteration += 1
                                            chosen_values[trip_counter] = rnd_departure_time
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                        elif trip_counter == 2:
                                            while True:
                                                # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                # print(f'Randomly sampled departure time: {rnd_departure_time}')
                                                rnd_departure_time = sample_departure_time(min_after_previous=0.25, previous_end_time=chosen_values_after_trip[trip_counter - 1], distribution=trips_probability)
                                                chosen_values[trip_counter] = rnd_departure_time
                                                print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                                index = int(value_to_index(rnd_departure_time))

                                                try:
                                                    probability, rnd_dist = next_state_constrained(index, 'Home', profiles_df, effective_purposes)
                                                    print(f'Probability: {probability}')
                                                    print(f'Next trip purpose: {rnd_dist}')

                                                    while rnd_dist == 'Home':
                                                        probability, rnd_dist = next_state_constrained(index, chosen_distribution[0], profiles_df, effective_purposes)
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                    if rnd_dist == 'None':
                                                        print("rnd_dist is None — restarting trip selection...")
                                                        rnd_departure_time = float(np.random.choice(x, p=trips_probability / sum(trips_probability)))
                                                        print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                        continue

                                                    chosen_distribution.append(rnd_dist)
                                                    if rnd_dist in ['Work']:
                                                        rnd_strategy = 'B'
                                                    break

                                                except Exception as e:
                                                    print(f"Exception in next_state: {e}. Restarting trip selection...")
                                                    continue

                                        elif trip_counter == 3:
                                            rnd_dist = chosen_distribution[2]
                                            chosen_distribution.append(rnd_dist)
                                            print(f'Nasumično odabrana distribucija: {rnd_dist}')
                                            chosen_distribution[trip_counter] = rnd_dist
                                            print(f'Chosen_distribution[{trip_counter}]: {chosen_distribution[trip_counter]}')
                                            print(f'Chosen_distribution: {chosen_distribution}')

                                            rnd_departure_time = sample_departure_time(min_after_previous=0.25, previous_end_time=chosen_values_after_trip[trip_counter - 1], distribution=trips_probability)

                                            chosen_values[trip_counter] = rnd_departure_time
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                print(f'Randomly sampled travel time (min): {travel_time}')
                                iteration = 2
                                if rnd_strategy == 'A':
                                    if trip_counter == 0:
                                        while not travel_time >= 5:  # Shortest trip duration
                                            travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                            print(f'Randomly sampled travel time in {iteration}. iteration (min): {travel_time}')
                                            iteration += 1
                                    elif trip_counter == 1:
                                        while not 5 <= travel_time <= 30:  # Shortest trip duration
                                            travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                            print(f'Randomly sampled travel time in {iteration}. iteration (min): {travel_time}')
                                            iteration += 1
                                    elif chosen_distribution.count(rnd_dist) == 2:
                                        travel_time = chosen_trips[chosen_distribution.index(rnd_dist)]
                                        print(f'Travel time for {rnd_dist} return trip: {travel_time}')
                                    elif chosen_distribution.count(rnd_dist) == 4:
                                        travel_time = chosen_trips[2]
                                        print(f'Travel time for {rnd_dist} return trip: {travel_time}')

                                elif rnd_strategy == 'B':
                                    if trip_counter in [0, 2]:
                                        while not travel_time >= 5:  # Shortest trip duration
                                            travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                            print(f'Randomly sampled travel time in {iteration}. iteration (min): {travel_time}')
                                            iteration += 1
                                    elif chosen_distribution.count(rnd_dist) == 2:
                                        travel_time = chosen_trips[chosen_distribution.index(rnd_dist)]
                                        print(f'Travel time for {rnd_dist} return trip: {travel_time}')
                                    elif chosen_distribution.count(rnd_dist) == 4:
                                        travel_time = chosen_trips[2]
                                        print(f'Travel time for {rnd_dist} return trip: {travel_time}')

                                else:
                                    if chosen_distribution.count(rnd_dist) == 2:
                                        travel_time = chosen_trips[chosen_distribution.index(rnd_dist)]
                                    elif chosen_distribution.count(rnd_dist) == 4:
                                        travel_time = chosen_trips[2]
                                    else:
                                        while not travel_time >= 5:  # Shortest trip duration
                                            travel_time = np.random.choice(x_axis_trips, p=trips_distribution / sum(trips_distribution))
                                            print(f'Randomly sampled travel time in {iteration}. iteration (min): {travel_time}')
                                            iteration += 1

                                print(f'Travel time: {travel_time}')

                                travel_time_intervals = np.ceil(travel_time / 15)
                                print(f'Travel time in intervals : {travel_time_intervals}')

                                arrival_time = rnd_departure_time + travel_time / 60
                                print(f'Arrival time (h): {arrival_time}')

                                if arrival_time > 24:
                                    print("Arrival time too late, retrying trip generation...")
                                    chosen_values[trip_counter] = 0
                                    chosen_values_after_trip[trip_counter] = 0
                                    chosen_trips[trip_counter] = 0
                                    trips_start_index[trip_counter] = 0
                                    trips_end_index[trip_counter] = 0

                                    if len(chosen_distribution) > trip_counter:
                                        chosen_distribution.pop()
                                    continue

                                break

                            chosen_values_after_trip[trip_counter] = arrival_time  # preimenuj u trip_end_time
                            print(f'Trips start time (h): {chosen_values}')
                            print(f'Trips end time (h): {chosen_values_after_trip}')
                            chosen_trips[trip_counter] = travel_time
                            print(f'Trips travel time (min): {chosen_trips}')

                            trips_start_index[trip_counter] = value_to_index(chosen_values[trip_counter])
                            trips_end_index[trip_counter] = value_to_index(chosen_values[trip_counter]) + travel_time_intervals

                            trip_counter += 1

                        trips_start_index_matrix_day[vehicle] = trips_start_index
                        print(trips_start_index_matrix_day[vehicle])
                        trips_end_index_matrix_day[vehicle] = trips_end_index
                        print(trips_end_index_matrix_day[vehicle])
                        trips_matrix_day[vehicle] = chosen_distribution[:]
                        print(trips_matrix_day[vehicle])
                        trips_duration_matrix_day[vehicle] = chosen_trips
                        print(trips_duration_matrix_day[vehicle])

                        # ===== VALIDATE CHAIN CONSISTENCY =====
                        total_chains += 1
                        is_valid, reason = validate_chain_consistency(
                            trip_chain=chosen_distribution[:],
                            profile=profile,
                            day_type=days[day]
                        )
                        print(f"Validating chain: {chosen_distribution} | Profile: {profile.name} | Valid: {is_valid}")

                        if not is_valid:
                            rejected_chains += 1
                            print(f"[CHAIN REJECTED] Vehicle {vehicle+1}, Day {day+1}: {reason}. Retrying (attempt {retry_outer}/50)...")
                            continue  # restarts the outer `while not success` loop, regenerating all trips

                        success = True
                        # ======================================

                    except Exception as e:
                        print(f"Greška kod vozila {vehicle + 1}: {e}. Pokušavam ponovo...")
                        continue  # ide iz početka za isto vozilo

                if not success:
                    print(f"[VEHICLE FALLBACK] Vehicle {vehicle+1}, Day {day+1}: max retries (50) reached, accepting last generated chain.")

        start_idx = day * number_of_vehicles
        end_idx = start_idx + number_of_vehicles

        trips_start_index_matrix_week[start_idx:end_idx, :] = trips_start_index_matrix_day
        print(trips_start_index_matrix_week)
        trips_end_index_matrix_week[start_idx:end_idx, :] = trips_end_index_matrix_day
        print(trips_end_index_matrix_week)
        trips_duration_matrix_week[start_idx:end_idx, :] = trips_duration_matrix_day
        print(trips_duration_matrix_week)

        for i in range(number_of_vehicles):
            trips_matrix_week[start_idx + i] = trips_matrix_day[i]

        print(trips_matrix_week)

    print("\n=== CHAIN VALIDATION SUMMARY ===")
    print(f"Total chains generated : {total_chains}")
    print(f"Chains rejected        : {rejected_chains}")
    if total_chains > 0:
        print(f"Rejection rate         : {rejected_chains/total_chains*100:.1f}%")

    return trips_matrix_week, trips_start_index_matrix_week, trips_duration_matrix_week, trips_end_index_matrix_week, vehicle_profiles #vehicle_soc


# ------------------------------ Call the function and get trip parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input()) # Number of vehicles included in the simulation

print('Insert number of trips (2/4):')
number_of_trips = int(input())

print('Insert number of days (1/7):')
number_of_days = int(input()) # Number of days included in the simulation

trip_parameters = get_trip_parameters(number_of_vehicles, number_of_trips, number_of_days)
trips_matrix_week, trips_start_index_matrix_week, trips_duration_matrix_week, trips_end_index_matrix_week, vehicle_profiles = trip_parameters
#vehicle_soc 


print(f'Chosen trip reasons:\n' + "\n".join(map(str, trips_matrix_week)))
print(f'Trip start indices: \n{trips_start_index_matrix_week}')
print(f'Trip durations: \n{trips_duration_matrix_week}')
print(f'Trip end indices: \n{trips_end_index_matrix_week}')


# ------------------------------ Preparing results for export ------------------------------ #


day_type = []
vehicle_numbers = []
trip_numbers = []
trip_types = []
start_indices = []
trip_durations = []
end_indices = []
profile_output = []  # NEW
#soc_output = []
days = days_week[:number_of_days]

day = 0
for day in range(len(days)):
    i = 0
    for i in range(number_of_vehicles * number_of_trips):
        day_type.append(days[day].value)
    vehicle = 0
    trip = 0
    for vehicle in range(number_of_vehicles):
        for trip in range(number_of_trips):
            vehicle_numbers.append(vehicle + 1)
            trip_numbers.append(trip + 1)
            profile_output.append(vehicle_profiles[vehicle].name)  # NEW
            #soc_output.append(vehicle_soc[vehicle])
            trip_types.append(trip_parameters[0][vehicle + number_of_vehicles * day][trip])
            start_indices.append(trip_parameters[1][vehicle + number_of_vehicles * day][trip])
            trip_durations.append(trip_parameters[2][vehicle + number_of_vehicles * day][trip])
            end_indices.append(trip_parameters[3][vehicle + number_of_vehicles * day][trip])

generated_trip_parameters = {
    'Day Type': day_type,
    'Vehicle ID': vehicle_numbers,
    'Trip ID': trip_numbers,
    'Profile': profile_output,  # NEW
    #'Initial_SoC': soc_output,
    'Trip type': trip_types,
    'Start': start_indices,
    'Duration': trip_durations,
    'End': end_indices
}

generated_trip_parameters = pd.DataFrame(generated_trip_parameters)
#print(generated_trip_parameters[["Vehicle ID", "Initial_SoC"]].head())
file_name = f"01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"

generated_trip_parameters.to_excel(file_name, index=False)

print(generated_trip_parameters)

# ===== NEW: PROFILE SUMMARY STATISTICS =====
print("\n" + "="*50)
print("PROFILE DISTRIBUTION SUMMARY")
print("="*50)
profile_counts = {}
for vehicle_idx in range(number_of_vehicles):
    profile_name = vehicle_profiles[vehicle_idx].name
    profile_counts[profile_name] = profile_counts.get(profile_name, 0) + 1

for profile_name, count in profile_counts.items():
    pct = 100 * count / number_of_vehicles
    print(f"{profile_name:15} : {count:3} vehicles ({pct:5.1f}%)")

# Validate constraints
work_vehicles = len([p for p in vehicle_profiles if p.work_required])
non_work_vehicles = len([p for p in vehicle_profiles if not p.work_required])
print(f"\nWork trip required  : {work_vehicles} vehicles")
print(f"Work trip optional  : {non_work_vehicles} vehicles")
print("="*50 + "\n")
# ==========================================


fig = go.Figure()
fig.add_trace(go.Histogram(x=generated_trip_parameters['Start']))
fig.show()
