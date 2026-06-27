from abc import ABC, abstractmethod
from pydantic import BaseModel

class MetricResult(BaseModel):
    name: str
    score: float
    details: str

class Metric(ABC):
    @abstractmethod
    def name(self) -> str: pass
    
    @abstractmethod
    def evaluate(self, question: str, answer: str, context: list[str] = None, reference: str = None) -> MetricResult: pass

class FaithfulnessMetric(Metric):
    def name(self) -> str: return "faithfulness"
    def evaluate(self, question, answer, context=None, reference=None):
        # Placeholder for actual Ragas/DeepEval faithfulness call
        return MetricResult(name=self.name(), score=0.9, details="Highly faithful to context.")

class StructuralMetric(Metric):
    def name(self) -> str: return "structure"
    def evaluate(self, question, answer, context=None, reference=None):
        # Checks if intro, body, conclusion, and bullet points exist
        score = 0.5
        if "Introduction" in answer or "Intro" in answer: score += 0.2
        if "Conclusion" in answer: score += 0.2
        if "-" in answer or "*" in answer: score += 0.1
        return MetricResult(name=self.name(), score=score, details="Structural analysis")
