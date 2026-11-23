-- Glyphwerk mGBA Explorer Harness (BPRE standard WRAM layout, profile-configurable)
-- Expected globals injected by runner header:
--   BOT_OUT (directory path ending with /), BOT_FRAMES, BOT_SECONDS,
--   BOT_PLAN (list of step tables from glyphwerk.bot.router),
--   BOT_START (optional savestate path), BOT_BOOT (boolean cold-start macro),
--   BOT_WRAM (optional table overriding default BPRE WRAM addresses).
-- Output: <BOT_OUT>events.tsv + DONE + end.ss0 + end.png

local K = C.GBA_KEY
local DIR_KEY = { U = K.UP, D = K.DOWN, L = K.LEFT, R = K.RIGHT }
local W = BOT_WRAM or {}
local ADDR_SB1_PTR      = W.save_block_1_ptr or 0x03005008
local ADDR_SCRIPT_LOCK  = W.script_lock_byte or 0x03000F9C
local ADDR_MAIN_CB2     = W.main_cb2_ptr     or 0x030030F4
local ADDR_BATTLE_FLAGS = W.battle_flags     or 0x03003529
local ADDR_STR_VAR4     = W.string_var4      or 0x02021D18
local BASE_FLAGS_OFF    = W.base_flags_off   or 0x0EE0
local BASE_FLAGS_SIZE   = W.base_flags_size  or 0x0120
local EXT_FLAGS_ADDR    = W.ext_flags_addr   -- nil on vanilla BPRE
local EXT_FLAGS_SIZE    = W.ext_flags_size   or 0

local f, held, release = 0, nil, 0
local ev = assert(io.open(BOT_OUT .. "events.tsv", "w"))
local function log(...) ev:write(table.concat({...}, "\t"), "\n"); ev:flush() end
local function press(k, n) if held then emu:clearKey(held) end; emu:addKey(k); held = k; release = f + (n or 6) end
local function releaseKey() if held then emu:clearKey(held); held = nil end end

local function hexRange(addr, size)
  if not addr or size <= 0 then return "" end
  local raw = emu:readRange(addr, size)
  local out = {}
  for i = 1, #raw do out[i] = string.format("%02X", raw:byte(i)) end
  return table.concat(out)
end

local function readPos()
  local p = emu:read32(ADDR_SB1_PTR)
  if p < 0x02000000 or p > 0x0203E000 then return nil end
  return emu:read8(p + 4), emu:read8(p + 5), emu:read16(p), emu:read16(p + 2), p
end

local function scriptLocked() return emu:read8(ADDR_SCRIPT_LOCK) ~= 0 end
local function inBattle() return (emu:read8(ADDR_BATTLE_FLAGS) & 2) ~= 0 end

local seenText = {}
local function probeText()
  local raw = emu:readRange(ADDR_STR_VAR4, 300)
  local e = raw:find("\xff", 1, true)
  if not e or e < 6 then return end
  local s = raw:sub(1, e - 1)
  if seenText[s] then return end
  seenText[s] = true
  local h = {}
  for i = 1, #s do h[i] = string.format("%02X", s:byte(i)) end
  log("T", table.concat(h))
end

local ended = false
local function finish(reason)
  if ended then return end
  ended = true
  releaseKey()
  local b, m, x, y = readPos()
  if b then log("P", b, m, x, y) end
  log("E", reason, f)
  emu:saveStateFile(BOT_OUT .. "end.ss0")
  emu:screenshot(BOT_OUT .. "end.png")
  ev:close()
  local d = assert(io.open(BOT_OUT .. "DONE", "w")); d:write(f); d:close()
  emu:pause()
end

if BOT_START then assert(emu:loadStateFile(BOT_START)) end
BOT_PLAN = BOT_PLAN or {}
BOT_SECONDS = BOT_SECONDS or 300

local stepIdx, attempts, stepStart, idle, startTime = 1, 0, 0, 0, os.time()
local fieldCB2, dialogSince, tapCount = nil, nil, 0
local waiting, reqNo, reqTime = false, 0, 0

local function requestPlan(reason)
  local b, m, x, y, p = readPos()
  if not b then return end
  reqNo = reqNo + 1
  local tmp = BOT_OUT .. "req_" .. reqNo .. ".tmp"
  local dst = BOT_OUT .. "req_" .. reqNo .. ".txt"
  local fh = assert(io.open(tmp, "w"))
  fh:write(b, " ", m, " ", x, " ", y, " ", reason, " ", f, "\n")
  fh:write(hexRange(p + BASE_FLAGS_OFF, BASE_FLAGS_SIZE), "\n")
  fh:write(hexRange(EXT_FLAGS_ADDR, EXT_FLAGS_SIZE), "\n")
  fh:close()
  os.rename(tmp, dst)
  waiting, reqTime, stepIdx, attempts, stepStart = true, os.time(), 1, 0, 0
end

callbacks:add("frame", function()
  if ended then return end
  f = f + 1
  if f % 60 == 0 then
    local h = assert(io.open(BOT_OUT .. "heartbeat", "w")); h:write(f); h:close()
  end
  if held and f >= release then releaseKey() end
  if f >= (BOT_FRAMES or 18000) then finish("frames"); return end
  if os.time() - startTime > BOT_SECONDS then finish("timeout"); return end
  local b, m, x, y = readPos()
  if not b or f % 6 ~= 0 then return end

  if inBattle() then
    probeText()
    if f % 12 == 0 then press(K.A, 4) end
    idle = 0
    return
  end

  local cb2 = emu:read32(ADDR_MAIN_CB2)
  local inMenu = (fieldCB2 ~= nil and cb2 ~= fieldCB2)
  if scriptLocked() or inMenu then
    probeText()
    dialogSince = dialogSince or f
    tapCount = tapCount + 1
    if tapCount % 2 == 0 then
      local key = (inMenu and (f - dialogSince) > 240) and K.B or K.A
      press(key, 4)
    end
    idle = 0
    if f - dialogSince > 3600 then finish("dialog_stuck") end
    return
  end

  if fieldCB2 == nil and idle >= 5 then fieldCB2 = cb2 end
  dialogSince = nil
  idle = idle + 1
  if idle < 5 or held then return end

  if waiting then
    local pf = io.open(BOT_OUT .. "plan_" .. reqNo .. ".lua", "r")
    if pf then
      pf:close()
      dofile(BOT_OUT .. "plan_" .. reqNo .. ".lua")
      waiting = false
      if BOT_DONE then finish(BOT_DONE) end
    elseif os.time() - reqTime > 60 then
      finish("plan_timeout")
    end
    return
  end

  local s = BOT_PLAN[stepIdx]
  if not s then requestPlan("plan_complete"); return end
  local db, dm, dx, dy = s.dest[1], s.dest[2], s.dest[3], s.dest[4]
  if b == db and m == dm and x == dx and y == dy then
    stepIdx, attempts, stepStart = stepIdx + 1, 0, 0
    return
  end
  if stepStart == 0 then stepStart = f end
  if f - stepStart > 120 then
    attempts = attempts + 1
    stepStart = f
    if attempts >= 3 then
      log("B", b, m, x, y, s.dir)
      requestPlan("blocked")
      return
    end
  end
  press(DIR_KEY[s.dir], 14)
end)
