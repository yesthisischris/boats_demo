import geopandas as gpd
import h3
import matplotlib.pyplot as plt
import contextily as ctx
from shapely.geometry import Polygon
from shapely.geometry import box
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib import colormaps

def generate_vignette_plot(vessel_gdf, mmsi_list, start_time, end_time, buffer_hrs=0):
    """
    Generates a vignette plot for the specified vessels, time range, and parameters.

    Parameters:
        vessel_gdf (GeoDataFrame): The full vessel GeoDataFrame containing vessel data.
        mmsi_list (list): List of MMSI values to filter.
        start_time (str or datetime): Start time for filtering data.
        end_time (str or datetime): End time for filtering data.
        buffer_hrs (int): Buffer time in hours to extend the start and end times.

    Returns:
        fig, ax: Matplotlib figure and axis objects for further customization or saving.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from shapely.geometry import Point
    from datetime import datetime, timedelta
    import contextily as ctx

    # Convert start_time and end_time to datetime if they are strings
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    # Apply buffer to the start and end times
    start_time -= timedelta(hours=buffer_hrs)
    end_time += timedelta(hours=buffer_hrs)

    # Filter the GeoDataFrame by MMSI and time range
    filtered_gdf = vessel_gdf[
        (vessel_gdf['mmsi'].isin(mmsi_list)) &
        (vessel_gdf['dt'] >= start_time) &
        (vessel_gdf['dt'] <= end_time)
    ].copy()

    # Create a relative time column (hours since the first dt in the filtered data)
    min_time = filtered_gdf['dt'].min()
    filtered_gdf['relative_time'] = (filtered_gdf['dt'] - min_time).dt.total_seconds() / 3600.0

    # Calculate plot extents with a 5% buffer
    bounds = filtered_gdf.total_bounds  # [minx, miny, maxx, maxy]
    x_buffer = (bounds[2] - bounds[0]) * 0.05
    y_buffer = (bounds[3] - bounds[1]) * 0.05
    extent = [float(bounds[0] - x_buffer), float(bounds[2] + x_buffer),
              float(bounds[1] - y_buffer), float(bounds[3] + y_buffer)]

    # Start the plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # Set up colormap and normalization for relative time
    cmap = plt.cm.viridis
    rel_min, rel_max = filtered_gdf['relative_time'].min(), filtered_gdf['relative_time'].max()
    norm = plt.Normalize(rel_min, rel_max)

    # Assign shapes for each MMSI (handle cases with one MMSI)
    shapes = {mmsi: (3, 0, 0) if i == 0 else 'o' for i, mmsi in enumerate(mmsi_list)}

    # Keep track of labels for legend
    legend_handles = {}

    # Plot each position using unique shape and color based on relative time
    for _, row in filtered_gdf.iterrows():
        x, y = row.geometry.x, row.geometry.y
        rt = row['relative_time']
        face_col = cmap(norm(rt))
        heading_deg = row['heading'] - 90  # rotate marker to point in heading direction
        mmsi = row['mmsi']
        marker_shape = shapes.get(mmsi, (3, 0, heading_deg))
        if isinstance(marker_shape, tuple):
            marker_shape = (3, 0, heading_deg)
        sc = ax.scatter(x, y,
                        s=100,
                        marker=marker_shape,
                        facecolor=face_col,
                        label=str(mmsi) if mmsi not in legend_handles else "")
        if mmsi not in legend_handles:
            legend_handles[mmsi] = mpatches.Patch(label=str(mmsi), facecolor='gray')

    # Add base map
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik,
                    crs=filtered_gdf.crs.to_string())

    # Apply buffered extents
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])

    # Add a colorbar for relative time
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical', pad=0.02)
    cbar.set_label('Relative Time (hours)')

    # Styling
    ax.set_title('Vessel Vignette', fontsize=16)
    ax.axis('off')

    # Add legend for MMSI marker types
    ax.legend(title="MMSI", loc='upper left')

    # Information text below plot
    info_text = (
        f"Start Time: {start_time.isoformat()}\n"
        f"End Time: {end_time.isoformat()}\n"
        f"Extents: [{extent[0]:.5f}, {extent[1]:.5f}, {extent[2]:.5f}, {extent[3]:.5f}]"
    )
    plt.figtext(0.5, -0.1, info_text, wrap=True, ha='center', fontsize=10)

    return fig, ax


def plot_h3_heatmap(
    df,
    h3_column,
    heatmap_column,
    resolution=None,
    use_parent_level=None,
    basemap=True,
    figsize=(12, 8)
):
    """
    Plots a complete H3 heatmap covering the map boundaries using GeoPandas and Contextily.
    Optionally aggregates cells up to a parent H3 resolution before plotting.

    Parameters:
        df (GeoDataFrame or DataFrame): Input data containing H3 cell IDs and heat values.
        h3_column (str): Name of the column with H3 cell IDs.
        heatmap_column (str): Name of the column with heatmap values.
        resolution (int): H3 resolution for filling the map (inferred if None).
        use_parent_level (int): If set, parent resolution to aggregate to (<= original resolution).
        basemap (bool): Whether to include a basemap (default True).
        figsize (tuple): Matplotlib figure size (default (12, 8)).

    Returns:
        fig, ax: Matplotlib figure and axis.
    """
    # Ensure we have the column
    if h3_column not in df.columns:
        raise KeyError(f"Column '{h3_column}' not found in DataFrame.")

    # Detect original resolution if not provided
    sample_h3 = df[h3_column].iloc[0]
    orig_res = h3.h3_get_resolution(sample_h3)
    if resolution is None:
        resolution = orig_res

    # Aggregate to parent level if requested
    if use_parent_level is not None:
        if use_parent_level > orig_res:
            raise ValueError(
                f"use_parent_level ({use_parent_level}) must be <= data resolution ({orig_res})."
            )
        # Compute parent cells
        df[h3_column] = df[h3_column].apply(
            lambda cell: h3.h3_to_parent(cell, use_parent_level)
        )
        # Sum heatmap values per parent cell
        df = df.groupby(h3_column, as_index=False)[heatmap_column].sum()
        # After aggregation, reset resolution to parent
        resolution = use_parent_level

    # Convert H3 cells to polygons
    df['geometry'] = df[h3_column].apply(
        lambda h3_cell: Polygon(h3.h3_to_geo_boundary(h3_cell, geo_json=True))
    )

    # Create GeoDataFrame
    h3_gdf = gpd.GeoDataFrame(
        {h3_column: df[h3_column],
         'heatmap_value': df[heatmap_column],
         'geometry': df['geometry']},
        crs="EPSG:4326"
    )

    # Compute bounds and fill missing cells
    bounds = h3_gdf.total_bounds  # [minx, miny, maxx, maxy]
    bounding_box = box(bounds[0], bounds[1], bounds[2], bounds[3])
    full_cells = h3.polyfill_geojson(bounding_box.__geo_interface__, resolution)

    # Build full grid
    grid_geoms, grid_vals = [], []
    val_map = dict(zip(h3_gdf[h3_column], h3_gdf['heatmap_value']))
    for cell in full_cells:
        poly = Polygon(h3.h3_to_geo_boundary(cell, geo_json=True))
        grid_geoms.append(poly)
        grid_vals.append(val_map.get(cell, 0))

    grid_gdf = gpd.GeoDataFrame(
        {'geometry': grid_geoms, 'heatmap_value': grid_vals},
        crs="EPSG:4326"
    )

    # Project to Web Mercator
    grid_gdf = grid_gdf.to_crs("EPSG:3857")

    # Normalize and style
    norm = Normalize(vmin=grid_gdf['heatmap_value'].min(), vmax=grid_gdf['heatmap_value'].max())
    cmap = colormaps['Reds']
    sm = ScalarMappable(norm=norm, cmap=cmap)

    # Plot
    fig, ax = plt.subplots(figsize=figsize)
    grid_gdf.plot(
        column='heatmap_value',
        cmap='Reds',
        linewidth=0.1,
        edgecolor='black',
        alpha=0.6,
        legend=False,
        ax=ax
    )
    if basemap:
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs=grid_gdf.crs)

    ax.set_xlim(grid_gdf.total_bounds[0], grid_gdf.total_bounds[2])
    ax.set_ylim(grid_gdf.total_bounds[1], grid_gdf.total_bounds[3])

    # Colorbar
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical', fraction=0.03, pad=0.04)
    cbar.set_ticks([norm.vmin, norm.vmax])
    cbar.set_ticklabels(['Less common', 'More common'])

    ax.set_title('H3 Heatmap', fontsize=16)
    ax.axis('off')

    return fig, ax