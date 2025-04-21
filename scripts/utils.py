import pyarrow.parquet as pq

# import snappy parquet file as pandas dataframe
def load_parquet(file_path):
    try:
        # Read the Parquet file
        df = pq.read_table(file_path).to_pandas()
        print("Parquet file loaded successfully.")
        return df
    except Exception as e:
        print(f"Error loading Parquet file: {e}")
        return None
