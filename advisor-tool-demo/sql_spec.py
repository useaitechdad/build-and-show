"""Act 2 (extensive) task: a from-scratch mini-SQL query engine. Graded by
comparing the candidate against a correct reference oracle (sql_ref.py) the model
never sees. Visible SQL drives the agent's run_tests loop; hidden SQL is the grade.
"""
from sql_ref import DATASET

SPEC_MD = """# Task: mini-SQL query engine

Implement `solution.py` exposing exactly:

    def query(sql: str, rows: list[dict]) -> list[dict]:
        # run the SQL-like query against `rows` (a list of dicts) and return the
        # result as a list of dicts.

You will be tested against data shaped like this (columns: name[str], dept[str],
salary[int], age[int]):

    [{"name":"Ann","dept":"eng","salary":120,"age":30}, ... 6 rows ...]

## Supported syntax (keywords are CASE-INSENSITIVE)
`SELECT <items> FROM <table> [WHERE <cond>] [GROUP BY <cols>] [ORDER BY <cols>] [LIMIT <n>]`

- **SELECT**: `*` (all columns, original order) OR a comma list of column names
  and/or aggregate calls. The `FROM <table>` name is ignored — always query `rows`.
- **Output keys**: each result dict's keys are the SELECT items written EXACTLY as
  given. `SELECT dept, COUNT(*)` → keys `"dept"` and `"COUNT(*)"`. `SELECT *` → all
  original columns.
- **WHERE**: comparisons `=` `!=` `<` `<=` `>` `>=` (note single `=` for equality);
  boolean `AND` `OR` `NOT` and parentheses. Precedence: `NOT` > `AND` > `OR`.
  Operands are column names, integer literals, or single-quoted strings (`'eng'`).
- **Aggregates**: `COUNT(*)`, `SUM(col)`, `AVG(col)`, `MIN(col)`, `MAX(col)`.
  `AVG` returns a float; `SUM`/`COUNT` return ints.
- **GROUP BY <cols>**: one output row per group; group order = first appearance in
  `rows`. Without GROUP BY but with an aggregate, the whole table is one group.
- **ORDER BY**: comma list of `col [ASC|DESC]` (default ASC); multi-key, stable.
  May order by an aggregate item present in SELECT (e.g. `ORDER BY MAX(salary) DESC`).
- **LIMIT n**: keep the first n rows (after ORDER BY).

Standard library only. Write a real parser; do not use eval() or sqlite3.
"""

INITIAL_USER = "Implement the mini-SQL query engine described in SPEC.md. Start by reading SPEC.md."

VISIBLE_SQL = [
    "SELECT * FROM data",
    "SELECT name, salary FROM data",
    "SELECT name FROM data WHERE dept = 'eng'",
    "SELECT name FROM data WHERE salary > 100",
    "SELECT name FROM data ORDER BY salary",
    "SELECT name FROM data ORDER BY salary DESC",
    "SELECT name FROM data LIMIT 2",
    "SELECT COUNT(*) FROM data",
    "SELECT dept, COUNT(*) FROM data GROUP BY dept",
    "SELECT SUM(salary) FROM data",
]

HIDDEN_SQL = [
    "SELECT name FROM data WHERE dept = 'eng' AND salary > 100",
    "SELECT name FROM data WHERE dept = 'eng' OR dept = 'hr'",
    "SELECT name FROM data WHERE dept = 'eng' AND salary > 100 OR dept = 'hr'",
    "SELECT name FROM data WHERE dept = 'eng' AND (salary > 100 OR age > 40)",
    "SELECT name FROM data WHERE NOT dept = 'eng'",
    "SELECT name FROM data WHERE salary >= 100 AND salary <= 120",
    "SELECT name, salary FROM data ORDER BY dept ASC, salary DESC",
    "SELECT dept, COUNT(*), AVG(salary) FROM data GROUP BY dept",
    "SELECT dept, MAX(salary) FROM data GROUP BY dept ORDER BY MAX(salary) DESC",
    "SELECT dept, MIN(age) FROM data GROUP BY dept",
    "SELECT name FROM data WHERE age > 30 AND age < 45 ORDER BY age",
    "select name from data where dept = 'sales'",
    "SELECT * FROM data WHERE dept = 'eng' ORDER BY salary DESC LIMIT 2",
    "SELECT COUNT(*) FROM data WHERE salary > 100",
    "SELECT dept, SUM(salary) FROM data GROUP BY dept ORDER BY SUM(salary)",
    "SELECT name FROM data ORDER BY age DESC LIMIT 3",
]
