"""Override-conflict UI (D18): pick the winner when extensions collide.

tkinter-based; the dialog only opens when the user invokes it from the app.
The *policy* (who wins, what is saved) lives in ``extensions.py`` and is
headless-testable; this module is only the interface. Importing it opens no
window (pinned by ``tests/regress_override_persistence.py``).
"""
import tkinter as tk


def pick_override_winners(root, conflicts):
    """Open the override-conflict dialog; return the winner selection.

    ``conflicts`` is ``{base_id: [ext_id, ...]}`` (see
    ``ExtensionManager.override_conflicts``). Returns ``{base_id: ext_id}``
    for the user's choices, or ``{}`` when the dialog is cancelled.
    """
    if not conflicts:
        return {}
    top = tk.Toplevel(root)
    top.title("Extension conflicts")
    top.transient(root)
    top.resizable(False, False)

    frame = tk.Frame(top, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="These extensions override the same provider. "
             "Pick the winner for each.").grid(
                 row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    choices = {}
    row = 1
    for base, exts in sorted(conflicts.items()):
        tk.Label(frame, text=base).grid(row=row, column=0, sticky="w")
        var = tk.StringVar(value=exts[0])
        choices[base] = var
        for ext in exts:
            tk.Radiobutton(frame, text=ext, variable=var,
                           value=ext).grid(row=row, column=1, sticky="w")
        row += 1

    done = []

    def _ok():
        done.append({b: v.get() for b, v in choices.items()})
        top.destroy()

    def _cancel():
        top.destroy()

    btns = tk.Frame(frame)
    btns.grid(row=row, column=0, columnspan=2, pady=(12, 0), sticky="e")
    tk.Button(btns, text="OK", width=10, command=_ok).pack(side="left", padx=4)
    tk.Button(btns, text="Cancel", width=10,
              command=_cancel).pack(side="left")

    top.grab_set()
    top.wait_window()
    return done[0] if done else {}
