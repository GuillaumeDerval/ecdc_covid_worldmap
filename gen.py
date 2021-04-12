import pandas as pd
import geopandas

owid = pd.read_csv("https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv")
owid["date"] = pd.to_datetime(owid["date"])
owid.set_index(["iso_code", "date"], inplace=True)


def get_column_increment(countrycode, column, delta=7):
    country_data = owid.loc[countrycode].dropna(subset=[column])
    best_date = None
    count = None
    for d in country_data.index:
        if best_date is None or d > best_date:
            a = country_data.loc[d, column]
            try:
                b = country_data.loc[d - timedelta(days=delta), column]
            except Exception as e:
                continue
            count = a - b
            best_date = d
    return best_date, count


def find_consecutive_days(days, delta):
    days = sorted(days)
    nb_consecutive = 0
    last = None
    best_ever = None
    for d in days:
        if last is None or d - last != timedelta(days=1):
            nb_consecutive = 1
        else:
            nb_consecutive += 1
        if nb_consecutive >= delta:
            best_ever = d
        last = d
    if best_ever is None:
        return None, None

    return best_ever - timedelta(days=delta - 1), best_ever


def get_column_consecutive_total(countrycode, column, delta=7):
    country_data = owid.loc[countrycode].dropna(subset=[column])
    country_data.reset_index(inplace=True)
    country_data.set_index(["date"], inplace=True)
    first_day, last_day = find_consecutive_days(country_data.index, delta)
    if last_day is None:
        return None, None
    return last_day, country_data.loc[first_day:last_day, column].sum()


def select_best_among(countrycode, new_col, total_col, delta):
    a, b = get_column_increment(countrycode, total_col, delta)
    c, d = get_column_consecutive_total(countrycode, new_col, delta)
    if a is None and c is None:
        return None, None
    if a is None:
        return c, d
    if c is None:
        return a, b
    if a < c:
        return c, d
    return a, b


def get_tests_per_100000(countrycode, delta=7):
    a, b = select_best_among(countrycode, "new_tests_per_thousand", "total_tests_per_thousand", delta)
    if a is None:
        return a, b
    return a, b * 100


def get_cases_per_100000(countrycode, delta):
    a, b = select_best_among(countrycode, "new_cases_per_million", "total_cases_per_million", delta)
    if a is None:
        return a, b
    return a, b / 10.0


colors = {
    "NO_DATA",
    "TOO_LOW_TESTING",
    "GREEN",
    "ORANGE",
    "RED",
    "DARKRED"
}

from datetime import timedelta, datetime


def get_color(last_day, nr_14, pr, tests):
    if datetime.now() - last_day > timedelta(days=14):
        return "NO_DATA"
    if tests < 300:
        return "TOO_LOW_TESTING"
    if pr < 4.0 and nr_14 < 25:
        return "GREEN"
    if nr_14 < 50 or (nr_14 < 150 and pr < 4.0):
        return "ORANGE"
    if nr_14 < 500:
        return "RED"
    return "DARKRED"


data = []
for countrycode in owid.index.levels[0]:
    up_c_2w, notification_rate = get_cases_per_100000(countrycode, 14)
    up_c_lw, new_cases_lw = get_cases_per_100000(countrycode, 7)
    up_t_lw, new_tests_lw = get_tests_per_100000(countrycode, 7)

    if up_c_2w and up_c_lw and up_t_lw:
        positive_rate = 100.0 * new_cases_lw / new_tests_lw
        last_day = min(up_c_2w, up_c_lw, up_t_lw)
        data.append((countrycode, get_color(last_day, notification_rate, positive_rate, new_tests_lw), last_day,
                     notification_rate, positive_rate, new_tests_lw))
data.append(("NO_DATA", "NO_DATA", None, 0, 0, 0))

data = pd.DataFrame(data=data, columns=["CountryCode", "Color", "LastUpdate", "NotificationRatePer100000", "PositiveRate", "TestsPer100000"]).set_index("CountryCode")

world_map = geopandas.read_file("sources/worldmap.geojson")
def func(x):
    try:
        return data.loc[x.iso_a3]
    except:
        return data.loc["NO_DATA"]
world_map = pd.concat([world_map, world_map.apply(func, axis=1)], axis=1)
world_map.to_file("covid.geojson", driver='GeoJSON')
data.to_excel("covid.xlsx")
data.to_csv("covid.csv")