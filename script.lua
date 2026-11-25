nimbus_proto = Proto("Nimbus", "Nimbus IoT Weather Protocol")

local f = nimbus_proto.fields

f.first_byte = ProtoField.uint8("nimbus.first_byte", "First Byte", base.HEX)
local PACKET_TYPES = {
    [0] = "REGISTRATION",
    [1] = "DATA",
    [2] = "ACTIVITY_CONFIRMATION",
    [3] = "REGISTRATION_RESPONSE",
    [4] = "DATA_RECEIVED",
    [5] = "REQUEST_RESEND",
    [6] = "INVALID_TOKEN",
    [7] = "ACTIVITY_CHECK"
}

local SENSOR_TYPES = {
    [0] = "THERMONODE",
    [1] = "WINDSENSE",
    [2] = "RAINDETECT",
    [3] = "AIRQUALITYBOX"
}

f.packet_type = ProtoField.uint8("nimbus.packet_type", "Packet Type", base.DEC, PACKET_TYPES, 0xE0)
f.sensor_id = ProtoField.uint8("nimbus.sensor_id", "Sensor ID", base.DEC, SENSOR_TYPES, 0x18)

f.low_battery = ProtoField.bool("nimbus.low_battery", "Low Battery", 8, nil, 0x04)
f.timestamp = ProtoField.uint32("nimbus.timestamp", "Timestamp", base.DEC)
f.token = ProtoField.uint32("nimbus.token", "Token", base.DEC)
f.checksum = ProtoField.uint32("nimbus.checksum", "Checksum", base.DEC)

function nimbus_proto.dissector(buffer, pinfo, tree)
    local length = buffer:len()
    if length == 0 then return end

    pinfo.cols.protocol = nimbus_proto.name

    local subtree = tree:add(nimbus_proto, buffer(), "Nimbus Protocol")

    local first_byte = buffer(0,1):uint()
    subtree:add(f.first_byte, buffer(0,1))
    subtree:add(f.packet_type, buffer(0,1))
    subtree:add(f.sensor_id, buffer(0,1))

    local packet_type = bit.rshift(bit.band(first_byte, 0xE0), 5)
    local sensor_id = bit.rshift(bit.band(first_byte, 0x18), 3)

    local low_battery = bit.band(first_byte, 0x04) ~= 0

    if packet_type == 0 or packet_type == 1 or packet_type == 2 then
        subtree:add(f.low_battery, buffer(0,1))
    end

    local packet_type_str = PACKET_TYPES[packet_type] or "UNKNOWN"
    local sensor_type_str = SENSOR_TYPES[sensor_id] or "UNKNOWN"

    local battery_info = ""
    if low_battery and (packet_type == 0 or packet_type == 1 or packet_type == 2) then
        battery_info = " [LOW_BATTERY]"
    end

    pinfo.cols.info:set(string.format("%s - %s%s [Len=%d]", packet_type_str, sensor_type_str, battery_info, length))

    local offset = 1

    if packet_type == 0 then
        if length >= 5 then
            subtree:add(f.timestamp, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 9 then
            subtree:add(f.checksum, buffer(offset,4))
        end

    elseif packet_type == 1 then
        if length >= 5 then
            subtree:add(f.token, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 9 then
            subtree:add(f.timestamp, buffer(offset,4))
            offset = offset + 4
        end

        local data_size = 0
        if sensor_id == 0 then data_size = 6
        elseif sensor_id == 1 then data_size = 4
        elseif sensor_id == 2 then data_size = 4
        elseif sensor_id == 3 then data_size = 5 end

        if length >= offset + data_size then
            subtree:add(buffer(offset, data_size), "Sensor Data (" .. data_size .. " bytes)")
            offset = offset + data_size
        end

        if length >= offset + 4 then
            subtree:add(f.checksum, buffer(offset,4))
        end

    elseif packet_type == 2 then
        if length >= 5 then
            subtree:add(f.token, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 9 then
            subtree:add(f.timestamp, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 13 then
            subtree:add(f.checksum, buffer(offset,4))
        end

    elseif packet_type == 3 then
        if length >= 5 then
            subtree:add(f.token, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 9 then
            subtree:add(f.timestamp, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 13 then
            subtree:add(f.checksum, buffer(offset,4))
        end

    else
        if length >= 5 then
            subtree:add(f.timestamp, buffer(offset,4))
            offset = offset + 4
        end
        if length >= 9 then
            subtree:add(f.checksum, buffer(offset,4))
        end
    end
end

local udp_port = DissectorTable.get("udp.port")
udp_port:add(5005, nimbus_proto)
