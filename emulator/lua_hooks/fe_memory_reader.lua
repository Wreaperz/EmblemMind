-- Fire Emblem Memory Reader for BizHawk
-- Targets FE7 GBA Game
-- Uses exact CodeBreaker memory addresses

local output_file_path = "fe_state.txt"

local MEMORY = {
  -- Global game state
  turn_phase = 0x0202BC07,     -- 00 = Player, 40 = Neutral, 80 = Enemy
  current_turn = 0x0202BC08,   -- Current turn number
  chapter_id = 0x0202BC06,     -- Current chapter ID
  gold = 0x0202BC00,           -- Gold/money (from CodeBreaker: "Money - 8202BC00 ZZZZ")

  -- Tactician name (7 characters max)
  tactician = {
    char1 = 0x0202BC18,
    char2 = 0x0202BC19,
    char3 = 0x0202BC1A,
    char4 = 0x0202BC1B,
    char5 = 0x0202BC1C,
    char6 = 0x0202BC1D,
    char7 = 0x0202BC1E
  },

  -- Cursor and camera
  cursor_x = 0x0202BBD0,       -- Map tile cursor x position
  cursor_y = 0x0202BBD2,       -- Map tile cursor y position
  camera_x = 0x0202BC2C,       -- Camera pixel position
  camera_y = 0x0202BC2E,       -- Camera pixel position

  -- Character data - exact offsets from CodeBreaker codes
  character = {
    base_addr = 0x0202BD50,    -- Starting address for character slot 1
    size = 0x48,               -- 72 bytes per character (0x48)

    -- Offsets from the character's base address
    offsets = {
      character_id = 0x00,
      class_id = 0x04,
      level = 0x08,
      experience = 0x09,
      turn_status = 0x0C,
      hidden_status = 0x0D,
      x_pos = 0x10,
      y_pos = 0x11,
      max_hp = 0x12,
      current_hp = 0x13,
      strength = 0x14,
      skill = 0x15,
      speed = 0x16,
      defense = 0x17,
      resistance = 0x18,
      luck = 0x19,
      constitution = 0x1A,
      rescue = 0x1B,
      movement = 0x1D,

      -- Items (5 slots, each with type and quantity)
      item1_type = 0x1E,
      item1_uses = 0x1F,
      item2_type = 0x20,
      item2_uses = 0x21,
      item3_type = 0x22,
      item3_uses = 0x23,
      item4_type = 0x24,
      item4_uses = 0x25,
      item5_type = 0x26,
      item5_uses = 0x27,

      -- Weapon ranks
      sword_rank = 0x28,
      lance_rank = 0x29,
      axe_rank = 0x2A,
      bow_rank = 0x2B,
      staff_rank = 0x2C,
      anima_rank = 0x2D,
      light_rank = 0x2E,
      dark_rank = 0x2F,

      -- Status effect
      status_effect = 0x30,
      status_turns = 0x31,

      -- Support levels (7 slots)
      support1 = 0x32,
      support2 = 0x33,
      support3 = 0x34,
      support4 = 0x35,
      support5 = 0x36,
      support6 = 0x37,
      support7 = 0x38
    }
  },

  -- Enemy data - address from CodeBreaker codes for first enemy
  enemy = {
    base_addr = 0x0202CEC0,    -- Starting address for first enemy (closest to player)
    size = 0x48,               -- 72 bytes per enemy (same structure as character)
    max_count = 20,            -- Maximum number of enemies to check for

    -- Using the same offsets as player characters
    offsets = {
      character_id = 0x00,
      class_id = 0x04,
      level = 0x08,
      experience = 0x09,
      turn_status = 0x0C,
      hidden_status = 0x0D,
      x_pos = 0x10,
      y_pos = 0x11,
      max_hp = 0x12,
      current_hp = 0x13,
      strength = 0x14,
      skill = 0x15,
      speed = 0x16,
      defense = 0x17,
      resistance = 0x18,
      luck = 0x19,
      constitution = 0x1A,
      rescue = 0x1B,
      movement = 0x1D,

      -- Items (5 slots, each with type and quantity)
      item1_type = 0x1E,
      item1_uses = 0x1F,
      item2_type = 0x20,
      item2_uses = 0x21,
      item3_type = 0x22,
      item3_uses = 0x23,
      item4_type = 0x24,
      item4_uses = 0x25,
      item5_type = 0x26,
      item5_uses = 0x27,

      -- Weapon ranks
      sword_rank = 0x28,
      lance_rank = 0x29,
      axe_rank = 0x2A,
      bow_rank = 0x2B,
      staff_rank = 0x2C,
      anima_rank = 0x2D,
      light_rank = 0x2E,
      dark_rank = 0x2F,

      -- Status effect
      status_effect = 0x30,
      status_turns = 0x31,

      -- Support levels (7 slots)
      support1 = 0x32,
      support2 = 0x33,
      support3 = 0x34,
      support4 = 0x35,
      support5 = 0x36,
      support6 = 0x37,
      support7 = 0x38
    }
  },

  -- Map data - Try different addresses for map size and terrain data
  map_width = 0x0202E4D4,       -- New address to try for map width
  map_height = 0x0202E4D8,      -- New address to try for map height
  map_terrain_start = 0x0202E4DC -- New address to try for terrain data start
}

-- Terrain types and their properties in FE7
-- These are gameplay terrain types that determine movement costs and stats
-- Note: This is different from map IDs which relate to chapter maps and their configuration
local TERRAIN_TYPES = {
  [0x00] = { name = "Plain", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x01] = { name = "Road", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x02] = { name = "Village", def = 0, avo = 10, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x03] = { name = "Armory/Vendor", def = 0, avo = 10, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x04] = { name = "Arena", def = 0, avo = 10, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x05] = { name = "House", def = 0, avo = 10, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x06] = { name = "Fort", def = 1, avo = 20, heal = true, costs = { infantry = 2, cavalry = 2, flier = 1, armor = 2 } },
  [0x07] = { name = "Gate", def = 2, avo = 20, heal = false, costs = { infantry = 2, cavalry = 2, flier = 1, armor = 2 } },
  [0x08] = { name = "Forest", def = 1, avo = 20, heal = false, costs = { infantry = 2, cavalry = 3, flier = 1, armor = 2 } },
  [0x09] = { name = "Thicket", def = 2, avo = 40, heal = false, costs = { infantry = 3, cavalry = 255, flier = 1, armor = 255 } },
  [0x0A] = { name = "Sand", def = 0, avo = 5, heal = false, costs = { infantry = 2, cavalry = 3, flier = 1, armor = 2 } },
  [0x0B] = { name = "Desert", def = 0, avo = 5, heal = false, costs = { infantry = 5, cavalry = 5, flier = 1, armor = 5 } },
  [0x0C] = { name = "River", def = 0, avo = 10, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x0D] = { name = "Mountain", def = 2, avo = 30, heal = false, costs = { infantry = 4, cavalry = 255, flier = 1, armor = 255 } },
  [0x0E] = { name = "Peak", def = 3, avo = 40, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x0F] = { name = "Bridge", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x10] = { name = "Sea", def = 0, avo = 10, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x11] = { name = "Lake", def = 0, avo = 10, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x12] = { name = "Floor", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x13] = { name = "Fence", def = 0, avo = 0, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x14] = { name = "Wall", def = 0, avo = 0, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x15] = { name = "Rubble", def = 0, avo = 10, heal = false, costs = { infantry = 2, cavalry = 2, flier = 1, armor = 2 } },
  [0x16] = { name = "Cliff", def = 0, avo = 0, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x17] = { name = "Ballista", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x18] = { name = "Long Ballista", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x19] = { name = "Killer Ballista", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x1A] = { name = "Door", def = 0, avo = 0, heal = false, costs = { infantry = 255, cavalry = 255, flier = 1, armor = 255 } },
  [0x1B] = { name = "Throne", def = 3, avo = 30, heal = true, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x1C] = { name = "Chest", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x1D] = { name = "Stairs", def = 0, avo = 0, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x1E] = { name = "Altar", def = 3, avo = 30, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } },
  [0x1F] = { name = "Shop", def = 0, avo = 10, heal = false, costs = { infantry = 1, cavalry = 1, flier = 1, armor = 1 } }
}

-- Map data codes - these are different from terrain types
-- These codes relate to chapter maps, palettes, animations and other configuration
-- The list from 0x00 to 0xF2 includes things like "Sacae Plains", "Chapter 1 Map", etc.
local MAP_DATA_CODES = {
  -- This would be the long list you provided, but is not relevant to gameplay mechanics
  -- We're not storing it in the script as it's not needed for the AI agent's decision making
}

-- Helper functions for memory reading
local function read_byte(addr) return memory.readbyte(addr) end
local function read_word(addr) return memory.read_u16_le(addr) end
local function read_dword(addr) return memory.read_u32_le(addr) end

-- Convert weapon rank value to letter rank
local function weapon_rank_letter(val)
  if val == 0 then return "-"       -- weapon disabled
  elseif val >= 0xFB then return "S" -- 0xFB-0xFF = S rank
  elseif val >= 0xB5 then return "A" -- 0xB5-0xFA = A rank
  elseif val >= 0x79 then return "B" -- 0x79-0xB4 = B rank
  elseif val >= 0x47 then return "C" -- 0x47-0x78 = C rank
  elseif val >= 0x1F then return "D" -- 0x1F-0x46 = D rank
  elseif val >= 0x01 then return "E" -- 0x01-0x1E = E rank
  else return "?"                    -- unknown/invalid value
  end
end

-- Convert turn phase value to a readable label
local function turn_phase_label(val)
  if val == 0x00 then return "Player"
  elseif val == 0x40 then return "NPC"
  elseif val == 0x80 then return "Enemy"
  else return string.format("Unknown(0x%02X)", val)
  end
end

-- Read tactician name characters
local function read_tactician_name()
  local name_bytes = {
    read_byte(MEMORY.tactician.char1),
    read_byte(MEMORY.tactician.char2),
    read_byte(MEMORY.tactician.char3),
    read_byte(MEMORY.tactician.char4),
    read_byte(MEMORY.tactician.char5),
    read_byte(MEMORY.tactician.char6),
    read_byte(MEMORY.tactician.char7)
  }

  -- Convert bytes to ASCII and create name string, stopping at first null byte
  local name = ""
  for i, byte in ipairs(name_bytes) do
    if byte == 0 then break end

    -- Handle special Fire Emblem character mappings if needed
    -- This is a basic conversion that assumes ASCII-like encoding
    -- You may need to adjust this for the actual FE7 text encoding
    if byte >= 32 and byte <= 126 then
      name = name .. string.char(byte)
    else
      name = name .. string.format("[%02X]", byte)
    end
  end

  return {
    bytes = name_bytes,
    text = name
  }
end

-- Read character data at the specified slot index
local function read_character(slot_index)
  local base_addr = MEMORY.character.base_addr + (slot_index * MEMORY.character.size)
  local offsets = MEMORY.character.offsets
  local char = {}

  -- Basic stats
  char.character_id = read_byte(base_addr + offsets.character_id)
  char.class_id = read_byte(base_addr + offsets.class_id)
  char.level = read_byte(base_addr + offsets.level)
  char.experience = read_byte(base_addr + offsets.experience)
  char.turn_status = read_byte(base_addr + offsets.turn_status)
  char.hidden_status = read_byte(base_addr + offsets.hidden_status)
  char.x_pos = read_byte(base_addr + offsets.x_pos)
  char.y_pos = read_byte(base_addr + offsets.y_pos)
  char.max_hp = read_byte(base_addr + offsets.max_hp)
  char.current_hp = read_byte(base_addr + offsets.current_hp)
  char.strength = read_byte(base_addr + offsets.strength)
  char.skill = read_byte(base_addr + offsets.skill)
  char.speed = read_byte(base_addr + offsets.speed)
  char.defense = read_byte(base_addr + offsets.defense)
  char.resistance = read_byte(base_addr + offsets.resistance)
  char.luck = read_byte(base_addr + offsets.luck)
  char.constitution = read_byte(base_addr + offsets.constitution)
  char.rescue = read_byte(base_addr + offsets.rescue)
  char.movement = read_byte(base_addr + offsets.movement)

  -- Items
  char.items = {
    { id = read_byte(base_addr + offsets.item1_type), uses = read_byte(base_addr + offsets.item1_uses) },
    { id = read_byte(base_addr + offsets.item2_type), uses = read_byte(base_addr + offsets.item2_uses) },
    { id = read_byte(base_addr + offsets.item3_type), uses = read_byte(base_addr + offsets.item3_uses) },
    { id = read_byte(base_addr + offsets.item4_type), uses = read_byte(base_addr + offsets.item4_uses) },
    { id = read_byte(base_addr + offsets.item5_type), uses = read_byte(base_addr + offsets.item5_uses) }
  }

  -- Weapon ranks
  local sword_val = read_byte(base_addr + offsets.sword_rank)
  local lance_val = read_byte(base_addr + offsets.lance_rank)
  local axe_val = read_byte(base_addr + offsets.axe_rank)
  local bow_val = read_byte(base_addr + offsets.bow_rank)
  local staff_val = read_byte(base_addr + offsets.staff_rank)
  local anima_val = read_byte(base_addr + offsets.anima_rank)
  local light_val = read_byte(base_addr + offsets.light_rank)
  local dark_val = read_byte(base_addr + offsets.dark_rank)

  char.weapon_ranks = {
    sword = sword_val,
    lance = lance_val,
    axe = axe_val,
    bow = bow_val,
    staff = staff_val,
    anima = anima_val,
    light = light_val,
    dark = dark_val
  }

  char.weapon_ranks_display = {
    sword = weapon_rank_letter(sword_val),
    lance = weapon_rank_letter(lance_val),
    axe = weapon_rank_letter(axe_val),
    bow = weapon_rank_letter(bow_val),
    staff = weapon_rank_letter(staff_val),
    anima = weapon_rank_letter(anima_val),
    light = weapon_rank_letter(light_val),
    dark = weapon_rank_letter(dark_val)
  }

  -- Status effect
  char.status_effect = read_byte(base_addr + offsets.status_effect)
  char.status_turns = read_byte(base_addr + offsets.status_turns)

  -- Support data
  char.supports = {
    read_byte(base_addr + offsets.support1),
    read_byte(base_addr + offsets.support2),
    read_byte(base_addr + offsets.support3),
    read_byte(base_addr + offsets.support4),
    read_byte(base_addr + offsets.support5),
    read_byte(base_addr + offsets.support6),
    read_byte(base_addr + offsets.support7)
  }

  return char
end

-- Read enemy data at the specified slot index
local function read_enemy(slot_index)
  local base_addr = MEMORY.enemy.base_addr + (slot_index * MEMORY.enemy.size)
  local offsets = MEMORY.enemy.offsets
  local enemy = {}

  -- Basic stats
  enemy.character_id = read_byte(base_addr + offsets.character_id)
  enemy.class_id = read_byte(base_addr + offsets.class_id)
  enemy.level = read_byte(base_addr + offsets.level)
  enemy.experience = read_byte(base_addr + offsets.experience)
  enemy.turn_status = read_byte(base_addr + offsets.turn_status)
  enemy.hidden_status = read_byte(base_addr + offsets.hidden_status)
  enemy.x_pos = read_byte(base_addr + offsets.x_pos)
  enemy.y_pos = read_byte(base_addr + offsets.y_pos)
  enemy.max_hp = read_byte(base_addr + offsets.max_hp)
  enemy.current_hp = read_byte(base_addr + offsets.current_hp)
  enemy.strength = read_byte(base_addr + offsets.strength)
  enemy.skill = read_byte(base_addr + offsets.skill)
  enemy.speed = read_byte(base_addr + offsets.speed)
  enemy.defense = read_byte(base_addr + offsets.defense)
  enemy.resistance = read_byte(base_addr + offsets.resistance)
  enemy.luck = read_byte(base_addr + offsets.luck)
  enemy.constitution = read_byte(base_addr + offsets.constitution)
  enemy.rescue = read_byte(base_addr + offsets.rescue)
  enemy.movement = read_byte(base_addr + offsets.movement)

  -- Items
  enemy.items = {
    { id = read_byte(base_addr + offsets.item1_type), uses = read_byte(base_addr + offsets.item1_uses) },
    { id = read_byte(base_addr + offsets.item2_type), uses = read_byte(base_addr + offsets.item2_uses) },
    { id = read_byte(base_addr + offsets.item3_type), uses = read_byte(base_addr + offsets.item3_uses) },
    { id = read_byte(base_addr + offsets.item4_type), uses = read_byte(base_addr + offsets.item4_uses) },
    { id = read_byte(base_addr + offsets.item5_type), uses = read_byte(base_addr + offsets.item5_uses) }
  }

  -- Weapon ranks
  local sword_val = read_byte(base_addr + offsets.sword_rank)
  local lance_val = read_byte(base_addr + offsets.lance_rank)
  local axe_val = read_byte(base_addr + offsets.axe_rank)
  local bow_val = read_byte(base_addr + offsets.bow_rank)
  local staff_val = read_byte(base_addr + offsets.staff_rank)
  local anima_val = read_byte(base_addr + offsets.anima_rank)
  local light_val = read_byte(base_addr + offsets.light_rank)
  local dark_val = read_byte(base_addr + offsets.dark_rank)

  enemy.weapon_ranks = {
    sword = sword_val,
    lance = lance_val,
    axe = axe_val,
    bow = bow_val,
    staff = staff_val,
    anima = anima_val,
    light = light_val,
    dark = dark_val
  }

  enemy.weapon_ranks_display = {
    sword = weapon_rank_letter(sword_val),
    lance = weapon_rank_letter(lance_val),
    axe = weapon_rank_letter(axe_val),
    bow = weapon_rank_letter(bow_val),
    staff = weapon_rank_letter(staff_val),
    anima = weapon_rank_letter(anima_val),
    light = weapon_rank_letter(light_val),
    dark = weapon_rank_letter(dark_val)
  }

  -- Status effect
  enemy.status_effect = read_byte(base_addr + offsets.status_effect)
  enemy.status_turns = read_byte(base_addr + offsets.status_turns)

  -- Support data
  enemy.supports = {
    read_byte(base_addr + offsets.support1),
    read_byte(base_addr + offsets.support2),
    read_byte(base_addr + offsets.support3),
    read_byte(base_addr + offsets.support4),
    read_byte(base_addr + offsets.support5),
    read_byte(base_addr + offsets.support6),
    read_byte(base_addr + offsets.support7)
  }

  -- Add the memory address for debugging purposes
  enemy.memory_addr = base_addr

  return enemy
end

-- Read map data with terrain information
local function read_map()
  -- Try to determine map dimensions from player and enemy positions
  -- This is a fallback method if direct memory reading fails
  local function determine_map_size_from_units(units)
    local max_x = 0
    local max_y = 0

    for _, unit in ipairs(units) do
      if unit.x_pos > max_x then max_x = unit.x_pos end
      if unit.y_pos > max_y then max_y = unit.y_pos end
    end

    -- Add some buffer around the max positions found
    return max_x + 5, max_y + 5
  end

  -- Try reading the map dimensions from memory
  local width = read_byte(MEMORY.map_width)
  local height = read_byte(MEMORY.map_height)

  -- Try a second location if the first fails
  if width == 0 or height == 0 or width > 64 or height > 64 then
    width = read_byte(0x0202E4F4) -- Alternative address for width
    height = read_byte(0x0202E4F0) -- Alternative address for height
  end

  -- If still not working, try word (16-bit) reads instead of byte reads
  if width == 0 or height == 0 or width > 64 or height > 64 then
    width = read_word(MEMORY.map_width) & 0xFF -- Try reading as word and mask to byte
    height = read_word(MEMORY.map_height) & 0xFF -- Try reading as word and mask to byte
  end

  local map = { width = width, height = height, terrain = {}, terrain_info = {} }

  -- Debug info
  console.log(string.format("Map dimensions from memory: %d x %d", width, height))

  -- Validate map dimensions
  if width == 0 or height == 0 or width > 64 or height > 64 then
    console.log("WARNING: Invalid map dimensions from memory. Using fixed values.")
    -- Use fixed dimensions as a last resort
    map.width = 15 -- Try a reasonable default size
    map.height = 10
  end

  -- Initialize terrain data with default plains
  for y = 0, map.height - 1 do
    map.terrain[y] = {}
    map.terrain_info[y] = {}
    for x = 0, map.width - 1 do
      map.terrain[y][x] = 0 -- Default to plains
      map.terrain_info[y][x] = get_terrain_info(0) -- Default terrain info for plains
    end
  end

  -- Try to read actual terrain data if dimensions are valid
  if map.width > 0 and map.height > 0 and map.width <= 64 and map.height <= 64 then
    local found_terrain = false

    -- Try several approaches to find valid terrain data
    for _, terrain_addr in ipairs({MEMORY.map_terrain_start, 0x0202E4DC, 0x0202E4FC, 0x0202E500}) do
      local valid_terrain_count = 0
      local total_tiles = 0

      for y = 0, map.height - 1 do
        for x = 0, map.width - 1 do
          total_tiles = total_tiles + 1
          local offset = y * map.width + x
          local terrain_id = read_byte(terrain_addr + offset)

          -- Check if this appears to be valid terrain data
          if terrain_id <= 0x1F then
            valid_terrain_count = valid_terrain_count + 1
          end
        end
      end

      -- If at least 75% of tiles have valid terrain IDs, use this address
      if valid_terrain_count >= (total_tiles * 0.75) then
        console.log(string.format("Found valid terrain data at address: 0x%08X (valid tiles: %d/%d)",
                                  terrain_addr, valid_terrain_count, total_tiles))

        -- Now actually read the terrain data
        for y = 0, map.height - 1 do
          for x = 0, map.width - 1 do
            local offset = y * map.width + x
            local terrain_id = read_byte(terrain_addr + offset)

            -- Ensure terrain ID is valid
            if terrain_id > 0x1F then terrain_id = 0 end

            map.terrain[y][x] = terrain_id
            map.terrain_info[y][x] = get_terrain_info(terrain_id)
          end
        end

        found_terrain = true
        break
      end
    end

    if not found_terrain then
      console.log("WARNING: Could not find valid terrain data. Using default plains.")
    end
  end

  return map
end

-- Get terrain info for a given terrain ID
local function get_terrain_info(terrain_id)
  -- Default terrain info for unknown types
  local default = {
    name = "Unknown",
    def = 0,
    avo = 0,
    heal = false,
    costs = {
      infantry = 255,
      cavalry = 255,
      flier = 1,
      armor = 255
    }
  }

  -- Return the terrain type info from our lookup table, or default if not found
  return TERRAIN_TYPES[terrain_id] or default
end

-- Export the current game state to a file
local function export_game_state()
  local phase_val = read_byte(MEMORY.turn_phase)
  local tactician = read_tactician_name()

  local state = {
    turn_phase = phase_val,
    turn_phase_label = turn_phase_label(phase_val),
    current_turn = read_byte(MEMORY.current_turn),
    chapter_id = read_byte(MEMORY.chapter_id),
    gold = read_word(MEMORY.gold),
    tactician_name = tactician,
    cursor_x = read_byte(MEMORY.cursor_x),
    cursor_y = read_byte(MEMORY.cursor_y),
    camera_x = read_word(MEMORY.camera_x),
    camera_y = read_word(MEMORY.camera_y),
    characters = {},
    enemies = {},
    map_width = read_byte(MEMORY.map_width),
    map_height = read_byte(MEMORY.map_height)
  }

  -- Read character data
  local char_count = 0
  for i = 0, 15 do  -- 16 character slots
    local char = read_character(i)
    if char.character_id ~= 0 then
      table.insert(state.characters, char)
      char_count = char_count + 1
    end
  end

  -- Read enemy data
  local enemy_count = 0
  for i = 0, MEMORY.enemy.max_count - 1 do  -- Check up to 20 enemy slots
    local enemy = read_enemy(i)
    -- Make sure the enemy position is sensible and they have HP
    if enemy.character_id ~= 0 and
       enemy.x_pos < 100 and enemy.y_pos < 100 and  -- Reasonable map positions
       enemy.current_hp > 0 and enemy.max_hp > 0 then
      table.insert(state.enemies, enemy)
      enemy_count = enemy_count + 1
    end
  end

  -- Log to console
  console.clear()
  console.log("Fire Emblem 7 Memory Reader")
  console.log("------------------------")
  console.log(string.format("Tactician: %s (Raw: %02X %02X %02X %02X %02X %02X %02X)",
    tactician.text,
    tactician.bytes[1] or 0,
    tactician.bytes[2] or 0,
    tactician.bytes[3] or 0,
    tactician.bytes[4] or 0,
    tactician.bytes[5] or 0,
    tactician.bytes[6] or 0,
    tactician.bytes[7] or 0))
  console.log(string.format("Turn Phase: %s (0x%02X)", state.turn_phase_label, state.turn_phase))
  console.log(string.format("Current Turn: %d", state.current_turn))
  console.log(string.format("Chapter ID: %d", state.chapter_id))
  console.log(string.format("Gold: %d", state.gold))
  console.log(string.format("Cursor Position: (%d, %d)", state.cursor_x, state.cursor_y))
  console.log(string.format("Camera Position: (%d, %d)", state.camera_x, state.camera_y))
  console.log(string.format("Map Size: %d x %d", state.map_width, state.map_height))
  console.log(string.format("Character Count: %d", char_count))
  console.log(string.format("Enemy Count: %d", enemy_count))

  if char_count > 0 then
    console.log("\nFirst Character:")
    local c = state.characters[1]
    console.log(string.format("CharID: %d, ClassID: %d, Level: %d", c.character_id, c.class_id, c.level))
    console.log(string.format("Position: (%d, %d)", c.x_pos, c.y_pos))
    console.log(string.format("HP: %d/%d, Str: %d, Skl: %d, Spd: %d, Def: %d, Res: %d, Lck: %d",
      c.current_hp, c.max_hp, c.strength, c.skill, c.speed, c.defense, c.resistance, c.luck))
    console.log(string.format("Weapon Ranks: Sword: %s, Lance: %s, Axe: %s, Bow: %s",
      c.weapon_ranks_display.sword, c.weapon_ranks_display.lance,
      c.weapon_ranks_display.axe, c.weapon_ranks_display.bow))
    console.log(string.format("Magic Ranks: Staff: %s, Anima: %s, Light: %s, Dark: %s",
      c.weapon_ranks_display.staff, c.weapon_ranks_display.anima,
      c.weapon_ranks_display.light, c.weapon_ranks_display.dark))
  end

  if enemy_count > 0 then
    console.log("\nFirst Enemy:")
    local e = state.enemies[1]
    console.log(string.format("Address: 0x%08X", e.memory_addr))
    console.log(string.format("CharID: %d, ClassID: %d, Level: %d", e.character_id, e.class_id, e.level))
    console.log(string.format("Position: (%d, %d)", e.x_pos, e.y_pos))
    console.log(string.format("HP: %d/%d, Str: %d, Skl: %d, Spd: %d, Def: %d, Res: %d, Lck: %d",
      e.current_hp, e.max_hp, e.strength, e.skill, e.speed, e.defense, e.resistance, e.luck))
    console.log(string.format("Weapon Ranks: Sword: %s, Lance: %s, Axe: %s, Bow: %s",
      e.weapon_ranks_display.sword, e.weapon_ranks_display.lance,
      e.weapon_ranks_display.axe, e.weapon_ranks_display.bow))
  end

  if enemy_count > 1 then
    console.log("\nSecond Enemy:")
    local e = state.enemies[2]
    console.log(string.format("Address: 0x%08X", e.memory_addr))
    console.log(string.format("CharID: %d, ClassID: %d, Level: %d", e.character_id, e.class_id, e.level))
    console.log(string.format("Position: (%d, %d)", e.x_pos, e.y_pos))
    console.log(string.format("HP: %d/%d", e.current_hp, e.max_hp))
  end

  console.log("\nWriting to: " .. output_file_path)

  -- Write state to file
  local file = io.open(output_file_path, "w")
  if file then
    file:write("GAME_STATE\n")
    file:write(string.format("game_id=FE7\n"))
    file:write(string.format("tactician=%s\n", tactician.text))
    file:write(string.format("tactician_raw=%02X,%02X,%02X,%02X,%02X,%02X,%02X\n",
      tactician.bytes[1] or 0,
      tactician.bytes[2] or 0,
      tactician.bytes[3] or 0,
      tactician.bytes[4] or 0,
      tactician.bytes[5] or 0,
      tactician.bytes[6] or 0,
      tactician.bytes[7] or 0))
    file:write(string.format("turn_phase=%s\n", state.turn_phase_label))
    file:write(string.format("turn_phase_raw=%d\n", state.turn_phase))
    file:write(string.format("current_turn=%d\n", state.current_turn))
    file:write(string.format("chapter_id=%d\n", state.chapter_id))
    file:write(string.format("gold=%d\n", state.gold))
    file:write(string.format("cursor_x=%d\n", state.cursor_x))
    file:write(string.format("cursor_y=%d\n", state.cursor_y))
    file:write(string.format("camera_x=%d\n", state.camera_x))
    file:write(string.format("camera_y=%d\n", state.camera_y))
    file:write(string.format("map_width=%d\n", state.map_width))
    file:write(string.format("map_height=%d\n", state.map_height))

    file:write("CHARACTERS\n")
    for i, char in ipairs(state.characters) do
      file:write(string.format("character=%d\n", i))
      file:write(string.format("  id=%d\n", char.character_id))
      file:write(string.format("  class=%d\n", char.class_id))
      file:write(string.format("  level=%d\n", char.level))
      file:write(string.format("  exp=%d\n", char.experience))
      file:write(string.format("  position=%d,%d\n", char.x_pos, char.y_pos))
      file:write(string.format("  hp=%d,%d\n", char.current_hp, char.max_hp))
      file:write(string.format("  stats=%d,%d,%d,%d,%d,%d\n",
        char.strength, char.skill, char.speed, char.defense, char.resistance, char.luck))

      file:write("  items=")
      for j, item in ipairs(char.items) do
        if item.id > 0 then
          file:write(string.format("%d:%d,", item.id, item.uses))
        end
      end
      file:write("\n")

      file:write(string.format("  ranks=%s,%s,%s,%s,%s,%s,%s,%s\n",
        char.weapon_ranks_display.sword, char.weapon_ranks_display.lance,
        char.weapon_ranks_display.axe, char.weapon_ranks_display.bow,
        char.weapon_ranks_display.staff, char.weapon_ranks_display.anima,
        char.weapon_ranks_display.light, char.weapon_ranks_display.dark))

      file:write(string.format("  ranks_raw=%d,%d,%d,%d,%d,%d,%d,%d\n",
        char.weapon_ranks.sword, char.weapon_ranks.lance,
        char.weapon_ranks.axe, char.weapon_ranks.bow,
        char.weapon_ranks.staff, char.weapon_ranks.anima,
        char.weapon_ranks.light, char.weapon_ranks.dark))
    end

    file:write("ENEMIES\n")
    for i, enemy in ipairs(state.enemies) do
      file:write(string.format("enemy=%d\n", i))
      file:write(string.format("  memory_addr=0x%08X\n", enemy.memory_addr))
      file:write(string.format("  id=%d\n", enemy.character_id))
      file:write(string.format("  class=%d\n", enemy.class_id))
      file:write(string.format("  level=%d\n", enemy.level))
      file:write(string.format("  exp=%d\n", enemy.experience))
      file:write(string.format("  position=%d,%d\n", enemy.x_pos, enemy.y_pos))
      file:write(string.format("  hp=%d,%d\n", enemy.current_hp, enemy.max_hp))
      file:write(string.format("  stats=%d,%d,%d,%d,%d,%d\n",
        enemy.strength, enemy.skill, enemy.speed, enemy.defense, enemy.resistance, enemy.luck))

      file:write("  items=")
      for j, item in ipairs(enemy.items) do
        if item.id > 0 then
          file:write(string.format("%d:%d,", item.id, item.uses))
        end
      end
      file:write("\n")

      file:write(string.format("  ranks=%s,%s,%s,%s,%s,%s,%s,%s\n",
        enemy.weapon_ranks_display.sword, enemy.weapon_ranks_display.lance,
        enemy.weapon_ranks_display.axe, enemy.weapon_ranks_display.bow,
        enemy.weapon_ranks_display.staff, enemy.weapon_ranks_display.anima,
        enemy.weapon_ranks_display.light, enemy.weapon_ranks_display.dark))
    end

    -- Add map terrain data
    local map_data = read_map()
    file:write("MAP\n")
    file:write(string.format("width=%d\n", map_data.width))
    file:write(string.format("height=%d\n", map_data.height))

    -- Write terrain data row by row
    for y = 0, map_data.height - 1 do
      local row = "terrain="
      for x = 0, map_data.width - 1 do
        row = row .. map_data.terrain[y][x] .. ","
      end
      file:write(row .. "\n")
    end

    -- Add terrain information for reference
    file:write("TERRAIN_INFO\n")
    for terrain_id, info in pairs(TERRAIN_TYPES) do
      if terrain_id <= 0x1F then
        file:write(string.format("terrain_type=%d\n", terrain_id))
        file:write(string.format("  name=%s\n", info.name))
        file:write(string.format("  defense=%d\n", info.def))
        file:write(string.format("  avoid=%d\n", info.avo))
        file:write(string.format("  healing=%s\n", info.heal and "true" or "false"))
        file:write("  movement_cost=")
        for unit_type, cost in pairs(info.costs) do
          file:write(string.format("%s:%d,", unit_type, cost))
        end
        file:write("\n")
      end
    end

    file:close()
    console.log("Successfully wrote state to file")
  else
    console.log("ERROR: Failed to open file for writing")
  end

  return state
end

-- Main function that runs every frame
local function main()
  local state = export_game_state()

  -- Display key info on screen
  gui.text(1, 1, "FE7 Memory Reader", "white", "black")
  gui.text(1, 15, string.format("Tactician: %s", state.tactician_name.text), "white", "black")
  gui.text(1, 30, string.format("Turn: %d, Phase: %s", state.current_turn, state.turn_phase_label), "white", "black")
  gui.text(1, 45, string.format("Gold: %d", state.gold), "white", "black")
  gui.text(1, 60, string.format("Chapter: %d", state.chapter_id), "white", "black")
  gui.text(1, 75, string.format("Units: %d | Enemies: %d", #state.characters, #state.enemies), "white", "black")

  -- Show cursor position
  local cursor_x, cursor_y = state.cursor_x, state.cursor_y
  gui.text(1, 90, string.format("Cursor: (%d, %d)", cursor_x, cursor_y), "white", "black")

  -- Draw a marker at cursor position if in range
  if cursor_x >= 0 and cursor_y >= 0 and cursor_x < state.map_width and cursor_y < state.map_height then
    local scale = 16  -- Typical tile size in pixels
    gui.drawBox((cursor_x * scale) + 2, (cursor_y * scale) + 2,
               (cursor_x * scale) + scale - 2, (cursor_y * scale) + scale - 2,
               "red", "clear")
  end

  -- Draw enemy positions
  for i, enemy in ipairs(state.enemies) do
    if enemy.x_pos >= 0 and enemy.y_pos >= 0 and
       enemy.x_pos < state.map_width and enemy.y_pos < state.map_height then
      local scale = 16  -- Typical tile size in pixels

      -- First enemy in red, others in orange
      local color = "red"
      if i > 1 then color = "orange" end

      -- Draw box for enemies
      gui.drawBox((enemy.x_pos * scale) + 4, (enemy.y_pos * scale) + 4,
                 (enemy.x_pos * scale) + scale - 4, (enemy.y_pos * scale) + scale - 4,
                 color, color)

      -- Show enemy HP
      gui.text((enemy.x_pos * scale), (enemy.y_pos * scale),
               string.format("%d", i),
               "yellow", "black")

      -- Show HP for first few enemies
      if i <= 3 then
        gui.text(5, 105 + (i * 15),
                string.format("Enemy %d: HP=%d/%d Pos=(%d,%d) Addr=0x%X",
                i, enemy.current_hp, enemy.max_hp,
                enemy.x_pos, enemy.y_pos, enemy.memory_addr),
                "white", "black")
      end
    end
  end

  -- Add this function before main()
  local function debug_map_terrain()
    local map = read_map()

    console.log("\nMap Terrain Data:")
    console.log(string.format("Dimensions: %d x %d", map.width, map.height))

    -- Print terrain type distribution
    local terrain_counts = {}
    for y = 0, map.height - 1 do
      for x = 0, map.width - 1 do
        local terrain_id = map.terrain[y][x]
        terrain_counts[terrain_id] = (terrain_counts[terrain_id] or 0) + 1
      end
    end

    console.log("\nTerrain Distribution:")
    for terrain_id, count in pairs(terrain_counts) do
      local info = get_terrain_info(terrain_id)
      console.log(string.format("  %s (ID: %d): %d tiles", info.name, terrain_id, count))
    end

    -- Print a small sample of the map
    console.log("\nMap Preview (10x10):")
    for y = 0, math.min(9, map.height - 1) do
      local row = ""
      for x = 0, math.min(9, map.width - 1) do
        local terrain_id = map.terrain[y][x]
        local symbol = ""

        -- Simple ASCII representation of terrain
        if terrain_id == 0x00 then symbol = "." -- Plain
        elseif terrain_id == 0x08 then symbol = "F" -- Forest
        elseif terrain_id == 0x0D then symbol = "^" -- Mountain
        elseif terrain_id == 0x0E then symbol = "^" -- Peak
        elseif terrain_id == 0x0C then symbol = "~" -- River
        elseif terrain_id == 0x10 then symbol = "w" -- Sea
        elseif terrain_id == 0x0F then symbol = "=" -- Bridge
        elseif terrain_id == 0x06 then symbol = "f" -- Fort
        elseif terrain_id == 0x02 then symbol = "v" -- Village
        elseif terrain_id == 0x1A then symbol = "D" -- Door
        elseif terrain_id == 0x14 then symbol = "#" -- Wall
        elseif terrain_id == 0x1B then symbol = "T" -- Throne
        else symbol = string.format("%X", terrain_id) -- Other terrain types
        end

        row = row .. symbol
      end
      console.log("  " .. row)
    end
  end

  -- Call debug_map_terrain() at the end of main()
  debug_map_terrain()
end
print("Fire Emblem 7 Memory Reader loaded!")
print("Output file: " .. output_file_path)
console.log("Fire Emblem 7 Memory Reader loaded!")
console.log("Output file: " .. output_file_path)

-- Register main function to run at the end of each frame
event.onframeend(main)

