## missed_capture
An opponent group was short of liberties (key point `capture_point`) and the
learner could have captured it, but played elsewhere. groups[0] is the
opponent group; its liberties_before tells how short it was (1 = in atari).
Good example (en): "The opponent's 3 stones marked with triangles had only one
liberty left. One stone on that liberty would have captured them. Instead you
played D7." Question: "Where could you have captured them?"
Good example (th): "หมากฝ่ายตรงข้าม 3 เม็ดที่มีสามเหลี่ยม เหลือลมหายใจแค่ช่องเดียว
ถ้าเราลงปิดช่องสุดท้ายก็กินได้ทันที แต่เราไปลงที่ D7 แทน"
Variant "short": the group had 2 liberties, so no single move captured it.
The answer is an atari that keeps it from getting more liberties; it is
captured on a later move. Never say one stone would capture it right away.
Good example (en, short): "The opponent's 3 stones marked with triangles had only
two liberties. You could have put them in atari and kept chasing until they
had nowhere to run." Question: "Which atari stops them from escaping?"
Good example (th, short): "หมากฝ่ายตรงข้าม 3 เม็ดที่มีสามเหลี่ยม เหลือลมหายใจแค่สองช่อง
เราลงทำให้ติดอาตาริแล้วไล่ต่อจนหนีไม่ได้ก็กินได้ แต่เราไปลงที่ D7 แทน"
