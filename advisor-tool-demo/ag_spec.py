"""Act 2 task: a hard, plan-sensitive expression evaluator solved over a real
agentic loop. The agent iterates against VISIBLE tests but is graded on HIDDEN
edge-case tests it never sees -- so a weaker model that overfits the visible set
botches the edge cases an up-front plan would have caught.
"""

SPEC_MD = """# Task: expression evaluator

Implement `solution.py` exposing exactly:

    def evaluate(expr: str, variables: dict | None = None):
        # returns a number (int/float) or a bool

## Grammar & semantics
- Integer and float literals; parentheses for grouping.
- Binary arithmetic: `+` `-` `*` `/` `%` with standard precedence
  (`*` `/` `%` bind tighter than `+` `-`). `-` and `/` are LEFT-associative.
- Exponent `**` binds tighter than `*` `/` `%` and is RIGHT-associative:
  `2 ** 3 ** 2` == 512.
- Unary minus binds LOOSER than `**`, so `-2 ** 2` == -4, but `2 ** -1` == 0.5.
- Comparisons `==` `!=` `<` `<=` `>` `>=` return a bool.
- Boolean `and` / `or` (short-circuit) and `not`. `1 == 1 or 1 / 0 == 0` must NOT
  raise (right side short-circuited). Boolean ops bind looser than comparisons.
- Variables resolved from the `variables` dict. Unknown variable ->
  raise ValueError (message containing the variable name).
- Functions: `min`/`max` (2+ args, variadic), `abs`, `pow`, `sqrt` (math.sqrt).
- `/` or `%` by zero -> raise ZeroDivisionError.
- Whitespace is insignificant.

Standard library only. Implement a real parser (do not use eval()).
"""

# (expr, variables, expected)  OR  (expr, variables, {"raises": "ExcName"})
VISIBLE_TESTS = [
    ("1 + 2 * 3", None, 7),
    ("(1 + 2) * 3", None, 9),
    ("2 ** 3", None, 8),
    ("10 / 4", None, 2.5),
    ("10 % 3", None, 1),
    ("x + 1", {"x": 5}, 6),
    ("max(3, 7)", None, 7),
    ("abs(-4)", None, 4),
    ("3 < 5", None, True),
    ("2 == 2 and 3 == 3", None, True),
]

HIDDEN_TESTS = [
    ("2 ** 3 ** 2", None, 512),            # right-assoc exponent
    ("-2 ** 2", None, -4),                 # unary looser than **
    ("2 ** -1", None, 0.5),
    ("-(3 + 4)", None, -7),
    ("1 / 0", None, {"raises": "ZeroDivisionError"}),
    ("5 % 0", None, {"raises": "ZeroDivisionError"}),
    ("y * 2", {}, {"raises": "ValueError"}),   # undefined variable
    ("1 == 1 or 1 / 0 == 0", None, True),      # short-circuit OR
    ("1 == 2 and 1 / 0 == 0", None, False),    # short-circuit AND
    ("not 3 > 5", None, True),
    ("min(4, 2, 8, 1)", None, 1),              # variadic
    ("max(min(3, 9), 2)", None, 3),            # nested
    ("pow(2, 10)", None, 1024),
    ("sqrt(144)", None, 12.0),
    ("3 + 4 * 2 - 6 / 3", None, 9.0),
    ("2 * 3 ** 2", None, 18),                  # ** before *
    ("10 - 2 - 3", None, 5),                   # left-assoc subtraction
    ("2 ** 2 ** 3", None, 256),                # 2**(2**3)
    ("( 1 + 2 ) * ( 3 + 4 )", None, 21),       # whitespace
    ("abs(3 - 10) + abs(-2)", None, 9),
]

# ---- client tools the executor can call ----
TOOLS = [
    {"name": "read_file", "description": "Read a file from the working directory.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a file in the working directory.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "run_tests", "description": "Run the VISIBLE test suite against solution.py. "
                                         "Returns how many passed and details of failures.",
     "input_schema": {"type": "object", "properties": {}}},
]

ADVISOR_TOOL = {"type": "advisor_20260301", "name": "advisor",
                "model": "claude-opus-4-8", "max_tokens": 2048, "max_uses": 2}

BASE_SYSTEM = (
    "You are an expert Python engineer working in a sandboxed working directory. "
    "The task and full spec live in SPEC.md -- read it first. Implement solution.py, "
    "then use run_tests to check it against the visible tests and iterate until they "
    "all pass. The visible tests are a SUBSET; think carefully about edge cases "
    "(associativity, operator precedence, short-circuiting, error semantics) that the "
    "visible tests may not cover. When you are confident the implementation is fully "
    "correct, stop. Use only the standard library in solution.py; do not use eval()."
)

ADVISOR_STEER = (
    "\n\nYou have an `advisor` tool backed by a stronger reviewer model. It takes NO "
    "parameters -- calling advisor() forwards your full conversation (task, every tool "
    "call and result, your reasoning). Call advisor BEFORE substantive work -- after a "
    "little orientation (reading the spec) but BEFORE you commit to a parser design or "
    "write solution.py. Also call it when stuck (tests not converging) and once before "
    "you declare done. Give the advice serious weight.\n"
    "Hard rule: your first write_file must be preceded by an advisor call."
)

ADVISOR_TRIM = (" (Advisor: keep guidance under 120 words -- focus on the parser/"
                "precedence design and the edge cases most likely to bite.)")

INITIAL_USER = "Implement the expression evaluator described in SPEC.md. Start by reading SPEC.md."

CONFIGS = {
    "sonnet_solo": {"label": "Sonnet solo", "model": "claude-sonnet-4-6",
                    "system": BASE_SYSTEM, "use_advisor": False},
    "advisor": {"label": "Sonnet + Opus advisor", "model": "claude-sonnet-4-6",
                "system": BASE_SYSTEM + ADVISOR_STEER, "use_advisor": True},
    "opus_solo": {"label": "Opus solo", "model": "claude-opus-4-8",
                  "system": BASE_SYSTEM, "use_advisor": False},
    "haiku_solo": {"label": "Haiku solo", "model": "claude-haiku-4-5-20251001",
                   "system": BASE_SYSTEM, "use_advisor": False},
    "haiku_advisor": {"label": "Haiku + Opus advisor", "model": "claude-haiku-4-5-20251001",
                      "system": BASE_SYSTEM + ADVISOR_STEER, "use_advisor": True},
}
