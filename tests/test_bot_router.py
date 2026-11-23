"""Unit tests for glyphwerk.bot.router (LiveFlags NPC unblocking + fail-closed script warps)."""
from glyphwerk.bot.router import LiveFlags, ScriptWarp, WorldGraph


def _build_corridor_maps():
    # Single-tile corridor on map (1, 0): (0,0) -> (1,0)[NPC flag 0x05] -> (2,0)
    # Plus second room (2, 0) reachable only via verified script warp
    return {
        (1, 0): ["..."],
        (2, 0): ["..."],
    }


def test_flag_aware_router_unblocks_only_when_live_flag_is_set():
    maps = _build_corridor_maps()
    npc_flags = {(1, 0, 1, 0): [0x0005]}

    # 1. Legacy static mode (flags=None): NPC blocks corridor -> None
    static_g = WorldGraph(maps, npc_flags=npc_flags, flags=None)
    assert static_g.find_path((1, 0, 0, 0), (1, 0, 2, 0)) is None

    # 2. Negative control: live flag 0x0005 is 0 -> still blocked!
    unset_flags = LiveFlags(base_hex="0000")
    blocked_g = WorldGraph(maps, npc_flags=npc_flags, flags=unset_flags)
    assert blocked_g.find_path((1, 0, 0, 0), (1, 0, 2, 0)) is None

    # 3. Positive control: live flag 0x0005 bit set (byte 0 bit 5 = 0x20) -> route opens!
    set_flags = LiveFlags(base_hex="2000")
    open_g = WorldGraph(maps, npc_flags=npc_flags, flags=set_flags)
    path = open_g.find_path((1, 0, 0, 0), (1, 0, 2, 0))
    assert path is not None
    assert [s.direction for s in path] == ["R", "R"]


def test_fail_closed_script_warps_reject_dynamic_0_0_and_open_opcodes():
    maps = _build_corridor_maps()
    # Dynamic 0.0 warp and unproven open-opcode warp MUST be rejected fail-closed
    bad_warps = [
        ScriptWarp(1, 0, 1, 0, 0, 0, 0, 0, proven=True),
        ScriptWarp(1, 0, 2, 0, 2, 0, 0, 0, proven=True, open_opcode_path=True),
    ]
    g_bad = WorldGraph(maps, script_warps=bad_warps)
    assert len(g_bad.rejected_script_warps) == 2
    assert g_bad.find_path((1, 0, 0, 0), (2, 0, 2, 0)) is None

    # Proven static script warp opens path cleanly
    good_warp = ScriptWarp(1, 0, 2, 0, 2, 0, 0, 0, proven=True, open_opcode_path=False)
    g_ok = WorldGraph(maps, script_warps=[good_warp])
    path = g_ok.find_path((1, 0, 0, 0), (2, 0, 2, 0))
    assert path is not None
    assert any(s.kind == "script_warp" for s in path)
