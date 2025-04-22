-- Fire Emblem Memory Reader - Terrain Map Builder
-- This script reads terrain data from EWRAM and builds a map visualization

-- Constants for memory locations (EWRAM offsets)
local MAP_WIDTH_ADDR = 0x0202E3D8
local MAP_HEIGHT_ADDR = 0x0202E3DA
local TERRAIN_PTR_TABLE_ADDR = 0x0202E3E0

-- Output file path
local output_file_path = "data/fe_map.txt"

-- Function to read a byte from memory
function readByte(address)
  return memory.readbyte(address)
end

-- Function to read 4 bytes (a pointer) from memory - little endian format
function readPointer(address)
  -- Create our own 4-byte reader using readbyte (little endian order)
  local b0 = memory.readbyte(address)
  local b1 = memory.readbyte(address + 1)
  local b2 = memory.readbyte(address + 2)
  local b3 = memory.readbyte(address + 3)

  -- Combine bytes in little-endian format (least significant byte first)
  return b0 + (b1 * 0x100) + (b2 * 0x10000) + (b3 * 0x1000000)
end

-- Terrain types with character representation matching main.py
local terrain_data = {
  [0x00] = {char = "-", name = "--"},
  [0x01] = {char = ".", name = "Plains"},
  [0x02] = {char = "=", name = "Road"},
  [0x03] = {char = "V", name = "Village"},
  [0x04] = {char = "V", name = "Village"},
  [0x05] = {char = "H", name = "House"},
  [0x06] = {char = "A", name = "Armory"},
  [0x07] = {char = "V", name = "Vendor"},
  [0x08] = {char = "A", name = "Arena"},
  [0x09] = {char = "C", name = "C Room"},
  [0x0A] = {char = "C", name = "Fort"},
  [0x0B] = {char = "G", name = "Gate"},
  [0x0C] = {char = "F", name = "Forest"},
  [0x0D] = {char = "F", name = "Thicket"},
  [0x0E] = {char = "S", name = "Sand"},
  [0x0F] = {char = "D", name = "Desert"},
  [0x10] = {char = "~", name = "River"},
  [0x11] = {char = "^", name = "Hill"},
  [0x12] = {char = "M", name = "Peak"},
  [0x13] = {char = "=", name = "Bridge"},
  [0x14] = {char = "=", name = "Bridge[Draw]"},
  [0x15] = {char = "~", name = "Sea"},
  [0x16] = {char = "~", name = "Lake"},
  [0x17] = {char = ".", name = "Floor"},
  [0x18] = {char = "H", name = "Floor[Heal]"},
  [0x19] = {char = "#", name = "Fence"},
  [0x1A] = {char = "#", name = "Wall"},
  [0x1B] = {char = "#", name = "Wall[Damaged]"},
  [0x1C] = {char = "*", name = "Rubble"},
  [0x1D] = {char = "P", name = "Pillar"},
  [0x1E] = {char = "D", name = "Door"},
  [0x1F] = {char = "T", name = "Throne"},
  [0x20] = {char = "C", name = "Chest[Empty]"},
  [0x21] = {char = "C", name = "Chest"},
  [0x22] = {char = "R", name = "Roof"},
  [0x23] = {char = "G", name = "Gate"},
  [0x24] = {char = "H", name = "Church"},
  [0x3B] = {char = "X", name = "Dark"},
  [0x3F] = {char = "#", name = "Brace"}
}

-- Function to get display character for a terrain ID
function getTerrainChar(terrain_id)
  if terrain_data[terrain_id] then
    return terrain_data[terrain_id].char
  else
    -- Fallback to first letter of terrain name if we have it in tiles.json
    -- or just return hex value
    return string.format("%02X", terrain_id)
  end
end

-- Main function to build the terrain map and write it to a file
function buildTerrainMap()
  -- Read map dimensions
  local width = readByte(MAP_WIDTH_ADDR)
  local height = readByte(MAP_HEIGHT_ADDR)

  -- Create a map table to hold terrain data
  local map = {}

  -- Get the pointer to the row pointers array (First level of indirection)
  local row_pointers_table = readPointer(TERRAIN_PTR_TABLE_ADDR)

  -- Debug info
  local first_row_ptr_addr = row_pointers_table
  local first_row_ptr = readPointer(first_row_ptr_addr)
  local first_terrain_id = readByte(first_row_ptr)

  -- Read the terrain data correctly through two layers of pointers
  for y = 0, height-1 do
    -- Each row pointer is at row_pointers_table + (y * 4)
    local row_ptr_addr = row_pointers_table + (y * 4)

    -- Get the pointer to the actual row of terrain data (Second level of indirection)
    local row_data_ptr = readPointer(row_ptr_addr)

    map[y] = {}

    -- Read each terrain ID in the row
    for x = 0, width-1 do
      local terrain_id = readByte(row_data_ptr + x)
      map[y][x] = terrain_id
    end
  end

  -- Open the output file for writing
  local file = io.open(output_file_path, "w")
  if not file then
    print("Failed to open output file for writing")
    return nil
  end

  -- Write map dimensions to the file
  file:write(string.format("Map size: %dx%d\n\n", width, height))

  -- Write the map
  for y = 0, height-1 do
    local line = ""
    for x = 0, width-1 do
      local terrain_id = map[y][x]
      local terrain_char = getTerrainChar(terrain_id)
      line = line .. terrain_char .. " "
    end
    file:write(line .. "\n")
  end

  -- Write debug info about the pointers
  file:write(string.format("\nTerrain pointer table: 0x%08X\n", TERRAIN_PTR_TABLE_ADDR))
  file:write(string.format("Row pointers array: 0x%08X\n", row_pointers_table))
  file:write(string.format("First row pointer (addr): 0x%08X\n", first_row_ptr_addr))
  file:write(string.format("First row data (addr): 0x%08X\n", first_row_ptr))
  file:write(string.format("First terrain ID at 0x%08X: 0x%02X\n", first_row_ptr, first_terrain_id))

  -- Write terrain legend based on main.py format
  file:write("\nTerrain Legend:\n")
  file:write(". = Plains, F = Forest, ^ = Hill, M = Mountain/Peak, ~ = Water\n")
  file:write("H = House/Village, C = Castle/Fort, = = Road/Bridge, # = Wall, D = Door/Gate\n")
  file:write("R = Floor/Roof, T = Throne, B = Brace, X = Dark terrain\n")

  -- Close the file
  file:close()

  -- Simple status indicator
  gui.text(1, 1, string.format("Map data written to %s", output_file_path))

  -- Return the map data in case we want to use it elsewhere
  return {width = width, height = height, data = map}
end

-- Main execution loop
while true do
  buildTerrainMap()
  -- Update every 60 frames (about 1 second) to avoid excessive file writes
  for i = 1, 60 do
    emu.frameadvance()
  end
end
