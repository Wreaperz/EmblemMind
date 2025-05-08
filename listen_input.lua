-- EmblemMind/input_listener.lua
local input_file = "data/emblemmind_input.txt"

function read_action()
    local f = io.open(input_file, "r")
    if not f then return nil end
    local line = f:read("*l")
    f:close()
    os.remove(input_file)
    return line
end

while true do
    local action = read_action()
    if action == "UP" then
        joypad.set({ Up = true })
    elseif action == "DOWN" then
        joypad.set({ Down = true })
    elseif action == "RIGHT" then
        joypad.set({ Right = true })
    elseif action == "LEFT" then
        joypad.set({ Left = true })
    end
    emu.frameadvance()
end
