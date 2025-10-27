def format_data(sensor_id, timestamp, params, low_battery):
    header = f"{timestamp} - "

    if low_battery:
        header += f"WARNING: LOW BATTERY {sensor_id}\n"
    else:
        header += f"{sensor_id}\n"

    line = "; ".join(f"{key}: {value}" for key, value in params.items()) + ";"

    return header + line + "\n"
