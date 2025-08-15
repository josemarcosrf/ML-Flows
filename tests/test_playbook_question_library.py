from collections import OrderedDict

from flows.shrag.playbook import build_question_library


class DummyQuestion:
    def __init__(self, question, question_type, valid_answers=None):
        self.question = question
        self.question_type = question_type
        self.valid_answers = valid_answers or []

    def __eq__(self, other):
        return (
            self.question == other.question
            and self.question_type == other.question_type
            and self.valid_answers == other.valid_answers
        )


def test_build_question_library_preserves_order():
    # Simulate a Playbook.definition as an OrderedDict
    definition = OrderedDict(
        [
            (
                "zero",
                {
                    "group": "",
                    "question": "Q1",
                    "question_type": "yes/no",
                    "valid_answers": ["a"],
                },
            ),
            (
                "first",
                {
                    "group": "g",
                    "question": "Q1",
                    "question_type": "yes/no",
                    "valid_answers": ["a"],
                },
            ),
            (
                "second",
                {
                    "group": "g",
                    "question": "Q2",
                    "question_type": "summarisation",
                    "valid_answers": ["b"],
                },
            ),
            (
                "third",
                {
                    "group": "g",
                    "question": "Q3",
                    "question_type": "summarisation",
                    "valid_answers": ["c"],
                },
            ),
        ]
    )

    result = build_question_library.fn(definition)
    # Handle Prefect State or direct dict
    if hasattr(result, "result"):
        q_collection = result.result()
    else:
        q_collection = result

    print(q_collection)
    assert list(q_collection.keys()) == ["zero", "g"], (
        f"Order of keys is not preserved: {q_collection.keys()}"
    )
    assert [q.key for q in q_collection["g"]] == ["first", "second", "third"], (
        f"Order of questions in group 'g' is not preserved: {[q.key for q in q_collection['g']]}"
    )
