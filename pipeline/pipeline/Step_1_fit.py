import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
from Functions_step_1 import map_location, next_state, string_to_index, sample_departure_time, value_to_index



def sample_work_start():

    # prihod na delo med 7:00 in 9:00
    return np.random.uniform(7.0, 9.0)
    
def sample_work_duration():

    # delovnik dolg 7-9ur
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

hourly_prob = df_prob.iloc[:,1].values

trips_probability = np.repeat(hourly_prob, 4)

trips_probability = trips_probability / trips_probability.sum()

print("len trips_probability:", len(trips_probability))
print(len(trips_probability))
print(sum(trips_probability))

# Prevent trips before 6am for Slovenia
trips_probability[:24] = 0  # 6 hours * 4 intervals/hour = 24
trips_probability = trips_probability / trips_probability.sum()


# ---------------------------------------- # Import Gauss fitting parameters # ---------------------------------------- #

trip_duration_params = np.array([5.0, 18.90741191528791])
x_axis_trips = np.linspace(0, 60, 1000)
trips_distribution = (1 / trip_duration_params[1]) * np.exp(-(x_axis_trips - trip_duration_params[0]) / trip_duration_params[1])


# ---------------------------------------- # Preparation # ---------------------------------------- #

#trips_probability = df_prob
days_week = ['Workday', 'Workday', 'Workday', 'Workday', 'Workday', 'Weekend', 'Weekend']
states = ['Home', 'Work', 'Business', 'Education', 'Shopping', 'Transport', 'Leisure', 'Personal']

# x = np.linspace(0, 23.75, 96)
# selected = np.random.choice(x, p=trips_probability/sum(trips_probability), size=4000)
# fig = go.Figure()
# fig.add_trace(go.Histogram(x=selected))
# fig.show()
# fig = go.Figure()
# fig.add_trace(go.Histogram(x=selected, nbinsx=24))
# fig.show()

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


def next_state(interval, state):
    current_states = profiles_df.iloc[:, interval]
    previous_states = profiles_df.iloc[:, interval - 1]

    transition_matrix = pd.DataFrame(0, index=states, columns=states)

    for prev_state, curr_state in zip(previous_states, current_states):
        if prev_state in states and curr_state in states:
            if prev_state == curr_state:
                transition_matrix.loc[prev_state, curr_state] = 0
            else:
                transition_matrix.loc[prev_state, curr_state] += 1

    prob_matrix = transition_matrix.div(transition_matrix.sum(axis=1), axis=0).fillna(0)
    probability = prob_matrix.loc[state]
    if sum(probability) > 0.999:
        next_trip = np.random.choice(prob_matrix.columns, p=probability)
    else:
        next_trip = 'None'

    return probability, next_trip


# ---------------------------------------- # Main function for generating trip parameters # ---------------------------------------- #

def get_trip_parameters(number_of_vehicles, number_of_trips, number_of_days):
    days = days_week[:number_of_days]
    trips_start_index_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))
    trips_end_index_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))
    trips_matrix_week = [[] for _ in range(number_of_vehicles * len(days))]
    trips_duration_matrix_week = np.zeros((number_of_vehicles * len(days), number_of_trips))

    for day in range(len(days)):
        if days[day] == 'Workday':
            trips_start_index_matrix_day = np.zeros((number_of_vehicles, number_of_trips))
            trips_end_index_matrix_day = np.zeros((number_of_vehicles, number_of_trips))
            trips_matrix_day = [[] for _ in range(number_of_vehicles)]
            trips_duration_matrix_day = np.zeros((number_of_vehicles, number_of_trips))

            for vehicle in range(number_of_vehicles):
                print(f'Vehicle ID {vehicle+1}')

                success = False
                while not success:
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
                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                    print(f'Randomly sampled departure time: {rnd_departure_time}')
                                    # chosen_values[trip_counter] = rnd_departure_time
                                    # print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")

                                    if trip_counter == 0:
                                        while True:
                                            rnd_departure_time = sample_work_start()

                                            chosen_values[trip_counter] = rnd_departure_time

                                            index = int(value_to_index(rnd_departure_time))

                                            try:
                                                probability, rnd_dist = next_state(index, 'Home')

                                                if rnd_dist == 'None':
                                                    continue

                                                chosen_distribution.append(rnd_dist)

                                            except:
                                                continue

                                            


                                    if trip_counter == 1:
                                        if rnd_dist in ['Work']:
                                            rnd_dist = chosen_distribution[0]
                                            chosen_distribution.append(rnd_dist)

                                            chosen_distribution[trip_counter] = rnd_dist



                                            iteration = 2
                                            while not (chosen_values_after_trip[trip_counter - 1] + 7 < rnd_departure_time <
                                                       chosen_values_after_trip[trip_counter - 1] + 9 and rnd_departure_time >
                                                       chosen_values_after_trip[trip_counter - 1]):
                                                rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))

                                                iteration += 1
                                            chosen_values[trip_counter] = rnd_departure_time

                                        else:
                                            rnd_dist = chosen_distribution[0]
                                            chosen_distribution.append(rnd_dist)

                                            chosen_distribution[trip_counter] = rnd_dist

                                            iteration = 2
                                            while not (rnd_departure_time > (
                                                    chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))

                                                iteration += 1
                                            chosen_values[trip_counter] = rnd_departure_time

                                if number_of_trips == 4:
                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))



                                    if trip_counter == 0:

                                        while True:


                                            rnd_departure_time = sample_work_start()

                                            chosen_values[trip_counter] = rnd_departure_time  # preimenuj u trip_start_time ako želiš
                                            print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                            index = int(value_to_index(rnd_departure_time))

                                            try:
                                                probability, rnd_dist = next_state(index, 'Home')
                                                print(f'Probability: {probability}')
                                                print(f'Next trip purpose: {rnd_dist}')

                                                while rnd_dist == 'Home':
                                                    probability, rnd_dist = next_state(index, chosen_distribution[0])
                                                    print(f'Probability: {probability}')
                                                    print(f'Next trip purpose: {rnd_dist}')

                                                if rnd_dist == 'None':
                                                    print("rnd_dist is None — restarting selection...")
                                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                    print(f'Randomly sampled departure time (h): {rnd_departure_time}')
                                                    continue

                                                chosen_distribution.append(rnd_dist)
                                                break

                                            except Exception as e:
                                                print(f"Exception in next_state: {e}. Restarting...")
                                                continue

                                        if 'Work' in chosen_distribution:
                                            # rnd_strategy = np.random.choice(strategies)
                                            rnd_strategy = np.random.choice(strategies, p=[0.95, 0.05])

                                            print(f'Work is first trip purpose with strategy: {rnd_strategy}')

                                    if 'Work' in chosen_distribution:
                                        if rnd_strategy == 'A':
                                            if trip_counter == 1:
                                                while True:
                                                    # rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                    # print(f'Randomly sampled departure time: {rnd_departure_time}')
                                                    iteration = 2
                                                    while not (10 < rnd_departure_time < 16.5 and rnd_departure_time > (chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                        rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
                                                        print(f'Randomly sampled second trip departure time in {iteration}. iteration (min): {rnd_departure_time}')
                                                        iteration += 1
                                                    chosen_values[trip_counter] = rnd_departure_time
                                                    print(f"Chosen_values[{trip_counter}]: {rnd_departure_time}")
                                                    index = int(value_to_index(rnd_departure_time))

                                                    try:
                                                        probability, rnd_dist = next_state(index, chosen_distribution[0])
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                        while rnd_dist == 'Home':
                                                            probability, rnd_dist = next_state(index, chosen_distribution[0])
                                                            print(f'Probability: {probability}')
                                                            print(f'Next trip purpose: {rnd_dist}')

                                                        if rnd_dist == 'None':
                                                            print("rnd_dist is None — restarting block...")
                                                            rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                          chosen_values_after_trip[trip_counter - 1] + 1.75:
                                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                while not (rnd_departure_time > (chosen_values_after_trip[trip_counter - 1] + 0.25)):
                                                    rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                        probability, rnd_dist = next_state(index, 'Home', profiles_df)
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                        while rnd_dist == 'Home':
                                                            probability, rnd_dist = next_state(index, chosen_distribution[0], profiles_df)
                                                            print(f'Probability: {probability}')
                                                            print(f'Next trip purpose: {rnd_dist}')

                                                        if rnd_dist == 'None':
                                                            print("rnd_dist is None — restarting trip selection...")
                                                            rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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
                                                    probability, rnd_dist = next_state(index, 'Home')
                                                    print(f'Probability: {probability}')
                                                    print(f'Next trip purpose: {rnd_dist}')

                                                    while rnd_dist == 'Home':
                                                        probability, rnd_dist = next_state(index, chosen_distribution[0])
                                                        print(f'Probability: {probability}')
                                                        print(f'Next trip purpose: {rnd_dist}')

                                                    if rnd_dist == 'None':
                                                        print("rnd_dist is None — restarting trip selection...")
                                                        rnd_departure_time = np.random.choice(x, p=trips_probability / sum(trips_probability))
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

                        success = True

                    except Exception as e:
                        #print(f"Greška kod vozila {vehicle + 1}: {e}. Pokušavam ponovo...")
                        continue  # ide iz početka za isto vozilo

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

    return trips_matrix_week, trips_start_index_matrix_week, trips_duration_matrix_week, trips_end_index_matrix_week


# ------------------------------ Call the function and get trip parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input()) # Number of vehicles included in the simulation

print('Insert number of trips (2/4):')
number_of_trips = int(input()) # Number of trips per vehicle and per day (2 or 4 trips)

print('Insert number of days (1/7):')
number_of_days = int(input()) # Number of days included in the simulation

trip_parameters = get_trip_parameters(number_of_vehicles, number_of_trips, number_of_days)

print(f'Chosen trip reasons:\n' + "\n".join(map(str, trip_parameters[0])))
print(f'Trip start indices: \n{trip_parameters[1]}')
print(f'Trip durations: \n{trip_parameters[2]}')
print(f'Trip end indices: \n{trip_parameters[3]}')


# ------------------------------ Preparing results for export ------------------------------ #


day_type = []
vehicle_numbers = []
trip_numbers = []
trip_types = []
start_indices = []
trip_durations = []
end_indices = []
days = days_week[:number_of_days]

day = 0
for day in range(len(days)):
    i = 0
    for i in range(number_of_vehicles * number_of_trips):
        day_type.append(days[day])
    vehicle = 0
    trip = 0
    for vehicle in range(number_of_vehicles):
        for trip in range(number_of_trips):
            vehicle_numbers.append(vehicle + 1)
            trip_numbers.append(trip + 1)
            trip_types.append(trip_parameters[0][vehicle + number_of_vehicles * day][trip])
            start_indices.append(trip_parameters[1][vehicle + number_of_vehicles * day][trip])
            trip_durations.append(trip_parameters[2][vehicle + number_of_vehicles * day][trip])
            end_indices.append(trip_parameters[3][vehicle + number_of_vehicles * day][trip])

generated_trip_parameters = {
    'Day Type': day_type,
    'Vehicle ID': vehicle_numbers,
    'Trip ID': trip_numbers,
    'Trip type': trip_types,
    'Start': start_indices,
    'Duration': trip_durations,
    'End': end_indices
}

generated_trip_parameters = pd.DataFrame(generated_trip_parameters)
file_name = f"01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"

generated_trip_parameters.to_excel(file_name, index=False)

print(generated_trip_parameters)


fig = go.Figure()
fig.add_trace(go.Histogram(x=generated_trip_parameters['Start']))
fig.show()
