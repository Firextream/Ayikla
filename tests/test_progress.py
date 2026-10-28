from types import SimpleNamespace

from ayikla.progress import DecisionPace


def snapshot(pending=10, kept=0, rejected=0):
    return SimpleNamespace(pending=[None] * pending, kept=[None] * kept,
                           rejected=[None] * rejected, total=pending + kept + rejected)


def test_estimate_hidden_until_ten_decisions_and_uses_median():
    now = [0.0]
    pace = DecisionPace(lambda: now[0])
    for i in range(10):
        now[0] += 600 if i == 4 else 2
        pace.record()
        if i < 9:
            assert "min left" not in pace.line(snapshot(30, i + 1), "cull")
    assert pace.line(snapshot(360, 9, 1), "cull") == "Round 1 · 10 / 370 · 9 kept · 1 rejected · ~12 min"


def test_round_two_completion_and_new_session_do_not_show_false_estimates():
    pace = DecisionPace(lambda: 0)
    assert pace.line(snapshot(20, 5, 3), "edit", 2) == "Round 2 · 2 / 5 edit picks"
    pace.record(10)
    assert pace.line(snapshot(0, 10), "cull") == "Round 1 · 10 / 10 · 10 kept · 0 rejected"
    assert "min left" not in DecisionPace().line(snapshot(10, 15), "cull")


def test_burst_frames_are_counted_and_round_switch_resets_interval():
    now = [0.0]
    pace = DecisionPace(lambda: now[0])
    now[0] = 10
    pace.record(5)
    now[0] = 1000
    pace.restart_interval()
    now[0] += 10
    pace.record(5)
    assert pace.samples == [2.0] * 10
    assert pace.remaining(30) == " · ~1 min left"
