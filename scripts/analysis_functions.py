import pandas as pd
from geopy.distance import geodesic
from shapely.geometry import Point
import h3
import pandas as pd


def identify_dark_periods(gdf, time_threshold=1):
    """
    Identifies periods where a vessel went 'dark' for more than the specified time threshold.

    Parameters:
        gdf (GeoDataFrame): Geopandas DataFrame containing AIS data.
                           Must include 'mmsi', 'dt', 'geometry', and H3 hexagon columns ('h3_lv2', 'h3_lv3', 'h3_lv4', 'h3_lv5', 'h3_lv6', 'h3_lv7').
        time_threshold (float): Time threshold in hours to identify a 'dark period'.

    Returns:
        GeoDataFrame: A GeoDataFrame containing the dark periods with columns:
                   ['mmsi', 'dt_start', 'dt_end', 'geometry_start', 'geometry_end', 'time_dark_hrs',
                    'km_travelled', 'h3_lv2_start', 'h3_lv2_end', 'h3_lv3_start', 'h3_lv3_end',
                    'h3_lv4_start', 'h3_lv4_end', 'h3_lv5_start', 'h3_lv5_end',
                    'h3_lv6_start', 'h3_lv6_end', 'h3_lv7_start', 'h3_lv7_end']
    """
    # Ensure the data is sorted by 'mmsi' and 'dt'
    gdf = gdf.sort_values(by=['mmsi', 'dt'])

    # Initialize an empty list to store dark period data
    dark_periods = []

    # Group by MMSI to process each ship's data individually
    for mmsi, group in gdf.groupby('mmsi'):
        group = group.sort_values(by='dt')  # Ensure sorted by time
        group['time_diff'] = group['dt'].diff().dt.total_seconds() / 3600  # Time diff in hours

        # Identify rows where the time difference exceeds the threshold
        dark_rows = group[group['time_diff'] > time_threshold]

        for idx, row in dark_rows.iterrows():
            # Use iloc to safely access rows in the DataFrame
            prev_row = group.iloc[group.index.get_loc(idx) - 1]  # Previous row

            dt_start = prev_row['dt']  # Timestamp before the gap
            dt_end = row['dt']         # Timestamp after the gap
            geometry_start = prev_row['geometry']  # Geometry before the gap
            geometry_end = row['geometry']         # Geometry after the gap
            time_dark_hrs = (dt_end - dt_start).total_seconds() / 3600  # Duration in hours
            km_travelled = geodesic(
                (geometry_start.y, geometry_start.x),
                (geometry_end.y, geometry_end.x)
            ).kilometers  # Distance traveled

            # Add H3 hexagons for start and end
            h3_lv2_start = prev_row['h3_lv2']
            h3_lv2_end = row['h3_lv2']
            h3_lv3_start = prev_row['h3_lv3']
            h3_lv3_end = row['h3_lv3']
            h3_lv4_start = prev_row['h3_lv4']
            h3_lv4_end = row['h3_lv4']
            h3_lv5_start = prev_row['h3_lv5']
            h3_lv5_end = row['h3_lv5']
            h3_lv6_start = prev_row['h3_lv6']
            h3_lv6_end = row['h3_lv6']
            h3_lv7_start = prev_row['h3_lv7']
            h3_lv7_end = row['h3_lv7']

            # Append the data to the list
            dark_periods.append({
                'mmsi': mmsi,
                'dt_start': dt_start,
                'dt_end': dt_end,
                'geometry_start': geometry_start,
                'geometry_end': geometry_end,
                'time_dark_hrs': time_dark_hrs,
                'km_travelled': km_travelled,
                'h3_lv2_start': h3_lv2_start,
                'h3_lv2_end': h3_lv2_end,
                'h3_lv3_start': h3_lv3_start,
                'h3_lv3_end': h3_lv3_end,
                'h3_lv4_start': h3_lv4_start,
                'h3_lv4_end': h3_lv4_end,
                'h3_lv5_start': h3_lv5_start,
                'h3_lv5_end': h3_lv5_end,
                'h3_lv6_start': h3_lv6_start,
                'h3_lv6_end': h3_lv6_end,
                'h3_lv7_start': h3_lv7_start,
                'h3_lv7_end': h3_lv7_end,
            })

    # Convert the list to a GeoDataFrame
    darkperiods = pd.DataFrame(dark_periods)

    return darkperiods


def find_proximity_dark_periods(darkperiods, h3_level):
    """
    Identifies periods where two or more vessels were dark within the same H3 cell at a given level
    and during overlapping time windows.

    Parameters:
        darkperiods (GeoDataFrame): The GeoDataFrame containing dark period data.
                                    Must include 'mmsi', 'dt_start', 'dt_end', 'geometry_start', and 'geometry_end'.
        h3_level (int): The H3 resolution level to use for proximity checks.

    Returns:
        DataFrame: A DataFrame containing pairs of vessels that were dark in the same H3 cell
                during overlapping time windows.
                Columns: ['mmsi_1', 'mmsi_2', 'dt_start_1', 'dt_end_1', 'geometry_start_1', 'geometry_end_1',
                            'dt_start_2', 'dt_end_2', 'geometry_start_2', 'geometry_end_2',
                            'h3_start_1', 'h3_start_2', 'h3_end_1', 'h3_end_2']
    """
    # Initialize a list to store proximity matches
    proximity_matches = []

    # Iterate through each pair of dark periods
    for i, row1 in darkperiods.iterrows():
        for j, row2 in darkperiods.iterrows():
            # Skip comparing a dark period with itself or with the same MMSI
            if i >= j or row1['mmsi'] == row2['mmsi']:
                continue

            # Calculate H3 cell IDs for the specified resolution level
            h3_start_1 = h3.geo_to_h3(row1['geometry_start'].y, row1['geometry_start'].x, h3_level)
            h3_start_2 = h3.geo_to_h3(row2['geometry_start'].y, row2['geometry_start'].x, h3_level)
            h3_end_1 = h3.geo_to_h3(row1['geometry_end'].y, row1['geometry_end'].x, h3_level)
            h3_end_2 = h3.geo_to_h3(row2['geometry_end'].y, row2['geometry_end'].x, h3_level)

            # Check if they occupy the same H3 cell (start or end)
            same_h3_start = h3_start_1 == h3_start_2
            same_h3_end = h3_end_1 == h3_end_2

            # Only proceed if there's an H3 match (either start or end)
            if same_h3_start or same_h3_end:
                # Check if their time windows overlap
                time_overlap = (
                    max(row1['dt_start'], row2['dt_start']) <= min(row1['dt_end'], row2['dt_end'])
                )

                # Only register a match if both H3 cell and time window conditions are met
                if time_overlap:
                    proximity_matches.append({
                        'mmsi_1': row1['mmsi'],
                        'mmsi_2': row2['mmsi'],
                        'dt_start_1': row1['dt_start'],
                        'dt_end_1': row1['dt_end'],
                        'geometry_start_1': row1['geometry_start'],
                        'geometry_end_1': row1['geometry_end'],
                        'dt_start_2': row2['dt_start'],
                        'dt_end_2': row2['dt_end'],
                        'geometry_start_2': row2['geometry_start'],
                        'geometry_end_2': row2['geometry_end'],
                        'h3_start_1': h3_start_1,
                        'h3_start_2': h3_start_2,
                        'h3_end_1': h3_end_1,
                        'h3_end_2': h3_end_2,
                    })

    # Convert the matches list to a DataFrame
    proximity_df = pd.DataFrame(proximity_matches)

    return proximity_df


def compute_colocations(df, h3_col, time_buffer_hours):
    """
    Identify and collapse co-location episodes between vessel pairs based on identical H3 cells
    and a maximum time buffer.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns 'mmsi', 'dt' (datetime), and the specified H3 column.
    h3_col : str
        Name of the H3 column (e.g. 'h3_lv7').
    time_buffer_hours : float
        Max time difference (in hours) to consider two points co-located and to chain into episodes.

    Returns
    -------
    pd.DataFrame
        Columns: vessel_1, vessel_2, start, end, duration, n_colocated, n_noncolocated
    """
    df = df.copy()
    # ensure datetime
    df['dt'] = pd.to_datetime(df['dt'])
    df = df.sort_values('dt').reset_index(drop=True)

    # convert to pd.Timedelta
    max_td = pd.Timedelta(hours=time_buffer_hours)

    # 1) Find all pairwise co-located point instances
    records = []
    for idx, row in df.iterrows():
        same_h3 = df[
            (df[h3_col] == row[h3_col]) &
            (df['mmsi'] != row['mmsi'])
        ]
        # time filter
        window = same_h3[
            (same_h3['dt'] >= row['dt'] - max_td) &
            (same_h3['dt'] <= row['dt'] + max_td)
        ]
        for _, r2 in window.iterrows():
            v1, v2 = sorted((row['mmsi'], r2['mmsi']))
            records.append({
                'vessel_1': v1,
                'vessel_2': v2,
                'time': min(row['dt'], r2['dt']),
            })

    if not records:
        return pd.DataFrame(columns=[
            'vessel_1','vessel_2','start','end','duration',
            'n_colocated','n_noncolocated'
        ])

    inst = pd.DataFrame(records)
    inst = inst.drop_duplicates().sort_values(['vessel_1','vessel_2','time'])

    # 2) Group into continuous episodes per pair
    episodes = []
    for (v1, v2), grp in inst.groupby(['vessel_1','vessel_2']):
        times = grp['time'].tolist()
        # seed first episode
        ep_times = [times[0]]
        for t in times[1:]:
            if t - ep_times[-1] <= max_td:
                ep_times.append(t)
            else:
                # close out previous episode
                episodes.append((v1, v2, ep_times))
                ep_times = [t]
        episodes.append((v1, v2, ep_times))

    # 3) Collapse each episode to summary stats
    out = []
    for v1, v2, ep_times in episodes:
        start, end = min(ep_times), max(ep_times)
        dur = end - start
        n_co = len(ep_times)
        # count all points by these two in that window
        win_pts = df[
            (df['mmsi'].isin((v1, v2))) &
            (df['dt'] >= start) &
            (df['dt'] <= end)
        ]
        n_non = len(win_pts) - n_co
        out.append({
            'vessel_1': v1,
            'vessel_2': v2,
            'start': start,
            'end': end,
            'duration': dur,
            'n_colocated': n_co,
            'n_noncolocated': n_non
        })

    return pd.DataFrame(out)


