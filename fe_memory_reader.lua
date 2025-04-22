-- Fire Emblem Memory Reader for BizHawk
-- Targets FE7 GBA Game
-- Uses exact CodeBreaker memory addresses

local output_file_path = "../data/fe_state.txt"
local map_output_file_path = "../data/fe_map.txt"
local write_frequency = 60  -- Write only once every N frames (adjust as needed)
local frame_counter = 0
local last_state_hash = ""  -- Store hash of last written state to avoid redundant writes
local previous_state = {}  -- Cache the previous state
local console_log_frequency = 120  -- Only log to console every N frames (about 2 seconds at 60fps)

-- Fixed settings - no config UI needed for background operation
local enable_console_logging = true
local enable_gui_overlay = false  -- Disabled for background operation
local enable_file_output = true
local enable_map_output = true

-- Constants for map memory locations (EWRAM offsets)
local MAP_WIDTH_ADDR = 0x0202E3D8
local MAP_HEIGHT_ADDR = 0x0202E3DA
local TERRAIN_PTR_TABLE_ADDR = 0x0202E3E0

-- Terrain types with character representation
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
  }
}

-- Helper functions for memory reading
local function read_byte(addr) return memory.readbyte(addr) end
local function read_word(addr) return memory.read_u16_le(addr) end
local function read_dword(addr) return memory.read_u32_le(addr) end
local function read_pointer(address)
  -- Create our own 4-byte reader using readbyte (little endian order)
  local b0 = memory.readbyte(address)
  local b1 = memory.readbyte(address + 1)
  local b2 = memory.readbyte(address + 2)
  local b3 = memory.readbyte(address + 3)

  -- Combine bytes in little-endian format (least significant byte first)
  return b0 + (b1 * 0x100) + (b2 * 0x10000) + (b3 * 0x1000000)
end

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
  char.character_id = read_word(base_addr + offsets.character_id)
  char.class_id = read_word(base_addr + offsets.class_id)
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
  enemy.character_id = read_word(base_addr + offsets.character_id)
  enemy.class_id = read_word(base_addr + offsets.class_id)
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

-- Convert turn status value to readable text
local function turn_status_text(val)
  if val == 0x00 then return "Not moved"
  elseif val == 0x01 then return "Chosen for Level"
  elseif val == 0x0B then return "Not Chosen for Level"
  elseif val == 0x10 then return "Rescuer, not moved"
  elseif val == 0x42 then return "Moved"
  elseif val == 0x52 then return "Rescuer, moved"
  elseif val == 0x21 then return "Rescued"
  else return string.format("Unknown (0x%02X)", val)
  end
end

-- Convert hidden status value to readable text
local function hidden_status_text(val)
  if val == 0x00 then return "None"
  elseif val == 0x10 then return "Special drop bonus"
  elseif val == 0x20 then return "Will drop item"
  elseif val == 0x30 then return "Afa's Drops + Will drop item"
  else return string.format("Unknown (0x%02X)", val)
  end
end

-- Convert status effect value to readable text
local function status_effect_text(val)
  if val == 0 then return "None"
  else
    local turns = math.floor(val / 16)
    local effect = val % 16

    local effect_name = "Unknown"
    if effect == 0 then effect_name = "None"
    elseif effect == 1 then effect_name = "Poison"
    elseif effect == 2 then effect_name = "Sleep"
    elseif effect == 3 then effect_name = "Silence"
    elseif effect == 4 then effect_name = "Berserk"
    elseif effect == 5 then effect_name = "Attack Boost"
    elseif effect == 6 then effect_name = "Defense Boost"
    elseif effect == 7 then effect_name = "Critical Boost"
    elseif effect == 8 then effect_name = "Avoid Boost"
    end

    local turns_text = (turns == 0) and "∞" or tostring(turns)
    return string.format("%s (%s turns)", effect_name, turns_text)
  end
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
    enemies = {}
  }

  -- Read character data
  local char_count = 0
  for i = 0, 49 do  -- Increased from 16 to 50 character slots
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

  -- Generate a simple hash of state to detect changes
  local state_hash = string.format("%d-%d-%d-%d-%d-%d-%d-%d-%d-%d",
    state.turn_phase, state.current_turn, state.chapter_id,
    state.cursor_x, state.cursor_y, char_count, enemy_count,
    state.characters[1] and state.characters[1].current_hp or 0,
    state.enemies[1] and state.enemies[1].current_hp or 0,
    state.enemies[1] and state.enemies[1].x_pos or 0)

  -- Log to console if enabled and only on specified frames to reduce spam
  if enable_console_logging and (frame_counter % console_log_frequency == 0) then
    console.clear()
    console.log("Fire Emblem 7 Memory Reader")
    console.log("------------------------")
    console.log(string.format("Frame: %d | Write Freq: %d | Console Freq: %d",
                frame_counter, write_frequency, console_log_frequency))
    console.log(string.format("Tactician: %s", tactician.text))
    console.log(string.format("Turn Phase: %s (0x%02X)", state.turn_phase_label, state.turn_phase))
    console.log(string.format("Current Turn: %d", state.current_turn))
    console.log(string.format("Chapter ID: %d", state.chapter_id))
    console.log(string.format("Gold: %d", state.gold))
    console.log(string.format("Cursor Position: (%d, %d)", state.cursor_x, state.cursor_y))
    console.log(string.format("Camera Position: (%d, %d)", state.camera_x, state.camera_y))
    console.log(string.format("Character Count: %d", char_count))
    console.log(string.format("Enemy Count: %d", enemy_count))

    if char_count > 0 then
      console.log("\nFirst Character:")
      local c = state.characters[1]
      console.log(string.format("CharID: %d, ClassID: %d, Level: %d", c.character_id, c.class_id, c.level))
      console.log(string.format("Position: (%d, %d)", c.x_pos, c.y_pos))
      console.log(string.format("HP: %d/%d", c.current_hp, c.max_hp))
    end

    if enemy_count > 0 then
      console.log("\nFirst Enemy:")
      local e = state.enemies[1]
      console.log(string.format("CharID: %d, ClassID: %d, Level: %d", e.character_id, e.class_id, e.level))
      console.log(string.format("Position: (%d, %d)", e.x_pos, e.y_pos))
      console.log(string.format("HP: %d/%d", e.current_hp, e.max_hp))
    end
  end

  -- Always write on the first frame to ensure we have a file
  local should_write = enable_file_output and
                      ((frame_counter % write_frequency == 0) or frame_counter == 1) and
                      (state_hash ~= last_state_hash or frame_counter == 1)

  if should_write then
    if enable_console_logging and (frame_counter % console_log_frequency == 0) then
      console.log(string.format("\nWriting to: %s (frame: %d)", output_file_path, frame_counter))
    end

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

      file:write("CHARACTERS\n")
      for i, char in ipairs(state.characters) do
        file:write(string.format("character=%d\n", i))
        file:write(string.format("  id=%d\n", char.character_id))
        file:write(string.format("  class=%d\n", char.class_id))
        file:write(string.format("  level=%d\n", char.level))
        file:write(string.format("  exp=%d\n", char.experience))
        file:write(string.format("  position=%d,%d\n", char.x_pos, char.y_pos))
        file:write(string.format("  hp=%d,%d\n", char.current_hp, char.max_hp))
        file:write(string.format("  stats=%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
          char.strength, char.skill, char.speed, char.luck, char.defense, char.resistance, char.movement, char.constitution, char.rescue))

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

        file:write(string.format("  turn_status=%d\n", char.turn_status))
        file:write(string.format("  turn_status_text=%s\n", turn_status_text(char.turn_status)))
        file:write(string.format("  hidden_status=%d\n", char.hidden_status))
        file:write(string.format("  hidden_status_text=%s\n", hidden_status_text(char.hidden_status)))
        file:write(string.format("  status_effect=%d\n", char.status_effect))
        file:write(string.format("  status_effect_text=%s\n", status_effect_text(char.status_effect)))
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
        file:write(string.format("  stats=%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
          enemy.strength, enemy.skill, enemy.speed, enemy.luck, enemy.defense, enemy.resistance, enemy.movement, enemy.constitution, enemy.rescue))

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

        file:write(string.format("  turn_status=%d\n", enemy.turn_status))
        file:write(string.format("  turn_status_text=%s\n", turn_status_text(enemy.turn_status)))
        file:write(string.format("  hidden_status=%d\n", enemy.hidden_status))
        file:write(string.format("  hidden_status_text=%s\n", hidden_status_text(enemy.hidden_status)))
        file:write(string.format("  status_effect=%d\n", enemy.status_effect))
        file:write(string.format("  status_effect_text=%s\n", status_effect_text(enemy.status_effect)))
      end

      file:close()
      last_state_hash = state_hash

      if enable_console_logging then
        console.log("Successfully wrote state to file")
      end
    else
      if enable_console_logging then
        console.log("ERROR: Failed to open file for writing: " .. output_file_path)
      end
    end
  end

  previous_state.current_turn = state.current_turn
  return state
end

-- Function to get display character for a terrain ID
local function getTerrainChar(terrain_id)
  if terrain_data[terrain_id] then
    return terrain_data[terrain_id].char
  else
    -- Fallback to hex value if terrain type is unknown
    return string.format("%02X", terrain_id)
  end
end

-- Function to build the terrain map and write it to a file
local function buildTerrainMap()

  -- Read map dimensions with safety checks
  local width = read_byte(MAP_WIDTH_ADDR)
  local height = read_byte(MAP_HEIGHT_ADDR)

  -- Verify we have valid dimensions
  if width == 0 or height == 0 or width > 100 or height > 100 then
    if enable_console_logging and (frame_counter % console_log_frequency == 0) then
      console.log(string.format("WARNING: Invalid map dimensions: %dx%d", width, height))
    end
    return nil
  end

  -- Create a map table to hold terrain data
  local map = {}

  -- Get the pointer to the row pointers array (First level of indirection)
  local row_pointers_table = read_pointer(TERRAIN_PTR_TABLE_ADDR)

  -- Verify we have a valid pointer
  if row_pointers_table == 0 or row_pointers_table > 0x10000000 then
    if enable_console_logging and (frame_counter % console_log_frequency == 0) then
      console.log(string.format("WARNING: Invalid row pointers table: 0x%08X", row_pointers_table))
    end
    return nil
  end

  -- Debug info
  local first_row_ptr_addr = row_pointers_table
  local first_row_ptr = read_pointer(first_row_ptr_addr)

  -- Verify first row pointer
  if first_row_ptr == 0 or first_row_ptr > 0x10000000 then
    if enable_console_logging and (frame_counter % console_log_frequency == 0) then
      console.log(string.format("WARNING: Invalid first row pointer: 0x%08X", first_row_ptr))
    end
    return nil
  end

  local first_terrain_id = read_byte(first_row_ptr)

  -- Read the terrain data correctly through two layers of pointers
  for y = 0, height-1 do
    -- Each row pointer is at row_pointers_table + (y * 4)
    local row_ptr_addr = row_pointers_table + (y * 4)

    -- Get the pointer to the actual row of terrain data (Second level of indirection)
    local row_data_ptr = read_pointer(row_ptr_addr)

    -- Verify row pointer
    if row_data_ptr == 0 or row_data_ptr > 0x10000000 then
      if enable_console_logging and (frame_counter % console_log_frequency == 0) then
        console.log(string.format("WARNING: Invalid row data pointer at y=%d: 0x%08X", y, row_data_ptr))
      end
      return nil
    end

    map[y] = {}

    -- Read each terrain ID in the row
    for x = 0, width-1 do
      local terrain_id = read_byte(row_data_ptr + x)
      map[y][x] = terrain_id
    end
  end

  -- Always write on the first frame to ensure we have a file
  local should_write = enable_map_output and
                       ((frame_counter % write_frequency == 0) or frame_counter == 1)

  if should_write then
    -- Open the output file for writing
    local file = io.open(map_output_file_path, "w")
    if file then
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

      -- Write terrain legend
      file:write("\nTerrain Legend:\n")
      file:write(". = Plains, F = Forest, ^ = Hill, M = Mountain/Peak, ~ = Water\n")
      file:write("H = House/Village, C = Castle/Fort, = = Road/Bridge, # = Wall, D = Door/Gate\n")
      file:write("R = Floor/Roof, T = Throne, B = Brace, X = Dark terrain\n")

      -- Close the file
      file:close()

      if enable_console_logging and (frame_counter % console_log_frequency == 0) then
        console.log(string.format("Map data written to %s", map_output_file_path))
      end
    else
      if enable_console_logging and (frame_counter % console_log_frequency == 0) then
        console.log("ERROR: Failed to open map file for writing: " .. map_output_file_path)
      end
    end
  end

  -- Return the map data in case we want to use it elsewhere
  return {width = width, height = height, data = map}
end

-- Main function that runs every frame
local function main()
  frame_counter = frame_counter + 1

  local state = export_game_state()

  -- Also build and export the terrain map
  local map_data = buildTerrainMap()

  -- Display minimal info on screen if GUI overlay is enabled
  if enable_gui_overlay then
    gui.text(1, 1, "FE7 Memory Reader Running", "white", "black")
  end
end

-- Add global error handler to prevent script crashes
local function errorHandler(err)
  console.log("ERROR: " .. tostring(err))
  print("ERROR: " .. tostring(err))
  return err
end

-- Create a wrapped main function with error handling
local function safeMain()
  local status, err = pcall(main)
  if not status then
    errorHandler(err)
  end
end

-- Initial setup
print("Fire Emblem 7 Memory Reader loaded!")
print("State output file: " .. output_file_path)
print("Map output file: " .. map_output_file_path)
print("Write frequency: Every " .. write_frequency .. " frames")
console.log("Fire Emblem 7 Memory Reader loaded!")
console.log("State output file: " .. output_file_path)
console.log("Map output file: " .. map_output_file_path)
console.log("Write frequency: Every " .. write_frequency .. " frames")

-- Register the safe main function to run at the end of each frame
event.onframeend(safeMain)

-- Print confirmation that the script is properly loaded and running
console.log("FE7 Memory Reader is now actively running!")
print("FE7 Memory Reader is now actively running!")

