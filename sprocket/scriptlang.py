"""A tiny, safe scripting language for his own designs.

He writes short Python-looking scripts that call ONLY the builder API below. They are never exec()'d or eval()'d:
the script is parsed into an AST and walked by this interpreter, which only understands a whitelist of syntax
(assignments, arithmetic, if, for-in-range, calls to the API). There is no attribute access, no import, no function
definitions, no string formatting, no file/network/OS access of any kind. Hard limits: 3 seconds, 20 000 steps, 160 shapes,
80 loop iterations per loop, bounded coordinates and sizes.  Output is plain data (a list of shapes) that goes through the same
validator as every other design.

API (coordinates are in metres around the building's centre; y is the BOTTOM of a shape):
  box(x,y,z, w,h,d, color, mat)      cylinder(x,y,z, r,h, color)    cone(x,y,z, r,h, color)     sphere(x,y,z, r, color)
  pyramid(x,y,z, w,d,h, color)       prism(x,y,z, w,d,h, color)     (a gable roof: ridge runs along x)     torus(x,y,z, r, color)
  wall(x1,z1,x2,z2, h, color, y, thick)          roof(style, x,y,z, w,d,h, color)    style = gable|hip|flat
  window(x,y,z, face, w, h)   door(x,y,z, face, w, h, color)   floor(x,z, w,d, color, y)   chimney(x,y,z, h, color)
  face is 'n' (-z), 's' (+z), 'e' (+x) or 'w' (-x).   helpers: rnd(a,b) pick(list) sin cos sqrt abs min max round int range
"""
import ast
import inspect
import math
import random
import time

from . import world

MAX_SRC, MAX_STEPS, MAX_SECONDS, MAX_PARTS, MAX_LOOP, MAX_NEST = 3500, 20000, 3.0, 160, 80, 3
MATS = ("matte", "shiny", "metal", "glow", "glass")


class ScriptError(Exception):
    pass


class _Stop(Exception):
    pass


def _c(v, name="color"):
    h = world.to_hex(v)
    if not h:
        raise ScriptError(f"unknown {name} '{str(v)[:20]}': use a name like cream, brick, slate, forest or #rrggbb")
    return h


def _n(v, lo, hi, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise ScriptError(f"{name} must be a number")
    return max(lo, min(hi, float(v)))


class Builder:
    def __init__(self, seed=1):
        self.parts, self.rng = [], random.Random(seed)

    def _add(self, **p):
        if len(self.parts) >= MAX_PARTS:
            raise ScriptError(f"too many shapes (max {MAX_PARTS})")
        p["x"], p["y"], p["z"] = (round(p["x"], 3), round(p["y"], 3), round(p["z"], 3))
        self.parts.append(p)

    def _prim(self, shape, x, y, z, w, h, d, color, mat="matte", rot=0.0):
        x, z, y = _n(x, -12, 12, "x"), _n(z, -12, 12, "z"), _n(y, -1, 12, "y")
        w, h, d = _n(w, 0.05, 12, "width"), _n(h, 0.05, 12, "height"), _n(d, 0.05, 12, "depth")
        mat = mat if mat in MATS else "matte"
        self._add(p=shape, x=x, y=y + h / 2, z=z, w=round(w, 3), h=round(h, 3), d=round(d, 3), c=_c(color), m=mat, r=[0, round(rot, 1), 0])

    # ---- the public API
    def box(self, x, y, z, w, h, d, color="cream", mat="matte"): self._prim("box", x, y, z, w, h, d, color, mat)
    def cylinder(self, x, y, z, r, h, color="stone", mat="matte"): self._prim("cylinder", x, y, z, _n(r, .05, 6, "r") * 2, h, _n(r, .05, 6, "r") * 2, color, mat)
    def cone(self, x, y, z, r, h, color="forest", mat="matte"): self._prim("cone", x, y, z, _n(r, .05, 6, "r") * 2, h, _n(r, .05, 6, "r") * 2, color, mat)
    def sphere(self, x, y, z, r, color="forest", mat="matte"): self._prim("sphere", x, y, z, _n(r, .05, 6, "r") * 2, _n(r, .05, 6, "r") * 2, _n(r, .05, 6, "r") * 2, color, mat)
    def torus(self, x, y, z, r, color="gold", mat="matte"): self._prim("torus", x, y, z, _n(r, .05, 6, "r") * 2, _n(r, .05, 6, "r") * 2, _n(r, .05, 6, "r") * 2, color, mat)
    def pyramid(self, x, y, z, w, d, h, color="terracotta", mat="matte"): self._prim("pyramid", x, y, z, w, h, d, color, mat)
    def prism(self, x, y, z, w, d, h, color="terracotta", mat="matte"): self._prim("prism", x, y, z, w, h, d, color, mat)
    def floor(self, x, z, w, d, color="stone", y=0): self._prim("box", x, y, z, w, 0.12, d, color)

    def wall(self, x1, z1, x2, z2, h, color="cream", y=0, thick=0.2):
        x1, z1, x2, z2 = (_n(v, -12, 12, "coordinate") for v in (x1, z1, x2, z2))
        ln = math.hypot(x2 - x1, z2 - z1)
        if ln < 0.1:
            raise ScriptError("a wall needs two different points")
        self._prim("box", (x1 + x2) / 2, y, (z1 + z2) / 2, ln, h, _n(thick, 0.05, 1, "thickness"), color, rot=math.degrees(math.atan2(-(z2 - z1), x2 - x1)))

    def roof(self, style, x, y, z, w, d, h, color="terracotta"):
        style = str(style).lower()
        if style == "gable": self.prism(x, y, z, w, d, h, color)
        elif style == "hip": self.pyramid(x, y, z, w, d, h, color)
        elif style == "flat": self._prim("box", x, y, z, w, 0.25, d, color)
        else: raise ScriptError("roof style must be gable, hip or flat")

    def _facing(self, face, x, z, depth):
        f = str(face).lower()[:1]
        if f not in "nsew":
            raise ScriptError("face must be 'n', 's', 'e' or 'w'")
        dx, dz, rot = {"n": (0, -1, 0), "s": (0, 1, 0), "e": (1, 0, 90), "w": (-1, 0, 90)}[f]
        return x + dx * depth, z + dz * depth, rot

    def window(self, x, y, z, face, w=0.7, h=0.9):
        w, h = _n(w, .2, 3, "width"), _n(h, .2, 3, "height")
        px, pz, rot = self._facing(face, _n(x, -12, 12, "x"), _n(z, -12, 12, "z"), 0.03)
        self._prim("box", px, y - 0.06, pz, w + 0.14, h + 0.12, 0.06, "ivory", rot=rot)
        px, pz, rot = self._facing(face, x, z, 0.07)
        self._prim("box", px, y, pz, w, h, 0.05, "sky", "glass", rot=rot)

    def door(self, x, y, z, face, w=0.9, h=1.9, color="wood"):
        px, pz, rot = self._facing(face, _n(x, -12, 12, "x"), _n(z, -12, 12, "z"), 0.04)
        self._prim("box", px, y, pz, _n(w, .4, 3, "width"), _n(h, .8, 4, "height"), 0.08, color, rot=rot)

    def chimney(self, x, y, z, h=1.2, color="brick"): self._prim("box", x, y, z, 0.45, h, 0.45, color)


def _helpers(rng):
    return {"rnd": lambda a, b: rng.uniform(float(a), float(b)), "pick": lambda xs: rng.choice(list(xs)),
            "sin": math.sin, "cos": math.cos, "sqrt": lambda v: math.sqrt(max(0, v)), "abs": abs, "min": min, "max": max,
            "round": round, "int": int, "float": float, "len": len, "range": range}


class Interp:
    def __init__(self, seed=1):
        self.b = Builder(seed)
        self.api = {n: getattr(self.b, n) for n in ("box", "cylinder", "cone", "sphere", "torus", "pyramid", "prism", "floor", "wall", "roof", "window", "door", "chimney")}
        self.help = _helpers(self.b.rng)
        self.vars, self.steps, self.t0, self.depth = {"pi": math.pi, "True": True, "False": False}, 0, time.monotonic(), 0

    def tick(self, n):
        self.steps += 1
        if self.steps > MAX_STEPS or (self.steps % 100 == 0 and time.monotonic() - self.t0 > MAX_SECONDS):
            raise ScriptError(f"the script ran too long (limit {MAX_SECONDS:.0f} seconds / {MAX_STEPS} steps)")

    def bad(self, n, what):
        raise ScriptError(f"line {getattr(n, 'lineno', '?')}: {what} is not allowed in design scripts")

    # ---- statements
    def run(self, body):
        for st in body:
            self.stmt(st)

    def stmt(self, n):
        self.tick(n)
        t = type(n)
        if t is ast.Assign:
            if len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name):
                self.bad(n, "this kind of assignment")
            name = n.targets[0].id
            if name in self.api or name in self.help:
                raise ScriptError(f"line {n.lineno}: '{name}' is a builder function; pick another variable name")
            self.vars[name] = self.ev(n.value)
        elif t is ast.AugAssign:
            if not isinstance(n.target, ast.Name) or n.target.id not in self.vars:
                self.bad(n, "this assignment")
            self.vars[n.target.id] = self.binop(n.op, self.vars[n.target.id], self.ev(n.value), n)
        elif t is ast.Expr:
            if isinstance(n.value, ast.Constant):
                return                                                       # a docstring or comment-like string
            if not isinstance(n.value, ast.Call):
                self.bad(n, "this statement")
            self.ev(n.value)
        elif t is ast.For:
            if not isinstance(n.target, ast.Name) or n.orelse:
                self.bad(n, "this kind of loop")
            seq = self.ev(n.iter)
            seq = list(seq) if isinstance(seq, (list, tuple, range)) else self.bad(n, "looping over this")
            if len(seq) > MAX_LOOP:
                raise ScriptError(f"line {n.lineno}: a loop may run at most {MAX_LOOP} times")
            self.depth += 1
            if self.depth > MAX_NEST:
                raise ScriptError(f"line {n.lineno}: loops may be nested at most {MAX_NEST} deep")
            for v in seq:
                self.vars[n.target.id] = v
                self.run(n.body)
            self.depth -= 1
        elif t is ast.If:
            self.run(n.body if self.ev(n.test) else n.orelse)
        elif t is ast.Pass:
            pass
        else:
            self.bad(n, f"'{t.__name__}'")

    # ---- expressions
    def binop(self, op, a, b, n):
        isnum = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        try:
            if isinstance(op, ast.Add):
                r = a + b
            elif isinstance(op, ast.Sub): r = a - b
            elif isinstance(op, ast.Mult):
                if (isinstance(a, (list, str)) or isinstance(b, (list, str))) and not (isnum(a) or isnum(b)):
                    raise ScriptError("cannot multiply those")
                r = a * b
            elif isinstance(op, ast.Div): r = a / b
            elif isinstance(op, ast.FloorDiv): r = a // b
            elif isinstance(op, ast.Mod): r = a % b
            elif isinstance(op, ast.Pow):
                if not (isnum(a) and isnum(b)) or abs(b) > 4 or abs(a) > 1000: raise ScriptError("that power is too big")
                r = a ** b
            else:
                self.bad(n, "this operator")
        except ZeroDivisionError:
            raise ScriptError(f"line {n.lineno}: division by zero")
        except TypeError:
            raise ScriptError(f"line {n.lineno}: those values cannot be combined that way")
        if isinstance(r, (list, str, tuple)) and len(r) > 200:
            raise ScriptError(f"line {n.lineno}: that list or text is too long")
        if isnum(r) and abs(r) > 1e6:
            raise ScriptError(f"line {n.lineno}: a number got too large")
        return r

    def ev(self, n):
        self.tick(n)
        t = type(n)
        if t is ast.Constant:
            if isinstance(n.value, (int, float, str, bool)) or n.value is None:
                return n.value
            self.bad(n, "this kind of value")
        if t is ast.Name:
            if n.id in self.vars: return self.vars[n.id]
            raise ScriptError(f"line {n.lineno}: unknown name '{n.id}'")
        if t is ast.BinOp: return self.binop(n.op, self.ev(n.left), self.ev(n.right), n)
        if t is ast.UnaryOp:
            v = self.ev(n.operand)
            if isinstance(n.op, ast.USub): return -v
            if isinstance(n.op, ast.UAdd): return +v
            if isinstance(n.op, ast.Not): return not v
            self.bad(n, "this operator")
        if t is ast.BoolOp:
            vals = [self.ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if t is ast.Compare:
            left = self.ev(n.left)
            for op, rhs in zip(n.ops, n.comparators):
                right = self.ev(rhs)
                f = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
                     ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}.get(type(op)) or self.bad(n, "this comparison")
                try:
                    if not f(left, right): return False
                except TypeError:
                    raise ScriptError(f"line {n.lineno}: those values cannot be compared")
                left = right
            return True
        if t is ast.IfExp: return self.ev(n.body) if self.ev(n.test) else self.ev(n.orelse)
        if t in (ast.List, ast.Tuple):
            if len(n.elts) > 60: raise ScriptError(f"line {n.lineno}: list too long")
            return [self.ev(e) for e in n.elts]
        if t is ast.Subscript:
            seq, idx = self.ev(n.value), self.ev(n.slice)
            if not isinstance(seq, (list, tuple, str)) or not isinstance(idx, int): self.bad(n, "this index")
            try: return seq[idx]
            except IndexError: raise ScriptError(f"line {n.lineno}: index out of range")
        if t is ast.Call:
            if not isinstance(n.func, ast.Name): self.bad(n, "calling this")
            name = n.func.id
            fn = self.api.get(name) or self.help.get(name)
            if not fn: raise ScriptError(f"line {n.lineno}: unknown function '{name}'. Use only the builder functions (box, wall, roof, window, door...)")
            args = [self.ev(a) for a in n.args]
            kw = {}
            for k in n.keywords:
                if k.arg is None: self.bad(n, "**arguments")
                kw[k.arg] = self.ev(k.value)
            if name == "range" and (len(args) > 3 or any(not isinstance(a, int) for a in args)): raise ScriptError(f"line {n.lineno}: range() needs whole numbers")
            try:
                if name in self.api:
                    inspect.signature(fn).bind(*args, **kw)
                return fn(*args, **kw)
            except TypeError as e:
                raise ScriptError(f"line {n.lineno}: wrong arguments for {name}(...): see the builder API")
            except ScriptError as e:
                raise ScriptError(f"line {n.lineno}: {e}")
            except (ValueError, OverflowError):
                raise ScriptError(f"line {n.lineno}: bad value in {name}(...)")
        self.bad(n, f"'{t.__name__}'")


def run_script(src, seed=1):
    """-> list of primitive parts. Raises ScriptError with a message meant for the model."""
    src = str(src or "").replace("\r", "")
    if len(src) > MAX_SRC:
        raise ScriptError(f"the script is too long (max {MAX_SRC} characters)")
    if not src.strip():
        raise ScriptError("the script is empty")
    try:
        tree = ast.parse(src, mode="exec")
    except SyntaxError as e:
        raise ScriptError(f"syntax error on line {e.lineno}: {str(e.msg)[:60]}")
    except (RecursionError, MemoryError, ValueError):
        raise ScriptError("the script is too complicated to read")
    it = Interp(seed)
    try:
        it.run(tree.body)
    except RecursionError:
        raise ScriptError("the script is too deeply nested")
    if not it.b.parts:
        raise ScriptError("the script made no shapes: call box(...), wall(...), roof(...) and so on")
    return it.b.parts
