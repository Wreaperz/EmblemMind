--[[-
BizHawk Lua bridge for streaming state to the Python agent and receiving
actions. The bridge keeps the socket non-blocking and provides helpers to
speed up simulation while the planner is active.
--]]

local socket = require("socket")
local json = require("json")

local bridge = {
  host = "127.0.0.1",
  port = 17653,
  timeout = 1.0,
  client = nil,
  recv_buffer = "",
  latest_action = nil,
  last_pong = nil,
  turbo_enabled = false,
  turbo_enemy = false,
  savestates = {},
}

local function now()
  return socket.gettime()
end

local function ensure_client()
  if bridge.client then
    return true
  end
  local client, err = socket.tcp()
  if not client then
    return false, err
  end
  client:settimeout(0)
  local ok, connect_err = client:connect(bridge.host, bridge.port)
  if not ok and connect_err ~= "timeout" then
    client:close()
    return false, connect_err
  end
  local start = now()
  while connect_err == "timeout" do
    local writable = socket.select(nil, { client }, 0.05)
    if writable and #writable > 0 then
      ok, connect_err = client:connect(bridge.host, bridge.port)
      if ok or connect_err == "already connected" then
        break
      elseif connect_err ~= "timeout" then
        client:close()
        return false, connect_err
      end
    end
    if now() - start > bridge.timeout then
      client:close()
      return false, "timeout"
    end
  end
  bridge.client = client
  bridge.recv_buffer = ""
  bridge.latest_action = nil
  return true
end

local function encode_line(payload)
  return json.encode(payload) .. "\n"
end

local function send_payload(payload)
  local ok, err = ensure_client()
  if not ok then
    return false, err
  end
  local message = encode_line(payload)
  local total = 0
  while total < #message do
    local sent, send_err, partial = bridge.client:send(message, total + 1)
    if not sent then
      if send_err == "timeout" then
        sent = partial or 0
      else
        return false, send_err
      end
    end
    total = total + sent
  end
  return true
end

local function receive_lines()
  if not bridge.client then
    return
  end
  while true do
    local chunk, err, partial = bridge.client:receive("*l")
    if chunk then
      bridge.recv_buffer = bridge.recv_buffer .. chunk .. "\n"
    elseif err == "timeout" then
      if partial and #partial > 0 then
        bridge.recv_buffer = bridge.recv_buffer .. partial
      end
      break
    elseif err == "closed" then
      bridge.client:close()
      bridge.client = nil
      bridge.recv_buffer = ""
      return
    else
      if partial and #partial > 0 then
        bridge.recv_buffer = bridge.recv_buffer .. partial
      end
      break
    end
  end
  while true do
    local idx = string.find(bridge.recv_buffer, "\n", 1, true)
    if not idx then
      break
    end
    local line = string.sub(bridge.recv_buffer, 1, idx - 1)
    bridge.recv_buffer = string.sub(bridge.recv_buffer, idx + 1)
    if #line > 0 then
      local ok, message = pcall(json.decode, line)
      if ok and type(message) == "table" then
        if message.t == "action" then
          bridge.latest_action = message
        elseif message.t == "pong" then
          bridge.last_pong = message.frame
        end
      end
    end
  end
end

function bridge.send_state(frame, state)
  state.t = "state"
  state.frame = frame
  return send_payload(state)
end

function bridge.poll()
  receive_lines()
  return bridge.latest_action
end

function bridge.clear_action()
  bridge.latest_action = nil
end

function bridge.send_ping(frame)
  return send_payload({ t = "ping", frame = frame })
end

local function set_turbo(enabled)
  if enabled == bridge.turbo_enabled then
    return
  end
  bridge.turbo_enabled = enabled
  if client and client.speedmode then
    if enabled then
      client.speedmode("turbo")
    else
      client.speedmode("normal")
    end
  end
end

function bridge.enable_planning_turbo()
  set_turbo(true)
end

function bridge.disable_planning_turbo()
  set_turbo(false)
end

function bridge.enable_enemy_turbo()
  bridge.turbo_enemy = true
  if client and client.speedmode then
    client.speedmode("turbo")
  end
end

function bridge.disable_enemy_turbo()
  bridge.turbo_enemy = false
  if not bridge.turbo_enabled and client and client.speedmode then
    client.speedmode("normal")
  end
end

function bridge.capture_savestate(slot)
  slot = slot or 1
  local handle = savestate.create(slot)
  savestate.save(handle)
  bridge.savestates[slot] = handle
  return handle
end

function bridge.load_savestate(slot)
  slot = slot or 1
  local handle = bridge.savestates[slot]
  if handle then
    savestate.load(handle)
  end
end

function bridge.list_savestates()
  local slots = {}
  for key, _ in pairs(bridge.savestates) do
    table.insert(slots, key)
  end
  table.sort(slots)
  return slots
end

function bridge.close()
  if bridge.client then
    bridge.client:close()
    bridge.client = nil
  end
  bridge.recv_buffer = ""
end

return bridge
