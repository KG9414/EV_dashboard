import pandas as pd
import numpy as np
import os


# ------------------------------ Input parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input()) # Number of vehicles included in the simulation

print('Insert number of trips (2/4):')
number_of_trips = int(input()) # Number of trips per vehicle and per day (2 or 4 trips)

print('Insert number of days (1/7):')
number_of_days = int(input()) # Number of days included in the simulation

trip_parameters_file_path = f"01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"
trip_parameters_df = pd.read_excel(trip_parameters_file_path)

trips_file_path = f"02_Trips/02_Trips_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"
trips_df = pd.read_excel(trips_file_path)

df = trip_parameters_df.copy()
#df['Start TP'] = trips_df.apply(lambda row: row['Start substation'] if row['Start substation distance'] < 2.4 else 'Out of area', axis=1)
#df['End TP'] = trips_df.apply(lambda row: row['End substation'] if row['End substation distance'] < 2.4 else 'Out of area', axis=1)
df['Actual duration'] = trips_df['Duration']
df['Actual distance'] = trips_df['Distance']

df['Start_lat'] = trips_df['Start location lat']
df['Start_lon'] = trips_df['Start location lon']

df['End_lat'] = trips_df['End location lat']
df['End_lon'] = trips_df['End location lon']

#topology_file_path = r'C:\Users\dudag\OneDrive - Univerza v Ljubljani\Desktop\Projects\RTP Velenje Network\Secondary_Substations.xlsx'
#substations_df = pd.read_excel(topology_file_path)


# ------------------------------ Initialize empty variables ------------------------------ #

vehicle_location = np.ones((number_of_vehicles, 96 * number_of_days))
vehicle_distance = np.zeros((number_of_vehicles, 96 * number_of_days))
#vehicle_substation = np.zeros((number_of_vehicles, 96 * number_of_days), dtype=object)
# start_date = '2024-10-23 00:00'
# end_date = '2024-10-29 23:45'
# time = pd.date_range(start=start_date, end=end_date, freq='15min')


# ------------------------------ Define distances, durations and substations for each 15-min interval ------------------------------ #


for vehicle in range(number_of_vehicles):
    index_vehicle = (df['Vehicle ID'] == vehicle + 1).tolist()
    print(df['Trip type'].iloc[index_vehicle])
    temp_data = df.iloc[index_vehicle].reset_index(drop=True)
    print(temp_data)

    trip = 0
    for day in range(number_of_days):
        for trip in range(number_of_trips):

            trip_start = temp_data['Start'][trip + number_of_trips*day] + 96*day
            print(f'Departure time: {trip_start}')

            trip_end = temp_data['End'][trip + number_of_trips*day] + 96*day
            print(f'Arrival time: {trip_end}')

            trip_duration = temp_data['Actual duration'][trip + number_of_trips*day]
            print(f'Trip duration: {trip_duration}')

            trip_distance = temp_data['Actual distance'][trip + number_of_trips*day]
            print(f'Travelled distance: {trip_distance}')

            trip_distance = trip_distance / (trip_end - trip_start)
            print(f'Distance travelled in 15 minutes: {trip_distance}')

            # ------------------------------ Define distance for each 15-min interval ------------------------------ #

            print(vehicle_distance[vehicle])
            vehicle_distance[vehicle, int(trip_start):int(trip_end)] = trip_distance
            print('--------------------------------------------------')
            print(vehicle_distance[vehicle])
            print('--------------------------------------------------')

            # ------------------------------ Define location for each 15-min interval ------------------------------ #

            print(vehicle_location[vehicle])
            vehicle_location[vehicle, int(trip_start):int(trip_end)] = 0
            print('--------------------------------------------------')
            print(vehicle_location[vehicle])

            print(temp_data['Trip type'][trip + number_of_trips*day])
            # if temp_data['Trip type'][trip + number_of_trips*day] == 'Work' or temp_data['Trip type'][trip + number_of_trips*day] == 'Business':
            if temp_data['Trip type'][trip + number_of_trips * day] == 'Work':
                vehicle_location[vehicle, int(trip_end):] = 2
            else:
                vehicle_location[vehicle, int(trip_end):] = 3
            print(vehicle_location[vehicle])

            if number_of_trips == 4:
                if trip == 1:
                    if temp_data['Trip type'][day*number_of_trips + 0] == temp_data['Trip type'][day*number_of_trips + 1]:
                        vehicle_location[vehicle, int(trip_end):] = 1
                elif trip == 2:
                    if temp_data['Trip type'][day*number_of_trips + 1] == temp_data['Trip type'][day*number_of_trips + 2]:
                        # if temp_data['Trip type'][day*number_of_trips + 0] == 'Work' or temp_data['Trip type'][day*number_of_trips + 0] == 'Business':
                        if temp_data['Trip type'][day * number_of_trips + 0] == 'Work':
                            vehicle_location[vehicle, int(trip_end):] = 2
                        else:
                            vehicle_location[vehicle, int(trip_end):] = 3
            print(vehicle_location[vehicle])

            if trip == number_of_trips - 1:
                vehicle_location[vehicle, int(trip_end):] = 1
            print(vehicle_location[vehicle])

            # ------------------------------ Define substations for each 15-min interval ------------------------------ #

            #if trip == 0:
             #   vehicle_substation[vehicle, 96*day:trip_start] = temp_data['Start TP'][trip]

            #vehicle_substation[vehicle, trip_end:] = temp_data['End TP'][day * number_of_trips + trip]
            #vehicle_substation[vehicle, trip_start:trip_end] = 0
            #print(vehicle_substation[vehicle, 96*day:96*day+96])


# ------------------------------ Substation occupancy ------------------------------ #

#substation_occupancy = np.zeros((96 * number_of_days, len(substations_df['naziv'])))
#vehicle_substation = pd.DataFrame(vehicle_substation).T
#vehicle_ID = df['Vehicle ID'].unique()
#vehicle_substation.columns = [f'EV {id}' for id in vehicle_ID]

#for tp in substations_df['naziv']:
#    index = substations_df[substations_df['naziv'] == tp].index[0]
#    sub = (vehicle_substation == tp).astype(int)
#    occupancy = sub.sum(axis=1)
#    substation_occupancy[:, index] = occupancy

# ------------------------------ Check if start and end substation are the same ------------------------------ #

#check = vehicle_substation.iloc[0,:] == vehicle_substation.iloc[-1,:]
#print(check)

#substation_occupancy_df = pd.DataFrame(substation_occupancy)
#substation_occupancy_df.columns = substations_df['naziv']
#substation_occupancy_df = substation_occupancy_df.loc[:, (substation_occupancy_df != 0).any()]


# ------------------------------ PORABA ------------------------------ #

df["Energy_kWh"] = trips_df["Consumption_kWh"]

# ------------------------------ Export results ------------------------------ #

# vehicle_substation.to_excel(f'03_Vehicle_substation_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx', index=False)
# vehicle_distance = pd.DataFrame(np.transpose(vehicle_distance))
# vehicle_distance.to_excel(f'03_Vehicle_distance_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx', index=False)
# vehicle_location = pd.DataFrame(np.transpose(vehicle_location))
# vehicle_location.to_excel(f'03_Vehicle_location_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx', index=False)
# substation_occupancy_df.to_excel(f'03_Substation_occupancy_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx', index=False)

#folder_path = r"C:\Users\dudag\OneDrive - Univerza v Ljubljani\Desktop\Magistrska\03_Gradnja modela\Simulacijski model\03_Vehicle_parameters"
folder_path = "03_Vehicle_parameters"
os.makedirs(folder_path, exist_ok=True)

#file_vehicle_substation = os.path.join(folder_path, f'03_Vehicle_substation_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx')
#vehicle_substation.to_excel(file_vehicle_substation, index=False)

vehicle_distance = pd.DataFrame(np.transpose(vehicle_distance))
file_vehicle_distance = os.path.join(folder_path, f'03_Vehicle_distance_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx')
vehicle_distance.to_excel(file_vehicle_distance, index=False)

vehicle_location = pd.DataFrame(np.transpose(vehicle_location))
file_vehicle_location = os.path.join(folder_path, f'03_Vehicle_location_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx')
vehicle_location.to_excel(file_vehicle_location, index=False)

#file_substation_occupancy = os.path.join(folder_path, f'03_Substation_occupancy_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx')
#substation_occupancy_df.to_excel(file_substation_occupancy, index=False)

file_vehicle_trip_parameters = os.path.join(folder_path, f'03_Vehicle_trip_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx')
df.to_excel(file_vehicle_trip_parameters, index=False)