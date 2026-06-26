import anthropic

from score import load_games, filter_games, compute_scores

TOP_N = 30
MODEL = "claude-opus-4-8"

SYSTEM = """\
You are helping a gamer decide which Steam games to complete next (get all achievements).
You will receive a list of candidate games ranked by an algorithm that scores ease, size, difficulty, and freshness.
Your job is to pick the best 5-7 games from this list and give a one-line reason for each.

Consider:
- Whether the game is known to have buggy, unobtainable, or grindy achievements
- Whether the game is fun/worth the time vs a chore
- Community health and whether online achievements are still possible
- If the player has already started (Ach % > 0), factor in momentum
- Variety: don't recommend 5 identical genre/length games

Be direct. No fluff. Output a numbered list: game name, then the reason on the same line.
"""


def format_candidates(df) -> str:
    lines = ["#  | Name | Score | Comp hours | Ach% | Playtime | Started"]
    lines.append("-" * 80)
    for i, (_, r) in enumerate(df.iterrows(), 1):
        started = "yes" if r["achievements_pct"] > 0 else "no"
        lines.append(
            f"{i:2}. {r['name']} | {r['score']:.1f} | {r['hltb_completionist_hours']:.1f}h"
            f" | {r['achievements_pct']*100:.0f}% | {r['playtime_hours']:.0f}h played | started={started}"
        )
    return "\n".join(lines)


def main() -> None:
    df = load_games()
    df = filter_games(df)
    df = compute_scores(df)
    candidates = df.nlargest(TOP_N, "score")

    prompt = (
        f"Here are my top {TOP_N} Steam game candidates to complete next, "
        f"ranked by algorithm score:\n\n{format_candidates(candidates)}\n\n"
        "Which 5-7 should I actually focus on? Pick the best ones and explain why briefly."
    )

    client = anthropic.Anthropic()
    print(f"Asking {MODEL} to pick from top {TOP_N} candidates...\n")

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print()


if __name__ == "__main__":
    main()
