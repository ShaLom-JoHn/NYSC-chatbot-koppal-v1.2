"""Executes koppal_intent_classifier.ipynb and writes the outputs back into the file.

This is what `jupyter nbconvert --execute --inplace` would do. It is hand rolled because
nbconvert is not installable in this environment, and because the notebook is the graded
deliverable: it has to be committed WITH its outputs, or a reader on GitHub sees code and no
results.

What it captures per code cell, in the order Jupyter would show them:

  stdout          -> a `stream` output
  matplotlib      -> a `display_data` output with the figure as base64 PNG
  last expression -> an `execute_result`, with both text/plain and text/html so a DataFrame
                     renders as a table rather than as its repr

The last-expression handling is the only fiddly part. Jupyter shows the value of a trailing
expression; a plain `exec` discards it. So the cell is parsed, and if its final statement is an
expression it is split off, evaluated separately, and formatted.

Run: python _execute_notebook.py
"""
import ast
import base64
import io
import json
import sys
import warnings
from contextlib import redirect_stdout

import matplotlib
matplotlib.use("Agg")                 # render figures to memory, never to a window
import matplotlib.pyplot as plt       # noqa: E402

warnings.filterwarnings("ignore")     # a clean notebook, the warnings are all convergence noise

NOTEBOOK = "koppal_intent_classifier.ipynb"


def figures():
    """Every open matplotlib figure as a base64 PNG, then closed."""
    out = []
    for num in plt.get_fignums():
        buffer = io.BytesIO()
        plt.figure(num).savefig(buffer, format="png", dpi=110, bbox_inches="tight")
        out.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    plt.close("all")
    return out


def formatted(value):
    """(text/plain, text/html or None) for a trailing expression's value."""
    try:
        import pandas as pd
        if isinstance(value, (pd.DataFrame, pd.Series)):
            return value.to_string(), value.to_frame().to_html() if isinstance(value, pd.Series) \
                else value.to_html()
    except ImportError:
        pass
    return repr(value), None


def run():
    with open(NOTEBOOK, encoding="utf-8") as f:
        nb = json.load(f)

    env = {"__name__": "__main__"}
    count = 0

    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue

        count += 1
        source = "".join(line for line in cell["source"] if not line.strip().startswith("%"))
        outputs = []
        buffer = io.StringIO()

        try:
            tree = ast.parse(source)
            tail = None
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                tail = ast.Expression(tree.body.pop().value)

            with redirect_stdout(buffer):
                if tree.body:
                    exec(compile(tree, "<cell %d>" % count, "exec"), env)
                value = eval(compile(tail, "<cell %d>" % count, "eval"), env) if tail else None
        except Exception as error:
            print("\nCELL %d FAILED: %s: %s" % (count, type(error).__name__, error))
            print("-" * 70)
            print(source)
            sys.exit(1)

        printed = buffer.getvalue()
        if printed:
            outputs.append({"output_type": "stream", "name": "stdout",
                            "text": printed.splitlines(keepends=True)})

        for png in figures():
            outputs.append({"output_type": "display_data", "metadata": {},
                            "data": {"image/png": png, "text/plain": ["<Figure>"]}})

        if tail is not None and value is not None:
            plain, html = formatted(value)
            data = {"text/plain": plain.splitlines(keepends=True)}
            if html:
                data["text/html"] = html.splitlines(keepends=True)
            outputs.append({"output_type": "execute_result", "execution_count": count,
                            "metadata": {}, "data": data})

        cell["outputs"] = outputs
        cell["execution_count"] = count
        nb["cells"][index] = cell
        print("cell %2d executed, %d output(s)" % (count, len(outputs)))

    with open(NOTEBOOK, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")

    with_output = sum(1 for c in nb["cells"] if c["cell_type"] == "code" and c["outputs"])
    print()
    print("wrote %s" % NOTEBOOK)
    print("  %d code cells executed, %d carry output" % (count, with_output))


if __name__ == "__main__":
    run()
