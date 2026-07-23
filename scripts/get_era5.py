import cdsapi

c = cdsapi.Client()

c.retrieve(
    "reanalysis-era5-single-levels",
    {
        "product_type": "reanalysis",
        "variable": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "2m_temperature",
            "2m_dewpoint_temperature",
            "total_precipitation",
        ],
        "year": "2025",
        "month": "03",
        "day": ["21", "22", "23", "24", "25", "26", "27", "28"],
        "time": ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"],
        "area": [36.90, 128.97, 36.10, 129.77],
        "data_format": "netcdf",
        "download_format": "zip",
    },
    "data/raw/firms/yeongdeok_2025_era5.nc",
)
print("done — file at data/raw/firms/yeongdeok_2025_era5.nc")
