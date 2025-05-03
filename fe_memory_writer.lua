-- fe_memory_writer.lua
-- Real-time RAM writer for Fire Emblem (BizHawk)
-- Reads commands from ../data/ram_edit_command.txt and writes to RAM

local command_file_path = "../data/ram_edit_command.txt"

-- Memory layout (must match fe_memory_reader.lua)
local MEMORY = {
  character = {
    base_addr = 0x0202BD50,
    size = 0x48,
    offsets = {
      hp = 0x13,         -- current HP
      max_hp = 0x12,
      str = 0x14,
      skl = 0x15,
      spd = 0x16,
      def = 0x17,
      res = 0x18,
      lck = 0x19,
      mov = 0x1D,
      -- Items (5 slots)
      item_type = {0x1E, 0x20, 0x22, 0x24, 0x26},
      item_uses = {0x1F, 0x21, 0x23, 0x25, 0x27}
    }
  },
  enemy = {
    base_addr = 0x0202CEC0,
    size = 0x48,
    offsets = {
      hp = 0x13,
      max_hp = 0x12,
      str = 0x14,
      skl = 0x15,
      spd = 0x16,
      def = 0x17,
      res = 0x18,
      lck = 0x19,
      mov = 0x1D,
      item_type = {0x1E, 0x20, 0x22, 0x24, 0x26},
      item_uses = {0x1F, 0x21, 0x23, 0x25, 0x27}
    }
  }
}

-- Helper: Write a stat to RAM
local function write_stat(unit_type, index, stat, value)
  local mem = MEMORY[unit_type]
  if not mem then return false, "Invalid unit type" end
  local addr = mem.base_addr + (index - 1) * mem.size
  local stat_map = {
    hp = mem.offsets.hp,
    max_hp = mem.offsets.max_hp,
    str = mem.offsets.str,
    skl = mem.offsets.skl,
    spd = mem.offsets.spd,
    def = mem.offsets.def,
    res = mem.offsets.res,
    lck = mem.offsets.lck,
    mov = mem.offsets.mov
  }
  local offset = stat_map[stat]
  if not offset then return false, "Invalid stat name" end
  memory.writebyte(addr + offset, value)
  return true
end

-- Helper: Write an item to RAM
local function write_item(unit_type, index, item_slot, item_id, uses)
  local mem = MEMORY[unit_type]
  if not mem then return false, "Invalid unit type" end
  if item_slot < 0 or item_slot > 4 then return false, "Invalid item slot" end
  local addr = mem.base_addr + (index - 1) * mem.size
  memory.writebyte(addr + mem.offsets.item_type[item_slot + 1], item_id)
  memory.writebyte(addr + mem.offsets.item_uses[item_slot + 1], uses)
  return true
end

-- Process a single command line
local function process_command(line)
  local args = {}
  for word in line:gmatch("%S+") do table.insert(args, word) end
  if #args == 0 then return end
  if args[1] == "set_stat" and #args == 5 then
    local unit_type = args[2]
    local index = tonumber(args[3])
    local stat = args[4]
    local value = tonumber(args[5])
    if not (unit_type and index and stat and value) then return end
    local ok, err = write_stat(unit_type, index, stat, value)
    if not ok then
      print("[RAM Writer] Error: " .. (err or "Unknown error"))
    else
      print(string.format("[RAM Writer] Set %s %d %s = %d", unit_type, index, stat, value))
    end
  elseif args[1] == "set_item" and #args == 6 then
    local unit_type = args[2]
    local index = tonumber(args[3])
    local item_slot = tonumber(args[4])
    local item_id = tonumber(args[5])
    local uses = tonumber(args[6])
    if not (unit_type and index and item_slot and item_id and uses) then return end
    local ok, err = write_item(unit_type, index, item_slot, item_id, uses)
    if not ok then
      print("[RAM Writer] Error: " .. (err or "Unknown error"))
    else
      print(string.format("[RAM Writer] Set %s %d item slot %d = id %d, uses %d", unit_type, index, item_slot, item_id, uses))
    end
  else
    print("[RAM Writer] Unknown or malformed command: " .. line)
  end
end

-- Efficiently process only if file is non-empty
local function process_command_file()
  local file = io.open(command_file_path, "r")
  if not file then return end
  local lines = {}
  for line in file:lines() do
    if line:match("%S") then table.insert(lines, line) end
  end
  file:close()
  if #lines == 0 then return end
  -- Process only the first line (for atomicity)
  process_command(lines[1])
  -- Rewrite the file without the first line
  local out = io.open(command_file_path, "w")
  for i = 2, #lines do
    out:write(lines[i] .. "\n")
  end
  out:close()
end

-- Register to run every frame
console.log("[RAM Writer] Loaded and running!")
event.onframeend(process_command_file)