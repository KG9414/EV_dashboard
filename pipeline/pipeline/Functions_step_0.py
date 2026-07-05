import numpy as np
import pandas as pd
from scipy.stats import norm
import math

def round_hhmm_to_15min(hhmm_array, mode="round"):
    rounded_times = []
    for hhmm in hhmm_array:
        hour = hhmm // 100
        minute = hhmm % 100
        total_minutes = hour * 60 + minute

        if mode == "floor":
            rounded_minutes = (total_minutes // 15) * 15
        elif mode == "ceil":
            rounded_minutes = math.ceil(total_minutes / 15) * 15
        else:  # default is round
            rounded_minutes = round(total_minutes / 15) * 15

        new_hour = rounded_minutes // 60
        new_minute = rounded_minutes % 60
        rounded_times.append(f"{new_hour:02}:{new_minute:02}")
    return rounded_times


def round_hhmm_to_1h(hhmm_array):
    rounded_times = []
    for hhmm in hhmm_array:
        hour = hhmm // 100
        minute = hhmm % 100
        total_minutes = hour * 60 + minute
        rounded_minutes = round(total_minutes / 15) * 15
        new_hour = rounded_minutes // 60
        new_minute = rounded_minutes % 60
        rounded_times.append(f"{new_hour:02}:00")
    return rounded_times


def normal_distribution(parameters, number_of_components):
    x = np.linspace(0, 23.75, 96)
    distribution = pd.Series([0]*96)
    for i in range(number_of_components):
        distribution = distribution + parameters[2, i] * norm.pdf(x, parameters[0, i], parameters[1, i])
    return distribution


def float_to_15min(hours):
    total_minutes = np.round(hours * 60 / 15) * 15
    h = (total_minutes // 60).astype(int)
    m = (total_minutes % 60).astype(int)
    return [f"{hour:02}:{minute:02}" for hour, minute in zip(h, m)]


def float_to_1h(hours):
    total_minutes = np.round(hours * 60 / 15) * 15
    h = (total_minutes // 60).astype(int)
    m = (total_minutes % 60).astype(int)
    return [f"{hour:02}:00" for hour, minute in zip(h, m)]