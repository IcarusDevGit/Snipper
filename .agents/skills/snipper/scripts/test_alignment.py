import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from alignment import find_snippet_in_text, resolve_paragraph_styling
from nlp import LemmaMatch


def test_normalized_snippet_search():
    # Target text has smart quotes and non-breaking space
    target = 'The CEO said, “Innovation\u00a0is paramount.”'
    # Finding query has straight quotes and regular space
    snippet = 'The CEO said, "Innovation is paramount."'
    
    pos = find_snippet_in_text(snippet, target)
    assert pos is not None
    start, end = pos
    assert target[start:end] == target


def test_nested_snippet_styling():
    # Raw sentence
    # "In 1995, the initiative was established in Boston by John Doe."
    # Q1 (Yellow): Outer sentence (0 to 60)
    # Q2 (Cyan): Inner phrase "established in Boston" (25 to 46)
    # Match: "John Doe" (50 to 58)
    text = "In 1995, the initiative was established in Boston by John Doe."
    
    match = LemmaMatch(
        paragraph_idx=0,
        start_char=50,
        end_char=58,
        text="John Doe",
        lemma="john doe",
        question_ids=[1],
        color="#FFFF00",
    )
    
    snippet_q1 = (0, len(text), [1], "#FFFF00")  # Yellow
    snippet_q2 = (25, 46, [2], "#00FFFF")        # Cyan (Shorter inner span)

    slices = resolve_paragraph_styling(
        paragraph_text=text,
        paragraph_idx=0,
        lemma_matches=[match],
        snippet_spans=[snippet_q1, snippet_q2],
    )

    # Check inner span (25 to 46) has Cyan (#00FFFF) and superscript for Q2 ('²')
    inner_slice = next((s for s in slices if s[0] == 25), None)
    assert inner_slice is not None
    assert inner_slice[2] == "#00FFFF"
    assert "²" in inner_slice[4]

    # Check "John Doe" match (50 to 58) is bolded!
    match_slice = next((s for s in slices if s[0] == 50), None)
    assert match_slice is not None
    assert match_slice[3] is True  # bold = True
    assert match_slice[2] == "#FFFF00"  # takes enclosing snippet color


if __name__ == "__main__":
    test_normalized_snippet_search()
    test_nested_snippet_styling()
    print("Alignment tests passed!")
