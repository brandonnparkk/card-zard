import subprocess
import sys


def test_importing_card_zard_does_not_load_a_web_framework() -> None:
    # A fresh interpreter, so modules imported by other tests don't leak in.
    code = (
        "import sys, card_zard; "
        "print(sorted(m for m in ('fastapi', 'starlette') if m in sys.modules))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "[]"
