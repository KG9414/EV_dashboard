import os
print(os.getcwd())

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from Functions_step_0 import round_hhmm_to_1h, float_to_1h, round_hhmm_to_15min

''' # --------------------- # Read NHTS data # --------------------- # '''

df_nhts = pd.read_csv('00_NHTS_data.csv', delimiter=';')


''' # --------------------- # Filter trips that are covered by car # --------------------- # '''

vehicle_filter = df_nhts['TRPTRANS'].isin([3])
df_vehicle_filter = df_nhts[vehicle_filter].reset_index(drop=True)


''' # --------------------- # Find new day and new daily profile # --------------------- # '''

day_trip = []
for trip in range(len(df_vehicle_filter['TDTRPNUM'])):
    if trip == 0:
        new_day = 1
    else:
        if df_vehicle_filter['TDTRPNUM'][trip] > df_vehicle_filter['TDTRPNUM'][trip-1] and df_vehicle_filter['STRTTIME'][trip] > df_vehicle_filter['STRTTIME'][trip-1]:
            new_day = 0
        else:
            new_day = 1
    day_trip.append(new_day)

df_vehicle_filter['NEWDAY'] = pd.DataFrame(day_trip)


''' # --------------------- # Indices of new day beginnings # --------------------- # '''

new_day_index = df_vehicle_filter[df_vehicle_filter['NEWDAY'] == 1].index.to_list()


''' # --------------------- # Reshape data # --------------------- # '''

house_id = []
start_time = []
start_time_15_min = []
end_time = []
end_time_15_min = []
start_location = []
end_location = []
distances = []
profile = []

for i in range(len(new_day_index) - 1):
    day_start = new_day_index[i]
    day_end = new_day_index[i + 1]

    temp = df_vehicle_filter.iloc[day_start:day_end]

    house_id.append(temp['HOUSEID'].values)
    start_time_15_min.append(round_hhmm_to_15min(temp['STRTTIME'].values, mode="floor"))
    end_time_15_min.append(round_hhmm_to_15min(temp['ENDTIME'].values, mode="ceil"))
    start_time.append(round_hhmm_to_1h(temp['STRTTIME'].values))
    end_time.append(round_hhmm_to_1h(temp['ENDTIME'].values))
    start_location.append(temp['WHYFROM'].values)
    end_location.append(temp['WHYTO'].values)
    distances.append(temp['TRPMILES'].values * 1.60934)
    profile.append(f'Profile {i + 1}')

trips = [f'Trip {i + 1}' for i in range(max(len(day) for day in start_time))]

df_house_id = pd.DataFrame(house_id, columns=trips)
df_start_time = pd.DataFrame(start_time, columns=trips)
df_start_time_15_min = pd.DataFrame(start_time_15_min, columns=trips)
df_end_time = pd.DataFrame(end_time, columns=trips)
df_end_time_15_min = pd.DataFrame(end_time_15_min, columns=trips)
df_start_location = pd.DataFrame(start_location, columns=trips)
df_end_location = pd.DataFrame(end_location, columns=trips)
df_distance = pd.DataFrame(distances, columns=trips)

distance_max = np.max(df_distance, axis=1)
distance_filter = distance_max[distance_max <= 109].index.tolist()

df_house_id = df_house_id.loc[distance_filter].reset_index(drop=True)
df_start_time = df_start_time.loc[distance_filter].reset_index(drop=True)
df_start_time_15_min = df_start_time_15_min.loc[distance_filter].reset_index(drop=True)
df_end_time = df_end_time.loc[distance_filter].reset_index(drop=True)
df_end_time_15_min = df_end_time_15_min.loc[distance_filter].reset_index(drop=True)
df_start_location = df_start_location.loc[distance_filter].reset_index(drop=True)
df_end_location = df_end_location.loc[distance_filter].reset_index(drop=True)
df_distance = df_distance.loc[distance_filter].reset_index(drop=True)

df_house_id = df_house_id.iloc[:, :4]
df_start_time = df_start_time.iloc[:, :4]
df_start_time_15_min = df_start_time_15_min.iloc[:, :4]
df_end_time = df_end_time.iloc[:, :4]
df_end_time_15_min = df_end_time_15_min.iloc[:, :4]
df_start_location = df_start_location.iloc[:, :4]
df_end_location = df_end_location.iloc[:, :4]
df_distance = df_distance.iloc[:, :4]


''' # --------------------- # SiStat data # --------------------- # '''

trips_counts = np.array([
    6877, 4028, 2857, 7978, 21702, 120939, 224975, 275057, 250145, 223157,
    241526, 202795, 200514, 210370, 294699, 341699, 299577, 257362, 235680,
    167180, 111677, 60552, 44604, 14506
])

# trips_counts = np.array([
#     2388, 0, 0, 7181, 19720, 100288, 162558, 114814, 37857, 15480,
#     15412, 23078, 30965, 53878, 111903, 132338, 77626, 34472, 27349,
#     14950, 19906, 16248, 23854, 5325
# ])

''' # --------------------- # Create new data frame # --------------------- # '''

df = pd.DataFrame({
    'All trips': trips_counts
})

trip_departure = np.linspace(0.5, 23.5, num=24)


''' # --------------------- # Repeat time values trips_counts times # --------------------- # '''

all_trips_extended = []
for i in range(len(trip_departure)):
    all_trips_extended.extend(np.repeat(trip_departure[i], trips_counts[i]))

df_extended = pd.DataFrame({
    'All trips': all_trips_extended
})

fig = go.Figure()
fig.add_trace(go.Histogram(x=df_extended['All trips'], histnorm='probability', marker_color='#007fad'))
fig.update_layout(
    title_text='Dnevno število poti po uri začetka poti',
    xaxis_title_text='Ura začetka poti',
    yaxis_title_text='Število',
    bargap=0.2
)
fig.show()


''' # --------------------- # PDF # --------------------- # '''

# number_of_components = 6
# gmm = GaussianMixture(n_components=number_of_components)
# gmm.fit(df_extended['All trips'].values.reshape(-1, 1))
#
# means = gmm.means_.flatten()
# standard_deviations = np.sqrt(gmm.covariances_).flatten()
# weights = gmm.weights_
#
# pdf_components = []
# fig = go.Figure()
# x = np.linspace(0, 23.75, 96)
# for mean, std, weight in zip(means, standard_deviations, weights):
#     pdf = weight * norm.pdf(x, mean, std)
#     pdf_components.append(pdf)
#     index = np.where(means == mean)[0][0]+1
#     fig.add_trace(go.Scatter(x=x, y=pdf, name=f'Component {index}'))
# fig.add_trace(go.Scatter(x=x, y=sum(pdf_components), name='Sum of components'))
#
# fig.add_trace(go.Histogram(x=df_extended['All trips'], histnorm='probability', name='Original data', marker_color='#007fad'))
# fig.update_layout(
#     title_text='Dnevno število poti po uri začetka poti',
#     xaxis_title_text='Ura začetka poti',
#     yaxis_title_text='Število',
#     bargap=0.2
# )
# fig.show()
#
# parameters = np.vstack((means, standard_deviations, weights))

# gauss_trips = normal_distribution(parameters, number_of_components)
# gauss_trips_pdf = gauss_trips.values / sum(gauss_trips.values)

gauss_trips_pdf = trips_counts/sum(trips_counts)
gauss_trips_pdf_df = pd.DataFrame(gauss_trips_pdf)


''' # --------------------- # Random sample trip departure time based on probability # --------------------- # '''

p_value = 0
while_stop = 0
statistic = 1

while p_value < 0.95 or statistic > 0.01:
    while_stop = while_stop + 1
    generated_data = np.random.choice(trip_departure, 10000, p=gauss_trips_pdf)
    print(generated_data)

    statistic, p_value = stats.ks_2samp(df_extended['All trips'], generated_data)
    print(p_value, statistic)

    if while_stop == 100:
        print('Exceeded 100 iterations')
        break

generated_data_df = pd.DataFrame(generated_data)


fig = go.Figure()
fig.add_trace(go.Histogram(x=df_extended['All trips'], histnorm='probability', marker_color='#007fad', name='Original'))
fig.add_trace(go.Histogram(x=generated_data, histnorm='probability', marker_color='darkred', name='Generated'))
fig.add_trace(go.Scatter(x=trip_departure, y=gauss_trips_pdf, name='Sum of components'))
fig.update_layout(
    title_text='Dnevno število poti po uri začetka poti',
    xaxis_title_text='Ura začetka poti',
    yaxis_title_text='Število',
    bargap=0.2
)
fig.show()


''' # --------------------- # CDF plot # --------------------- # '''

original_sorted = np.sort(df_extended['All trips'])
generated_sorted = np.sort(generated_data)

original_cdf = np.linspace(0, 1, len(original_sorted))
generated_cdf = np.linspace(0, 1, len(generated_sorted))

fig = go.Figure()
fig.add_trace(go.Scatter(x=original_sorted, y=original_cdf, mode='lines', marker_color='#007fad', name='Original'))
fig.add_trace(go.Scatter(x=generated_sorted, y=generated_cdf, mode='lines', marker_color='darkred', name='Generated'))
fig.update_layout(
    title_text='Dnevno število poti po uri začetka poti',
    xaxis_title_text='Ura začetka poti',
    yaxis_title_text='Število'
)
fig.show()


trip_beginnings_list = float_to_1h(generated_data)
trip_beginnings_df = pd.DataFrame({
    'Trip beginnings': trip_beginnings_list
})
print(trip_beginnings_df)


''' # --------------------- # Analysis # --------------------- # '''

trip_beginnings_list_replica = trip_beginnings_list.copy()
selected_profiles_index = []
# for dist in trip_distances_list_replica:
while trip_beginnings_list_replica:
    start = trip_beginnings_list_replica[0]
    print(f'Departure time: {start}')
    print(f'List size: {len(trip_beginnings_list_replica)}')
    index_table = []
    for column in df_start_time.columns:
        index = df_start_time[column].str.contains(start).apply(lambda row: 1 if row == True else 0)
        index_table.append(index)
        index_table_df = pd.DataFrame(np.transpose(index_table))

    selected_rows = sum(index_table)
    selected_rows_df = pd.DataFrame(selected_rows)
    selected_rows_index = selected_rows[selected_rows == 1].index.to_list()

    for index in selected_rows_index:
        profile = df_start_time.iloc[index, :].values
        profile = profile[~(pd.isna(profile))]
        # print(f'Profile: {profile}')

        matches = profile[np.isin(profile, trip_beginnings_list_replica)]
        # print(f'Match in list: {matches}')

        if np.array_equal(profile, matches):
            # print(f'Index of the selected profile: {index}')
            selected_profiles_index.append(index)

            for departure in profile:
                # print(f'Departure time: {departure}')
                if departure in trip_beginnings_list_replica:
                    trip_beginnings_list_replica.remove(departure)
                    if len(trip_beginnings_list_replica) > 0:
                        print(f'List size: {len(trip_beginnings_list_replica)}')
                        print(trip_beginnings_list_replica[0])

        if trip_beginnings_list_replica.count(start) == 0:
            break

    if len(trip_beginnings_list_replica) == 0:
        break

selected_profiles_index_df = pd.DataFrame(selected_profiles_index)

selected_daily_profiles_df = df_start_time.iloc[selected_profiles_index]
selected_profiles_distance = df_distance.iloc[selected_profiles_index]
selected_profiles_houseid = df_house_id.iloc[selected_profiles_index]

selected_profiles_series = pd.Series(selected_daily_profiles_df.values.ravel())
selected_profiles_series = selected_profiles_series.dropna()
selected_profiles_series = selected_profiles_series[selected_profiles_series != 'None']

sampled_quarterly = pd.to_datetime(selected_profiles_series, format='%H:%M', errors='coerce').dropna().apply(
    lambda t: t.hour + t.minute / 60
)
sampled_hourly = pd.to_datetime(selected_profiles_series, format='%H:%M', errors='coerce').dropna().dt.hour


''' # --------------------- # Analysis # --------------------- # '''

fig = go.Figure()
fig.add_trace(go.Histogram(x=df_extended['All trips'], histnorm='probability', marker_color='#007fad', name='Original'))
fig.add_trace(go.Histogram(x=generated_data, histnorm='probability', marker_color='darkred', name='Generated'))
fig.add_trace(go.Histogram(x=sampled_hourly, histnorm='probability', marker_color='darkgreen', name='Sampled (1h)'))
fig.add_trace(go.Histogram(x=sampled_quarterly, histnorm='probability', marker_color='orange', name='Sampled (15 min)'))

fig.update_layout(
    title_text='Dnevno število poti po uri začetka poti',
    xaxis_title_text='Ura začetka poti',
    yaxis_title_text='Število',
    bargap=0.2

)
fig.show()


''' # --------------------- # Analysis # --------------------- # '''

trips_per_day = selected_daily_profiles_df.notna().sum(axis=1).mean()
print(f'Average trips per day: {trips_per_day:.2f}')

distance_per_day = selected_profiles_distance.sum(axis=1).mean()
print(f'Average distance per day: {distance_per_day:.2f} km')

distance_per_trip = selected_profiles_distance.stack().mean()
print(f'Average distance per trip: {distance_per_trip:.2f} km')


''' # --------------------- # Analysis # --------------------- # '''

# df_razdalje = pd.read_excel('Trip_distances.xlsx')
# df_razdalje = df_razdalje[0:109]
#
# distances = df_razdalje['Dolžina_avto']
# distance_values = distances.values
#
# counts = df_razdalje['Count of število poti']
#
# data = []
# for distance, count in zip(distances, counts):
#     data.extend(np.repeat(distance, count))
# fig = go.Figure()
#
#
# sampled_distances = pd.Series(selected_profiles_distance.values.ravel())
# sampled_distances = sampled_distances.dropna()
# sampled_distances = sampled_distances[sampled_distances != 'None']
#
#
# fig = go.Figure()
# # fig.add_trace(go.Histogram(x=data, histnorm='probability', marker_color='#007fad', name='Original'))
# # fig.add_trace(go.Histogram(x=generated_ds_pdf, histnorm='probability', marker_color='darkred', name='Generated'))
# fig.add_trace(go.Histogram(x=np.abs(sampled_distances), histnorm='probability', marker_color='darkgreen', name='Sampled'))
#
# fig.update_layout(
#     title_text='Število poti',
#     xaxis_title_text='Prevožena razdalja [km]',
#     yaxis_title_text='Število poti',
#     bargap=0.2
# )
# fig.show()


''' # --------------------- # Save results # --------------------- # '''

version = 1
selected_profiles_index_df.to_excel(f'Selected_profiles_v{version}.xlsx')
df_start_time.to_excel(f'df_start_time_v{version}.xlsx')
df_end_time.to_excel(f'df_end_time_v{version}.xlsx')
df_start_location.to_excel(f'df_start_location_v{version}.xlsx')
df_end_location.to_excel(f'df_end_location_v{version}.xlsx')
df_house_id.to_excel(f'df_house_id_v{version}.xlsx')
df_distance.to_excel(f'df_distance_v{version}.xlsx')

gauss_trips_pdf_df.to_excel(f'df_gauss_v{version}.xlsx')
generated_data_df.to_excel(f'df_generated_data_v{version}.xlsx')
trip_beginnings_df.to_excel(f'df_trip_beginnings_v{version}.xlsx')

df_start_time_15_min.to_excel(f'df_start_time_15min_v{version}.xlsx')
df_end_time_15_min.to_excel(f'df_end_time_15min_v{version}.xlsx')
