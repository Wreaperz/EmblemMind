-- Fire Emblem Memory Reader for BizHawk
-- Targets FE7 GBA Game
-- Uses exact CodeBreaker memory addresses

local output_file_path = "../agent/data/fe_state.txt"
local write_frequency = 60  -- Write only once every N frames (adjust as needed)
local frame_counter = 0
local last_state_hash = ""  -- Store hash of last written state to avoid redundant writes
local previous_state = {}  -- Cache the previous state
local console_log_frequency = 120  -- Only log to console every N frames (about 2 seconds at 60fps)

-- Configuration options
local CONFIG = {
  enable_console_logging = true,  -- Set to false to disable console logs
  enable_gui_overlay = true,      -- Set to false to disable on-screen display
  enable_file_output = true,      -- Set to false to completely disable file writing
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

  -- Generate a simple hash of state to detect changes
  local state_hash = string.format("%d-%d-%d-%d-%d-%d-%d-%d-%d-%d",
    state.turn_phase, state.current_turn, state.chapter_id,
    state.cursor_x, state.cursor_y, char_count, enemy_count,
    state.characters[1] and state.characters[1].current_hp or 0,
    state.enemies[1] and state.enemies[1].current_hp or 0,
    state.enemies[1] and state.enemies[1].x_pos or 0)

  -- Log to console if enabled and only on specified frames to reduce spam
  if CONFIG.enable_console_logging and (frame_counter % console_log_frequency == 0) then
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

  -- Only write to file if enabled, on appropriate frames, and if data has changed
  local should_write = CONFIG.enable_file_output and
                      (frame_counter % write_frequency == 0) and
                      (state_hash ~= last_state_hash)

  if should_write then
    if CONFIG.enable_console_logging and (frame_counter % console_log_frequency == 0) then
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

      file:close()
      last_state_hash = state_hash

      if CONFIG.enable_console_logging and (frame_counter % console_log_frequency == 0) then
        console.log("Successfully wrote state to file")
      end
    else
      if CONFIG.enable_console_logging and (frame_counter % console_log_frequency == 0) then
        console.log("ERROR: Failed to open file for writing")
      end
    end
  end

  previous_state.current_turn = state.current_turn
  return state
end

-- Main function that runs every frame
local function main()
  frame_counter = frame_counter + 1

  local state = export_game_state()

  -- Display key info on screen
  if CONFIG.enable_gui_overlay then
    gui.text(1, 1, "FE7 Memory Reader", "white", "black")
    gui.text(1, 15, string.format("Tactician: %s", state.tactician_name.text), "white", "black")
    gui.text(1, 30, string.format("Turn: %d, Phase: %s", state.current_turn, state.turn_phase_label), "white", "black")
    gui.text(1, 45, string.format("Gold: %d", state.gold), "white", "black")
    gui.text(1, 60, string.format("Chapter: %d", state.chapter_id), "white", "black")
    gui.text(1, 75, string.format("Units: %d | Enemies: %d", #state.characters, #state.enemies), "white", "black")

    -- Show cursor position
    local cursor_x, cursor_y = state.cursor_x, state.cursor_y
    gui.text(1, 90, string.format("Cursor: (%d, %d)", cursor_x, cursor_y), "white", "black")

    -- Show write frequency and last write frame
    gui.text(1, 105, string.format("Frame: %d | Write: %d | Log: %d",
             frame_counter, write_frequency, console_log_frequency), "white", "black")
  end
end

-- Configuration menu for runtime adjustment
local function create_config_menu()
  -- Add menu items to allow user to adjust settings at runtime
  forms.destroyall()
  local form = forms.newform(300, 280, "FE7 Memory Reader Config")

  -- File writing frequency
  forms.label(form, "File Write Frequency (frames):", 10, 10, 150, 20)
  local freq_track = forms.trackbar(form, 15, 10, 35, 150, 15, 1, 60)

  -- Configuration checkboxes
  local console_check = forms.checkbox(form, "Enable Console Logging", 10, 70)
  forms.setproperty(console_check, "Checked", CONFIG.enable_console_logging)

  local gui_check = forms.checkbox(form, "Enable GUI Overlay", 10, 100)
  forms.setproperty(gui_check, "Checked", CONFIG.enable_gui_overlay)

  local file_check = forms.checkbox(form, "Enable File Output", 10, 130)
  forms.setproperty(file_check, "Checked", CONFIG.enable_file_output)

  -- Apply button
  local apply_button = forms.button(form, "Apply Settings",
    function()
      write_frequency = forms.getproperty(freq_track, "Value")
      CONFIG.enable_console_logging = forms.getproperty(console_check, "Checked")
      CONFIG.enable_gui_overlay = forms.getproperty(gui_check, "Checked")
      CONFIG.enable_file_output = forms.getproperty(file_check, "Checked")

      console.log(string.format("Settings updated: Write freq=%d, Console=%s, GUI=%s, File=%s",
        write_frequency,
        CONFIG.enable_console_logging and "ON" or "OFF",
        CONFIG.enable_gui_overlay and "ON" or "OFF",
        CONFIG.enable_file_output and "ON" or "OFF"))
    end,
    100, 200)
end

print("Fire Emblem 7 Memory Reader loaded!")
print("Output file: " .. output_file_path)
print("Write frequency: Every " .. write_frequency .. " frames")
print("Console log frequency: Every " .. console_log_frequency .. " frames")
console.log("Fire Emblem 7 Memory Reader loaded!")
console.log("Output file: " .. output_file_path)
console.log("Write frequency: Every " .. write_frequency .. " frames")
console.log("Console log frequency: Every " .. console_log_frequency .. " frames")

-- Register main function to run at the end of each frame
event.onframeend(main)

-- Print confirmation that the script is properly loaded and running
console.log("FE7 Memory Reader is now actively running!")
print("FE7 Memory Reader is now actively running!")
print("Press F1 to open configuration menu")
console.log("Press F1 to open configuration menu")

