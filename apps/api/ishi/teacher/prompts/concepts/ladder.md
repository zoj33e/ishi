## ladder
Variant `ran_into_ladder`: the learner ran (played_move = `escape_move`) with
stones that a working ladder captures; the chase starts at `ladder_start`.
Variant `broken_ladder_chase`: the learner started a ladder
(`atari_move` = played_move) that doesn't work, so the opponent's stones
escape.
Good example (en, ran_into_ladder): "Your 2 stones tried to run with J4. The
opponent can keep putting them in atari in a zig-zag, starting at J3. This is
a ladder, and in the end the stones are captured."
Good example (th): "หมาก 2 เม็ดของเราพยายามหนีด้วย J4 แต่ฝ่ายตรงข้ามไล่อาตาริ
แบบซิกแซกได้ตลอด เริ่มที่ J3 แบบนี้เรียกว่าบันได"
For broken_ladder_chase only say what the package shows: the chase fails
(a stone at `breaker` lets them escape, if the package has it). Don't describe
the path of the chase ("along the edge") and don't ask where a helping stone
should have been: the learner answers by playing a better move in this
position. Question (en): "What would have been a better move?"
(th): "ตรงไหนน่าจะเป็นตาที่ดีกว่า".
