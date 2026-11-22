from __future__ import annotations

from forge.core.models import PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.puzzles.pigpen import Pigpen, code_of, decode


def test_every_letter_has_its_own_symbol_and_decodes() -> None:
    az = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    codes = [code_of(c) for c in az]
    assert len(set(codes)) == 26
    assert decode(codes) == az


def test_message_carries_the_keyword() -> None:
    pg = Pigpen()
    spec = PuzzleSpec.model_validate(
        {
            "type": "pigpen",
            "level": "easy",
            "audience": "adult",
            "constraints": [{"kind": "answer_is", "word": "CRIMSON"}],
            "options": {"text": "The thread was crimson wool"},
        }
    )
    pz = pg.generate(spec, 1)
    assert pz.verify is not None and pz.verify.ok
    assert pg.solve(pz).solution["text"] == "THE THREAD WAS CRIMSON WOOL"
    r = pg.render(pz, RenderCtx(width_in=6, height_in=8))
    assert any(k.endswith(".svg") for k in r.files) and r.files["img/pigpen-key.svg"].startswith(
        b"<svg"
    )
