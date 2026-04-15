# DTO - Security Result

class SecurityResult:
    def __init__(self, risk_score: int, anomaly_detected: bool, error: str = None):
        self.risk_score = risk_score
        self.anomaly_detected = anomaly_detected
        self.error = error

    @classmethod
    def failure(cls, error: str):
        return cls(risk_score=0, anomaly_detected=False, error=error)
