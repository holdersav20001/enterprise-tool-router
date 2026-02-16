from dataclasses import dataclass

@dataclass
class EvalResult:
    total: int
    correct: int
    accuracy: float
    schema_ok: int
    schema_rate: float

def summarize(total: int, correct: int, schema_ok: int) -> EvalResult:
    acc = (correct / total) if total else 0.0
    srate = (schema_ok / total) if total else 0.0
    return EvalResult(total=total, correct=correct, accuracy=acc, schema_ok=schema_ok, schema_rate=srate)
