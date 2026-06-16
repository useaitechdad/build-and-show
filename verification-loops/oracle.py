"""Correct reference (oracle) for the mini-SQL task. NEVER placed in the agent's
workdir and NEVER shown to the model -- the grader runs candidate vs this oracle.
Implements exactly the semantics described in sql_spec.SPEC_MD.
"""
import re

DATASET = [
    {"name": "Ann", "dept": "eng",   "salary": 120, "age": 30},
    {"name": "Bob", "dept": "eng",   "salary": 100, "age": 45},
    {"name": "Cy",  "dept": "sales", "salary": 90,  "age": 35},
    {"name": "Dee", "dept": "sales", "salary": 150, "age": 50},
    {"name": "Eve", "dept": "hr",    "salary": 80,  "age": 28},
    {"name": "Fay", "dept": "eng",   "salary": 110, "age": 38},
]

_KW = ("SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "LIMIT", "ASC", "DESC")
_CMP = ("<=", ">=", "!=", "=", "<", ">")


def _split_top(s, sep=","):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


# ---- WHERE: recursive-descent boolean expression over a row ----
def _tok_where(s):
    toks, i = [], 0
    pat = re.compile(r"\s*(<=|>=|!=|=|<|>|\(|\)|'[^']*'|[A-Za-z_]\w*|-?\d+\.?\d*)")
    while i < len(s):
        m = pat.match(s, i)
        if not m:
            i += 1
            continue
        toks.append(m.group(1)); i = m.end()
    return toks


def _eval_where(toks, row):
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def nxt():
        t = toks[pos[0]]; pos[0] += 1; return t

    def operand():
        t = nxt()
        if t.startswith("'"):
            return t[1:-1]
        if re.fullmatch(r"-?\d+\.?\d*", t):
            return float(t) if "." in t else int(t)
        if t in row:
            return row[t]
        raise ValueError(f"unknown column {t}")

    def comparison():
        if peek() == "(":
            nxt(); v = or_expr(); nxt()  # consume ')'
            return v
        left = operand()
        op = nxt()
        right = operand()
        if op == "=":  return left == right
        if op == "!=": return left != right
        if op == "<":  return left < right
        if op == "<=": return left <= right
        if op == ">":  return left > right
        if op == ">=": return left >= right
        raise ValueError(f"bad op {op}")

    def not_expr():
        if peek() and peek().upper() == "NOT":
            nxt(); return not not_expr()
        return comparison()

    def and_expr():
        v = not_expr()
        while peek() and peek().upper() == "AND":
            nxt(); r = not_expr(); v = v and r
        return v

    def or_expr():
        v = and_expr()
        while peek() and peek().upper() == "OR":
            nxt(); r = and_expr(); v = v or r
        return v

    return bool(or_expr())


def _agg(name, col, group):
    vals = [r[col] for r in group] if col != "*" else group
    if name == "COUNT":
        return len(group)
    if name == "SUM":
        return sum(r[col] for r in group)
    if name == "MIN":
        return min(r[col] for r in group)
    if name == "MAX":
        return max(r[col] for r in group)
    if name == "AVG":
        return sum(r[col] for r in group) / len(group)
    raise ValueError(name)


def _parse_agg(item):
    m = re.fullmatch(r"([A-Za-z]+)\(\s*(\*|[A-Za-z_]\w*)\s*\)", item)
    if m and m.group(1).upper() in ("COUNT", "SUM", "MIN", "MAX", "AVG"):
        return m.group(1).upper(), m.group(2)
    return None


def query(sql, rows):
    s = " ".join(sql.strip().split())
    # locate clauses (case-insensitive keywords)
    def find(kw, src):
        m = re.search(r"(?i)\b" + kw + r"\b", src)
        return m.start() if m else -1

    up = s
    i_from = find("FROM", up)
    i_where = find("WHERE", up)
    i_group = find("GROUP", up)
    i_order = find("ORDER", up)
    i_limit = find("LIMIT", up)

    bounds = sorted([b for b in [i_where, i_group, i_order, i_limit, len(s)] if b >= 0])
    sel = s[find("SELECT", up) + 6: i_from].strip()
    sel_items = _split_top(sel)

    def clause(start, kwlen):
        if start < 0:
            return None
        ends = [b for b in [i_where, i_group, i_order, i_limit, len(s)] if b > start]
        return s[start + kwlen: min(ends)].strip()

    where = clause(i_where, 5)
    group = clause(i_group, 5)
    if group:
        group = re.sub(r"(?i)^BY\s+", "", group)
    order = clause(i_order, 5)
    if order:
        order = re.sub(r"(?i)^BY\s+", "", order)
    limit = clause(i_limit, 5)

    # WHERE
    data = rows
    if where:
        toks = _tok_where(where)
        data = [r for r in data if _eval_where(toks, r)]

    aggs = [(_parse_agg(it), it) for it in sel_items]
    has_agg = any(a for a, _ in aggs)

    def apply_order(rowset):
        # stable, multi-key; least-significant key sorted first
        if not order:
            return rowset
        for spec in reversed(_split_top(order)):
            parts = spec.split()
            col = parts[0]
            desc = len(parts) > 1 and parts[1].upper() == "DESC"
            rowset = sorted(rowset, key=lambda r, c=col: r[c], reverse=desc)
        return rowset

    if has_agg or group:
        gcols = _split_top(group) if group else []
        groups = {}
        for r in data:
            key = tuple(r[c] for c in gcols)
            groups.setdefault(key, []).append(r)
        if not gcols and not groups:
            groups = {(): []}
        out = []
        for key, grp in groups.items():
            row = {}
            for (a, it) in aggs:
                if a:
                    row[it] = _agg(a[0], a[1], grp)
                else:
                    row[it] = grp[0][it] if grp else None
            out.append(row)
        data = apply_order(out)            # order by aggregate/group items in SELECT
    else:
        data = apply_order(data)           # order FULL rows (may use non-selected cols)
        if sel_items == ["*"]:
            data = [dict(r) for r in data]
        else:
            data = [{c: r[c] for c in sel_items} for r in data]

    if limit:
        data = data[: int(limit)]
    return data
