#@cantarellabots
"""
Minimal pure-Python WebAssembly interpreter for the flixcloud embed player.

The /e/ player ships a different randomised WASM binary on every page load
(``r.data.w_payload``). Its ``_r`` function is the only thing the bot needs:
it mixes three 32-byte fragments into a keystroke. The constants inside are
randomised per request, so the binary must be executed, not parsed by hand.

This file implements just enough of the WASM spec to run that module:
no imports, one memory, one global, ``loop``/``block``/``br`` control flow
and the i32 arithmetic / load-store opcodes the module uses. It is a
pragmatic subset, not a full VM - if upstream ever emits a new opcode the
player will raise instead of silently producing garbage.
"""

from __future__ import annotations


def _read_uleb(data: bytes, i: int):
    result = 0
    shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            break
    return result, i


def _read_sleb(data: bytes, i: int):
    result = 0
    shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            if byte & 0x40:
                result -= 1 << shift
            break
    return result, i


_OPNAMES = {
    0x45: "i32.eqz", 0x46: "i32.eq", 0x47: "i32.ne", 0x48: "i32.lt_s",
    0x49: "i32.lt_u", 0x4A: "i32.gt_s", 0x4B: "i32.gt_u", 0x4C: "i32.le_s",
    0x4D: "i32.le_u", 0x4E: "i32.ge_s", 0x4F: "i32.ge_u",
    0x67: "i32.clz", 0x68: "i32.ctz", 0x69: "i32.popcnt", 0x6A: "i32.add",
    0x6B: "i32.sub", 0x6C: "i32.mul", 0x6D: "i32.div_s", 0x6E: "i32.div_u",
    0x6F: "i32.rem_s", 0x70: "i32.rem_u", 0x71: "i32.and", 0x72: "i32.or",
    0x73: "i32.xor", 0x74: "i32.shl", 0x75: "i32.shr_s", 0x76: "i32.shr_u",
    0x77: "i32.rotl", 0x78: "i32.rotr",
}


def _parse_wasm(data: bytes):
    if data[:4] != b"\x00asm":
        raise ValueError("not a wasm module")
    i = 8
    globals_init: list[int] = []
    exports: dict[str, tuple] = {}
    code: list[tuple] = []
    datas: list[tuple] = []
    while i < len(data):
        sec = data[i]
        i += 1
        size, i = _read_uleb(data, i)
        sec_end = i + size
        if sec == 1:  # type
            n, i = _read_uleb(data, i)
            for _ in range(n):
                i += 1  # 0x60
                params, i = _read_uleb(data, i)
                i += params
                results, i = _read_uleb(data, i)
                i += results
        elif sec == 3:  # function
            n, i = _read_uleb(data, i)
            for _ in range(n):
                _, i = _read_uleb(data, i)
        elif sec == 5:  # memory
            n, i = _read_uleb(data, i)
            for _ in range(n):
                flags, i = _read_uleb(data, i)
                _, i = _read_uleb(data, i)
                if flags & 1:
                    _, i = _read_uleb(data, i)
        elif sec == 6:  # global
            n, i = _read_uleb(data, i)
            for _ in range(n):
                i += 2  # type + mutability
                if data[i] != 0x41:
                    raise ValueError("unsupported global init")
                i += 1
                value, i = _read_sleb(data, i)
                i += 1  # 0x0B end
                globals_init.append(value)
        elif sec == 7:  # export
            n, i = _read_uleb(data, i)
            for _ in range(n):
                name_len, i = _read_uleb(data, i)
                name = data[i:i + name_len].decode()
                i += name_len
                kind = data[i]
                i += 1
                index, i = _read_uleb(data, i)
                exports[name] = (kind, index)
        elif sec == 10:  # code
            n, i = _read_uleb(data, i)
            for _ in range(n):
                body_size, i = _read_uleb(data, i)
                body_end = i + body_size
                decl_count, i = _read_uleb(data, i)
                locals_decl: list[int] = []
                for _ in range(decl_count):
                    count, i = _read_uleb(data, i)
                    typ = data[i]
                    i += 1
                    locals_decl.extend([typ] * count)
                instrs: list[tuple] = []
                while i < body_end:
                    op = data[i]
                    i += 1
                    if op == 0x20:
                        v, i = _read_uleb(data, i); instrs.append(("local.get", v))
                    elif op == 0x21:
                        v, i = _read_uleb(data, i); instrs.append(("local.set", v))
                    elif op == 0x22:
                        v, i = _read_uleb(data, i); instrs.append(("local.tee", v))
                    elif op == 0x23:
                        v, i = _read_uleb(data, i); instrs.append(("global.get", v))
                    elif op == 0x24:
                        v, i = _read_uleb(data, i); instrs.append(("global.set", v))
                    elif op == 0x41:
                        v, i = _read_sleb(data, i); instrs.append(("i32.const", v & 0xFFFFFFFF))
                    elif op == 0x02:
                        bt = data[i]; i += 1; instrs.append(("block", bt))
                    elif op == 0x03:
                        bt = data[i]; i += 1; instrs.append(("loop", bt))
                    elif op == 0x04:
                        bt = data[i]; i += 1; instrs.append(("if", bt))
                    elif op == 0x05:
                        instrs.append(("else",))
                    elif op == 0x0B:
                        instrs.append(("end",))
                    elif op == 0x0C:
                        v, i = _read_uleb(data, i); instrs.append(("br", v))
                    elif op == 0x0D:
                        v, i = _read_uleb(data, i); instrs.append(("br_if", v))
                    elif op == 0x0F:
                        instrs.append(("return",))
                    elif op == 0x10:
                        v, i = _read_uleb(data, i); instrs.append(("call", v))
                    elif op == 0x28:
                        _, i = _read_uleb(data, i); off, i = _read_uleb(data, i); instrs.append(("i32.load", off))
                    elif op == 0x2C:
                        _, i = _read_uleb(data, i); off, i = _read_uleb(data, i); instrs.append(("i32.load8_s", off))
                    elif op == 0x2D:
                        _, i = _read_uleb(data, i); off, i = _read_uleb(data, i); instrs.append(("i32.load8_u", off))
                    elif op == 0x36:
                        _, i = _read_uleb(data, i); off, i = _read_uleb(data, i); instrs.append(("i32.store", off))
                    elif op == 0x3A:
                        _, i = _read_uleb(data, i); off, i = _read_uleb(data, i); instrs.append(("i32.store8", off))
                    elif op in _OPNAMES:
                        instrs.append((_OPNAMES[op],))
                    else:
                        raise ValueError(f"unsupported opcode 0x{op:02x}")
                code.append((locals_decl, instrs))
                assert i == body_end, "wasm code body size mismatch"
        elif sec == 11:  # data
            n, i = _read_uleb(data, i)
            for _ in range(n):
                flags, i = _read_uleb(data, i)
                if flags != 0:
                    raise ValueError("unsupported data segment")
                if data[i] != 0x41:
                    raise ValueError("unsupported data offset")
                i += 1
                off, i = _read_sleb(data, i)
                i += 1
                length, i = _read_uleb(data, i)
                datas.append((off, bytes(data[i:i + length])))
                i += length
        else:
            i = sec_end
    return globals_init, exports, code, datas


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


class WasmInstance:
    """Run the tiny flixcloud ``_s`` / ``_r`` / ``_c`` module."""

    def __init__(self, wasm_bytes: bytes):
        self.globals, self.exports, self.code, self.datas = _parse_wasm(wasm_bytes)
        self.memory = bytearray(65536)
        for off, chunk in self.datas:
            self.memory[off:off + len(chunk)] = chunk
        self._match: dict[tuple, int] = {}
        for func_index, (_, instrs) in enumerate(self.code):
            stack: list[int] = []
            for pc, ins in enumerate(instrs):
                if ins[0] in ("block", "loop", "if"):
                    stack.append(pc)
                elif ins[0] == "end" and stack:
                    start = stack.pop()
                    self._match[(func_index, start)] = pc
                    self._match[(func_index, pc)] = start

    def call(self, func_index: int, args: list[int]):
        locals_decl, instrs = self.code[func_index]
        locals_list = [a & 0xFFFFFFFF for a in args] + [0] * len(locals_decl)
        stack: list[int] = []
        control: list[tuple] = []
        pc = 0
        while True:
            if pc < 0 or pc >= len(instrs):
                break
            ins = instrs[pc]
            op = ins[0]
            if op in ("block", "loop", "if"):
                end_pc = self._match[(func_index, pc)]
                if op == "if":
                    if stack.pop():
                        control.append(("if", pc, end_pc))
                        pc += 1
                    else:
                        pc = end_pc + 1
                else:
                    control.append((op, pc, end_pc))
                    pc += 1
            elif op == "else":
                _, _, end_pc = control.pop()
                pc = end_pc + 1
            elif op == "end":
                if control and self._match.get((func_index, pc)) == control[-1][1]:
                    control.pop()
                    pc += 1
                else:
                    break
            elif op == "local.get":
                stack.append(locals_list[ins[1]] & 0xFFFFFFFF); pc += 1
            elif op == "local.set":
                locals_list[ins[1]] = stack.pop() & 0xFFFFFFFF; pc += 1
            elif op == "local.tee":
                locals_list[ins[1]] = stack[-1] & 0xFFFFFFFF; pc += 1
            elif op == "global.get":
                stack.append(self.globals[ins[1]] & 0xFFFFFFFF); pc += 1
            elif op == "global.set":
                self.globals[ins[1]] = stack.pop() & 0xFFFFFFFF; pc += 1
            elif op == "i32.const":
                stack.append(ins[1] & 0xFFFFFFFF); pc += 1
            elif op == "i32.load8_u":
                addr = (stack.pop() + ins[1]) & 0xFFFFFFFF
                stack.append(self.memory[addr]); pc += 1
            elif op == "i32.load8_s":
                addr = (stack.pop() + ins[1]) & 0xFFFFFFFF
                byte = self.memory[addr]
                stack.append((byte - 256 if byte >= 128 else byte) & 0xFFFFFFFF); pc += 1
            elif op == "i32.load":
                addr = (stack.pop() + ins[1]) & 0xFFFFFFFF
                stack.append(int.from_bytes(self.memory[addr:addr + 4], "little")); pc += 1
            elif op == "i32.store8":
                value = stack.pop(); addr = (stack.pop() + ins[1]) & 0xFFFFFFFF
                self.memory[addr] = value & 0xFF; pc += 1
            elif op == "i32.store":
                value = stack.pop(); addr = (stack.pop() + ins[1]) & 0xFFFFFFFF
                self.memory[addr:addr + 4] = int(value).to_bytes(4, "little"); pc += 1
            elif op in ("br", "br_if"):
                if op == "br_if" and not stack.pop():
                    pc += 1
                    continue
                depth = ins[1]
                kind, start_pc, end_pc = control[-1 - depth]
                if kind == "loop":
                    del control[len(control) - depth:]
                    pc = start_pc + 1
                else:
                    del control[len(control) - 1 - depth:]
                    pc = end_pc + 1
            elif op == "return":
                break
            elif op == "call":
                raise NotImplementedError("wasm call inside _s/_r is not supported")
            elif op in ("i32.add", "i32.sub", "i32.mul", "i32.div_s", "i32.div_u",
                        "i32.rem_s", "i32.rem_u", "i32.and", "i32.or", "i32.xor",
                        "i32.shl", "i32.shr_s", "i32.shr_u", "i32.rotl", "i32.rotr"):
                b = stack.pop(); a = stack.pop()
                if op == "i32.add":
                    r = (a + b) & 0xFFFFFFFF
                elif op == "i32.sub":
                    r = (a - b) & 0xFFFFFFFF
                elif op == "i32.mul":
                    r = (a * b) & 0xFFFFFFFF
                elif op == "i32.div_s":
                    sa, sb = _s32(a), _s32(b)
                    r = (int(sa / sb) if sb != 0 else 0) & 0xFFFFFFFF
                elif op == "i32.div_u":
                    r = (a // b) if b != 0 else 0
                elif op == "i32.rem_s":
                    sa, sb = _s32(a), _s32(b)
                    r = ((abs(sa) % abs(sb)) * (1 if sa >= 0 else -1) if sb != 0 else 0) & 0xFFFFFFFF
                elif op == "i32.rem_u":
                    r = (a % b) if b != 0 else 0
                elif op == "i32.and":
                    r = a & b
                elif op == "i32.or":
                    r = a | b
                elif op == "i32.xor":
                    r = a ^ b
                elif op == "i32.shl":
                    r = (a << (b & 31)) & 0xFFFFFFFF
                elif op == "i32.shr_s":
                    r = (_s32(a) >> (b & 31)) & 0xFFFFFFFF
                elif op == "i32.shr_u":
                    r = (a >> (b & 31)) & 0xFFFFFFFF
                elif op == "i32.rotl":
                    s = b & 31
                    r = (((a << s) | (a >> (32 - s) if s else a)) & 0xFFFFFFFF) if s else a
                else:  # rotr
                    s = b & 31
                    r = (((a >> s) | (a << (32 - s) if s else a)) & 0xFFFFFFFF) if s else a
                stack.append(r); pc += 1
            elif op in ("i32.eqz", "i32.eq", "i32.ne", "i32.lt_s", "i32.lt_u",
                        "i32.gt_s", "i32.gt_u", "i32.le_s", "i32.le_u",
                        "i32.ge_s", "i32.ge_u"):
                if op == "i32.eqz":
                    r = 1 if stack.pop() == 0 else 0
                else:
                    b = stack.pop(); a = stack.pop()
                    if op == "i32.eq":
                        r = 1 if a == b else 0
                    elif op == "i32.ne":
                        r = 1 if a != b else 0
                    elif op == "i32.lt_s":
                        r = 1 if _s32(a) < _s32(b) else 0
                    elif op == "i32.lt_u":
                        r = 1 if a < b else 0
                    elif op == "i32.gt_s":
                        r = 1 if _s32(a) > _s32(b) else 0
                    elif op == "i32.gt_u":
                        r = 1 if a > b else 0
                    elif op == "i32.le_s":
                        r = 1 if _s32(a) <= _s32(b) else 0
                    elif op == "i32.le_u":
                        r = 1 if a <= b else 0
                    elif op == "i32.ge_s":
                        r = 1 if _s32(a) >= _s32(b) else 0
                    else:
                        r = 1 if a >= b else 0
                stack.append(r); pc += 1
            elif op in ("i32.clz", "i32.ctz", "i32.popcnt"):
                a = stack.pop()
                if op == "i32.clz":
                    r = 32 if a == 0 else 32 - a.bit_length()
                elif op == "i32.ctz":
                    r = ((a & -a).bit_length() - 1) if a != 0 else 32
                else:
                    r = bin(a).count("1")
                stack.append(r); pc += 1
            else:  # pragma: no cover - parser already limits opcodes
                raise ValueError(f"unhandled opcode {op}")
        return stack[-1] if stack else None

    def call_s(self, seed: int):
        _, index = self.exports["_s"]
        return self.call(index, [seed & 0xFFFFFFFF])

    def call_r(self, p0: int, p1: int, p2: int, p3: int, length: int):
        _, index = self.exports["_r"]
        return self.call(index, [p0, p1, p2, p3, length])

    def call_c(self):
        _, index = self.exports["_c"]
        return self.call(index, [])


def run_wasm_mix(wasm_bytes: bytes, seed_int: int, t: bytes, e: bytes, a: bytes) -> bytes:
    """Execute ``_s(seed)`` + ``_r(t, e, a)`` and return the mixed bytes."""
    instance = WasmInstance(wasm_bytes)
    length = len(t)
    if len(e) < length or len(a) < length:
        raise ValueError("wasm mix inputs must share a length")
    base = 1000
    off1 = base
    off2 = base + length
    off3 = off2 + length
    out = off3 + length
    instance.memory[off1:off1 + length] = t
    instance.memory[off2:off2 + length] = e
    instance.memory[off3:off3 + length] = a
    instance.call_s(seed_int)
    instance.call_r(off1, off2, off3, out, length)
    return bytes(instance.memory[out:out + length])


def run_wasm_pk(wasm_bytes: bytes) -> bytes:
    """Execute ``_c()`` and return the 32-byte playlist XOR key (``__pk``)."""
    instance = WasmInstance(wasm_bytes)
    # ``_c`` only reads the data segment; a fresh instance is enough.
    addr = instance.call_c()
    if addr is None:
        raise ValueError("wasm _c returned nothing")
    return bytes(instance.memory[addr:addr + 32])
