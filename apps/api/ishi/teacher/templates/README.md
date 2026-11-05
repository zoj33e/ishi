Template narration (06-teacher-llm): the safety net. Every lesson must be fully readable from these
files alone. One file per concept and locale: `{concept_id}.{th,en}.yaml`, plus `praise` and
`clean`. Fields follow the Narration contract; `new_term` is put first in the explanation when the
learner meets the concept for the first time; `variants` override fields for one variant.

Slots (filled from the FactPackage only): `{played_move}`, `{threat_move}`, `{size}` (stones in the
first group), `{stones}` (after a determiner: "your stone" / "your 3 stones"; Thai "3 เม็ด"), `{a_stones}`, and English agreement slots `{marked}`, `{they}`, `{them}`, `{were}`, `{are}`, `{get}`, `{do}` and every key point by
name (`{last_liberty}`, `{ladder_start}`, ...). Mistake templates never name the correct move before
the retry: the UI shows it as the solution.
